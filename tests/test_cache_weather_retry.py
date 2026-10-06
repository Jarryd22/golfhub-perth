import json
import socket
import ssl
import threading
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import MagicMock, call, patch
from urllib.error import HTTPError, URLError

from app import golfhub_core as core
from scripts import prepare_weather_cache as preparation


class WeatherRetryTests(unittest.TestCase):
    query = "coords:-31.95,115.86"
    day = "2026-10-07"
    url = "https://api.open-meteo.com/v1/forecast?latitude=-31.95&longitude=115.86"
    response = {
        "daily": {
            "time": ["2026-10-07"],
            "weather_code": [61],
            "temperature_2m_max": [18],
            "temperature_2m_min": [9],
            "precipitation_probability_max": [80],
            "precipitation_sum": [4.2],
            "wind_speed_10m_max": [25],
        }
    }

    def setUp(self):
        core.preload_weather_cache({})
        core.GEOCODE_CACHE.clear()
        self.addCleanup(core.preload_weather_cache, {})
        self.addCleanup(core.GEOCODE_CACHE.clear)

    def test_success_uses_one_request_without_delay(self):
        with patch.object(core, "fetch_json", return_value=self.response) as fetch, patch.object(core, "sleep") as pause:
            result = core._fetch_weather_json(self.url, core.WeatherRetryBudget())
        self.assertIs(result, self.response)
        fetch.assert_called_once_with(self.url)
        pause.assert_not_called()

    def test_direct_and_wrapped_timeouts_recover_once(self):
        for error in (
            TimeoutError("timed out"),
            URLError(TimeoutError("_ssl.c:989: The handshake operation timed out")),
        ):
            with (
                self.subTest(error=error),
                patch.object(core, "fetch_json", side_effect=[error, self.response]) as fetch,
                patch.object(core, "sleep") as pause,
            ):
                result = core._fetch_weather_json(self.url, core.WeatherRetryBudget())
                self.assertIs(result, self.response)
                self.assertEqual(fetch.call_args_list, [call(self.url), call(self.url)])
                pause.assert_called_once_with(1)

    def test_default_lookup_does_not_enable_retries(self):
        with (
            patch.object(core, "fetch_json", side_effect=URLError(TimeoutError("handshake timed out"))) as fetch,
            patch.object(core, "sleep") as pause,
        ):
            self.assertIsNone(core.get_weather_for_date(self.query, self.day, "Course"))
        fetch.assert_called_once()
        pause.assert_not_called()

    def test_http_certificate_and_unconfirmed_failures_are_not_retried(self):
        errors = [
            HTTPError(self.url, status, "timeout", {}, None)
            for status in (401, 403, 429, 500, 503)
        ] + [
            # HTTPError is a URLError subclass; even a typed reason must not qualify.
            HTTPError(self.url, 429, TimeoutError("timed out"), {}, None),
            ssl.SSLCertVerificationError(1, "certificate verify failed"),
            URLError(ssl.SSLCertVerificationError(1, "certificate verify failed")),
            ssl.SSLError(1, "TLS protocol failure"),
            URLError(ssl.SSLError(1, "TLS protocol failure")),
            URLError("timed out"),
            URLError(socket.gaierror(-2, "Name or service not known")),
            ConnectionRefusedError("connection refused"),
            URLError(ConnectionRefusedError("connection refused")),
            ConnectionResetError("connection reset"),
            URLError(ConnectionResetError("connection reset")),
            json.JSONDecodeError("invalid JSON", "no", 0),
            ValueError("invalid forecast"),
        ]
        for error in errors:
            with (
                self.subTest(error=repr(error)),
                patch.object(core, "fetch_json", side_effect=error) as fetch,
                patch.object(core, "sleep") as pause,
            ):
                with self.assertRaises(type(error)):
                    core._fetch_weather_json(self.url, core.WeatherRetryBudget())
                fetch.assert_called_once_with(self.url)
                pause.assert_not_called()

    def test_failed_retry_stops_and_is_negative_cached(self):
        for second_error in (
            TimeoutError("second timeout"),
            HTTPError(self.url, 429, "Too Many Requests", {}, None),
            URLError(ssl.SSLCertVerificationError(1, "certificate verify failed")),
        ):
            with (
                self.subTest(error=repr(second_error)),
                patch.object(core, "fetch_json", side_effect=[TimeoutError("first timeout"), second_error]) as fetch,
                patch.object(core, "sleep") as pause,
            ):
                core.preload_weather_cache({})
                budget = core.WeatherRetryBudget()
                self.assertIsNone(core.get_weather_for_date(self.query, self.day, "Course", retry_budget=budget))
                self.assertIsNone(core.get_weather_for_date(self.query, "2026-10-08", "Course", retry_budget=budget))
                self.assertEqual(fetch.call_count, 2)
                pause.assert_called_once_with(1)
                self.assertEqual(core.weather_cache_snapshot(), {self.query: {}})

    def test_recovery_caches_actual_forecast_for_later_consumers(self):
        with (
            patch.object(core, "fetch_json", side_effect=[URLError(TimeoutError("handshake timed out")), self.response]) as fetch,
            patch.object(core, "sleep"),
        ):
            first = core.get_weather_for_date(self.query, self.day, "First", retry_budget=core.WeatherRetryBudget())
            second = core.get_weather_for_date(self.query, self.day, "Second")
            outside = core.get_weather_for_date(self.query, "2026-11-01", "Course")
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(first["tmax"], 18)
        self.assertEqual(first["rain_mm"], 4.2)
        self.assertEqual(first["location_name"], "First")
        self.assertEqual(second["location_name"], "Second")
        self.assertIsNone(outside)
        self.assertNotIn("stale", first)

    def test_preloaded_empty_forecast_prevents_even_opted_in_retry(self):
        core.preload_weather_cache({self.query: {}})
        with patch.object(core, "fetch_json") as fetch, patch.object(core, "sleep") as pause:
            self.assertIsNone(core.get_weather_for_date(self.query, self.day, "Course", retry_budget=core.WeatherRetryBudget()))
        fetch.assert_not_called()
        pause.assert_not_called()

    def test_geocode_timeout_does_not_gain_a_retry(self):
        with (
            patch.object(core, "geocode_location", side_effect=URLError(TimeoutError("timed out"))) as geocode,
            patch.object(core, "fetch_json") as fetch,
            patch.object(core, "sleep") as pause,
        ):
            self.assertIsNone(core.get_weather_for_date("Perth", self.day, "Course", retry_budget=core.WeatherRetryBudget()))
        geocode.assert_called_once_with("Perth")
        fetch.assert_not_called()
        pause.assert_not_called()

    def test_concurrent_preparation_caps_extra_requests_and_resets_next_run(self):
        queries = [f"coords:-31.{number},115.86" for number in range(6)]
        for run in range(2):
            with self.subTest(run=run):
                core.preload_weather_cache({})
                requests = Counter()
                lock = threading.Lock()
                first_attempts = threading.Barrier(len(queries))

                def fetch(url):
                    with lock:
                        requests[url] += 1
                        attempt = requests[url]
                    if attempt == 1:
                        first_attempts.wait(timeout=5)
                        raise URLError(TimeoutError("handshake timed out"))
                    return self.response

                with patch.object(core, "fetch_json", side_effect=fetch), patch.object(core, "sleep") as pause:
                    result = preparation.prepare_forecasts(queries, date.fromisoformat(self.day), len(queries))
                self.assertEqual(sum(requests.values()), len(queries) + 4)
                self.assertEqual(sorted(requests.values()), [1, 1, 2, 2, 2, 2])
                self.assertEqual(sum(bool(value) for value in result.values()), 4)
                self.assertEqual(set(result), set(queries))
                self.assertEqual(pause.call_count, 4)

    def test_concurrent_same_location_shares_one_retry_sequence(self):
        started = threading.Event()
        release = threading.Event()
        callers = threading.Barrier(8)
        lock = threading.Lock()
        attempts = 0
        budget = core.WeatherRetryBudget()

        def fetch(url):
            nonlocal attempts
            with lock:
                attempts += 1
                attempt = attempts
            if attempt == 1:
                started.set()
                if not release.wait(timeout=5):
                    raise AssertionError("test did not release initial weather request")
                raise URLError(TimeoutError("handshake timed out"))
            return self.response

        def lookup():
            callers.wait(timeout=5)
            return core.get_weather_for_date(self.query, self.day, "Course", retry_budget=budget)

        with patch.object(core, "fetch_json", side_effect=fetch), patch.object(core, "sleep") as pause:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(lookup) for _ in range(8)]
                try:
                    self.assertTrue(started.wait(timeout=5))
                finally:
                    release.set()
                results = [future.result(timeout=5) for future in futures]
        self.assertEqual(attempts, 2)
        self.assertTrue(all(result["rain_mm"] == 4.2 for result in results))
        pause.assert_called_once_with(1)
        self.assertEqual(core.WEATHER_INFLIGHT, {})

    def test_real_fetch_path_preserves_verified_tls_on_retry(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = json.dumps(self.response).encode("utf-8")
        with (
            patch.object(core.urllib.request, "urlopen", side_effect=[URLError(TimeoutError("handshake timed out")), response]) as open_url,
            patch.object(core, "sleep") as pause,
        ):
            result = core._fetch_weather_json(self.url, core.WeatherRetryBudget())
        self.assertEqual(result, self.response)
        self.assertEqual(open_url.call_count, 2)
        for attempt in open_url.call_args_list:
            self.assertEqual(attempt.args[0].full_url, self.url)
            self.assertEqual(attempt.kwargs["timeout"], 25)
            self.assertEqual(attempt.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(attempt.kwargs["context"].check_hostname)
        pause.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
