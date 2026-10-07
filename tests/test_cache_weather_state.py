import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime
from unittest.mock import patch
from urllib.error import HTTPError

from app import golfhub_core as core
from scripts import prepare_weather_cache as preparation
from scripts import weather_state as state


NOW = datetime(2026, 10, 7, 0, 10, tzinfo=timezone.utc)
QUERY = "coords:-31.95,115.86"
URL = "https://api.open-meteo.com/v1/forecast"
DAY = "2026-10-07"


def forecast(fetched_at=None):
    return {
        "icon": "Rain",
        "icon_file": "rain.png",
        "label": "Rain",
        "tmax": 18,
        "tmin": 9,
        "rain_chance": 80,
        "rain_mm": 4.2,
        "rain_amount_label": "4.2 mm",
        "wind": 25,
        "fetched_at": fetched_at or (NOW - timedelta(minutes=20)).isoformat(),
        "reused": False,
    }


def payload():
    return {
        "schema": 1,
        "base_date": "2026-10-06",
        "generated_at": NOW.isoformat(),
        "forecasts": {QUERY: {DAY: forecast(), "2026-10-08": forecast()}},
    }


def limited(retry_after=None, status=429):
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError(URL, status, "Too Many Requests", headers, None)


def daily_response():
    return {
        "daily": {
            "time": [DAY],
            "weather_code": [61],
            "temperature_2m_max": [18],
            "temperature_2m_min": [9],
            "precipitation_probability_max": [80],
            "precipitation_sum": [4.2],
            "wind_speed_10m_max": [25],
        }
    }


class ReusableForecastTests(unittest.TestCase):
    def test_recent_forecast_survives_midnight_without_resetting_fetch_time(self):
        previous = payload()
        result = state.reusable_forecasts(previous, [QUERY], now=NOW)
        self.assertEqual(set(result[QUERY]), {DAY, "2026-10-08"})
        for day in result[QUERY].values():
            self.assertIs(day["reused"], True)
            self.assertEqual(day["fetched_at"], previous["forecasts"][QUERY][DAY]["fetched_at"])
        self.assertIs(previous["forecasts"][QUERY][DAY]["reused"], False)
        result[QUERY][DAY]["label"] = "changed copy"
        self.assertEqual(previous["forecasts"][QUERY][DAY]["label"], "Rain")

    def test_only_requested_locations_are_reused(self):
        previous = payload()
        previous["forecasts"]["unrequested"] = copy.deepcopy(previous["forecasts"][QUERY])
        self.assertEqual(set(state.reusable_forecasts(previous, [QUERY, "missing"], now=NOW)), {QUERY})

    def test_expiry_future_naive_and_invalid_fetch_timestamps_are_rejected(self):
        timestamps = (
            (NOW - timedelta(seconds=state.MAX_FORECAST_AGE_SECONDS)).isoformat(),
            (NOW - timedelta(seconds=state.MAX_FORECAST_AGE_SECONDS + 1)).isoformat(),
            (NOW + timedelta(seconds=1)).isoformat(),
            NOW.replace(tzinfo=None).isoformat(),
            "not a timestamp",
            None,
        )
        for timestamp in timestamps:
            with self.subTest(timestamp=timestamp):
                previous = payload()
                for day in previous["forecasts"][QUERY].values():
                    day["fetched_at"] = timestamp
                # A recent artifact generation time cannot refresh old weather.
                self.assertEqual(state.reusable_forecasts(previous, [QUERY], now=NOW), {})

    def test_forecast_just_inside_maximum_age_is_reused(self):
        previous = payload()
        timestamp = (NOW - timedelta(seconds=state.MAX_FORECAST_AGE_SECONDS - 1)).isoformat()
        for day in previous["forecasts"][QUERY].values():
            day["fetched_at"] = timestamp
        self.assertEqual(state.reusable_forecasts(previous, [QUERY], now=NOW)[QUERY][DAY]["fetched_at"], timestamp)

    def test_inconsistent_day_timestamps_discard_the_whole_location(self):
        previous = payload()
        previous["forecasts"][QUERY]["2026-10-08"]["fetched_at"] = (NOW - timedelta(minutes=21)).isoformat()
        self.assertEqual(state.reusable_forecasts(previous, [QUERY], now=NOW), {})

    def test_missing_or_malformed_forecast_fields_discard_the_whole_location(self):
        required = ("icon", "icon_file", "label", "rain_amount_label", "tmin", "tmax", "rain_chance", "rain_mm", "wind", "fetched_at")
        for field in required:
            with self.subTest(missing=field):
                previous = payload()
                del previous["forecasts"][QUERY]["2026-10-08"][field]
                self.assertEqual(state.reusable_forecasts(previous, [QUERY], now=NOW), {})
        for field in ("tmin", "tmax", "rain_chance", "rain_mm", "wind"):
            for value in (float("nan"), float("inf"), -float("inf"), True, "18", None):
                with self.subTest(field=field, value=value):
                    previous = payload()
                    previous["forecasts"][QUERY]["2026-10-08"][field] = value
                    self.assertEqual(state.reusable_forecasts(previous, [QUERY], now=NOW), {})
        for field in ("icon", "icon_file", "label", "rain_amount_label"):
            with self.subTest(field=field):
                previous = payload()
                previous["forecasts"][QUERY][DAY][field] = 7
                self.assertEqual(state.reusable_forecasts(previous, [QUERY], now=NOW), {})

    def test_malformed_artifact_shapes_and_empty_locations_are_not_reused(self):
        for previous in (None, [], {}, {"schema": 2, "forecasts": payload()["forecasts"]},
                         {"schema": 1, "forecasts": []}, {"schema": 1, "forecasts": {QUERY: {}}},
                         {"schema": 1, "forecasts": {QUERY: {DAY: None}}}):
            with self.subTest(previous=previous):
                self.assertEqual(state.reusable_forecasts(previous, [QUERY], now=NOW), {})


class RateLimitStateTests(unittest.TestCase):
    def test_valid_positive_delta_and_http_date_are_honoured_exactly(self):
        for header, seconds in (("120", 120), ("7200", 7200),
                                (format_datetime(NOW + timedelta(seconds=90), usegmt=True), 90)):
            with self.subTest(header=header):
                result = state.cooldown_after_429(limited(header), now=NOW)
                self.assertEqual(datetime.fromisoformat(result["observed_at"]), NOW)
                self.assertEqual(datetime.fromisoformat(result["cooldown_until"]), NOW + timedelta(seconds=seconds))
                self.assertEqual(result["retry_after"], header)

    def test_absent_invalid_zero_negative_or_past_retry_after_gets_default_cooldown(self):
        for header in (None, "", "not a delay", "0", "-1", "1.5", "inf",
                       format_datetime(NOW, usegmt=True),
                       format_datetime(NOW - timedelta(minutes=1), usegmt=True)):
            with self.subTest(header=header):
                result = state.cooldown_after_429(limited(header), now=NOW)
                self.assertEqual(datetime.fromisoformat(result["cooldown_until"]),
                                 NOW + timedelta(seconds=state.DEFAULT_COOLDOWN_SECONDS))

    def test_active_rate_limit_round_trips_without_extending_deadline(self):
        rate_limit = state.cooldown_after_429(limited("120"), now=NOW)
        later = NOW + timedelta(seconds=60)
        result = state.rate_limit_from({"schema": 1, "rate_limit": rate_limit}, now=later)
        self.assertEqual(result, rate_limit)
        result["cooldown_until"] = "changed copy"
        self.assertNotEqual(rate_limit["cooldown_until"], "changed copy")

    def test_expired_future_observation_and_malformed_cooldowns_are_discarded(self):
        valid = state.cooldown_after_429(limited("120"), now=NOW)
        variants = [
            {**valid, "cooldown_until": NOW.isoformat()},
            {**valid, "cooldown_until": (NOW - timedelta(seconds=1)).isoformat()},
            {**valid, "observed_at": (NOW + timedelta(seconds=1)).isoformat()},
            {**valid, "observed_at": "invalid"},
            {**valid, "observed_at": NOW.replace(tzinfo=None).isoformat()},
            {**valid, "cooldown_until": "invalid"},
            {**valid, "cooldown_until": (NOW + timedelta(hours=1)).replace(tzinfo=None).isoformat()},
            {}, None, [],
        ]
        for rate_limit in variants:
            with self.subTest(rate_limit=rate_limit):
                self.assertIsNone(state.rate_limit_from({"schema": 1, "rate_limit": rate_limit}, now=NOW))
        self.assertIsNone(state.rate_limit_from({"schema": 1, "rate_limit": valid}, now=NOW + timedelta(seconds=120)))


class WeatherRequestPolicyTests(unittest.TestCase):
    def setUp(self):
        core.preload_weather_cache({})
        core.GEOCODE_CACHE.clear()
        self.addCleanup(core.preload_weather_cache, {})
        self.addCleanup(core.GEOCODE_CACHE.clear)
        self.clock = patch.object(state, "utc_now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_429_checkpoints_cooldown_before_any_new_request_is_allowed(self):
        snapshots = []
        policy = state.WeatherRequestPolicy(checkpoint=lambda *args: snapshots.append(policy.snapshot()))
        with patch.object(core, "fetch_json", side_effect=limited("120")) as fetch:
            with self.assertRaises(HTTPError):
                policy.fetch_json(URL)
            with self.assertRaises(RuntimeError):
                policy.fetch_json(URL + "?later")
        fetch.assert_called_once_with(URL)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0], policy.snapshot())
        self.assertEqual(datetime.fromisoformat(snapshots[0]["cooldown_until"]), NOW + timedelta(seconds=120))

    def test_active_seed_cooldown_blocks_network(self):
        cooldown = state.cooldown_after_429(limited("120"), now=NOW)
        policy = state.WeatherRequestPolicy(rate_limit=cooldown)
        with patch.object(core, "fetch_json") as fetch:
            with self.assertRaises(RuntimeError):
                policy.fetch_json(URL)
        fetch.assert_not_called()
        self.assertEqual(policy.snapshot(), cooldown)

    def test_current_run_stays_stopped_even_after_short_cooldown_expires(self):
        policy = state.WeatherRequestPolicy()
        with patch.object(core, "fetch_json", side_effect=limited("1")) as fetch:
            with self.assertRaises(HTTPError):
                policy.fetch_json(URL)
            with patch.object(state, "utc_now", return_value=NOW + timedelta(seconds=2)):
                with self.assertRaises(RuntimeError):
                    policy.fetch_json(URL + "?later")
        fetch.assert_called_once_with(URL)

    def test_expired_seed_cooldown_allows_new_fetch(self):
        cooldown = state.cooldown_after_429(limited("120"), now=NOW - timedelta(minutes=3))
        policy = state.WeatherRequestPolicy(rate_limit=cooldown)
        response = daily_response()
        with patch.object(core, "fetch_json", return_value=response) as fetch:
            self.assertEqual(policy.fetch_json(URL), response)
        fetch.assert_called_once_with(URL)

    def test_non429_http_errors_do_not_create_cooldown(self):
        for status in (401, 403, 500, 503):
            with self.subTest(status=status):
                checkpoints = []
                policy = state.WeatherRequestPolicy(checkpoint=lambda *args: checkpoints.append(args))
                with patch.object(core, "fetch_json", side_effect=limited("7200", status=status)) as fetch:
                    with self.assertRaises(HTTPError):
                        policy.fetch_json(URL)
                fetch.assert_called_once_with(URL)
                self.assertIsNone(policy.snapshot())
                self.assertEqual(checkpoints, [])

    def test_concurrent_429s_stop_queued_requests_and_keep_longest_cooldown(self):
        workers = 4
        admitted = threading.Barrier(workers)
        lock = threading.Lock()
        attempts = 0
        checkpoints = []
        policy = state.WeatherRequestPolicy(checkpoint=lambda *args: checkpoints.append(policy.snapshot()))

        def fetch(url):
            nonlocal attempts
            with lock:
                attempts += 1
                attempt = attempts
            admitted.wait(timeout=5)
            raise limited(str(attempt * 60))

        queries = [f"coords:-31.{number},115.86" for number in range(12)]
        with patch.object(core, "fetch_json", side_effect=fetch), patch.object(core, "sleep") as pause:
            result = preparation.prepare_forecasts(queries, date.fromisoformat(DAY), workers, retry_budget=policy)
        self.assertEqual(attempts, workers)
        self.assertEqual(result, {query: {} for query in queries})
        self.assertTrue(checkpoints)
        self.assertEqual(datetime.fromisoformat(policy.snapshot()["cooldown_until"]), NOW + timedelta(seconds=240))
        pause.assert_not_called()

    def test_429_cancels_an_already_waiting_transport_retry(self):
        paused = threading.Event()
        release = threading.Event()
        policy = state.WeatherRequestPolicy()

        def pause(seconds):
            paused.set()
            if not release.wait(timeout=5):
                raise AssertionError("test did not release pending retry")

        def fetch(url):
            if url.endswith("timeout"):
                raise TimeoutError("handshake timed out")
            raise limited("120")

        with patch.object(core, "fetch_json", side_effect=fetch) as network, patch.object(core, "sleep", side_effect=pause):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(core._fetch_weather_json, URL + "?timeout", policy)
                try:
                    self.assertTrue(paused.wait(timeout=5))
                    with self.assertRaises(HTTPError):
                        policy.fetch_json(URL + "?limited")
                finally:
                    release.set()
                with self.assertRaises(RuntimeError):
                    pending.result(timeout=5)
        self.assertEqual(network.call_count, 2)

    def test_live_malformed_daily_payloads_are_rejected_before_caching(self):
        malformed = [{}, {"daily": {}}, {"daily": []}]
        for key in daily_response()["daily"]:
            missing = daily_response()
            del missing["daily"][key]
            malformed.append(missing)
        for key in daily_response()["daily"]:
            if key == "time":
                continue
            for value in (float("nan"), float("inf"), None, True, "18"):
                invalid = daily_response()
                invalid["daily"][key] = [value]
                malformed.append(invalid)
            wrong_length = daily_response()
            wrong_length["daily"][key] = []
            malformed.append(wrong_length)
        for response in malformed:
            with self.subTest(response=response):
                policy = state.WeatherRequestPolicy()
                with patch.object(core, "fetch_json", return_value=response):
                    with self.assertRaises(ValueError):
                        policy.fetch_json(URL)


if __name__ == "__main__":
    unittest.main()
