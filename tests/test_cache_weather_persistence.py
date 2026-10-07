import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from app import golfhub_core as core
from scripts import prepare_weather_cache as preparation
from scripts import weather_state as state
from test_cache_weather_state import daily_response, forecast, NOW, DAY, QUERY


class WeatherPersistenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "weather.json"
        self.addCleanup(core.preload_weather_cache, {})

    def run_worker(self, command, **kwargs):
        self.assertEqual(kwargs, {"timeout": 90, "check": True})
        with patch("sys.argv", command[1:]):
            return preparation.main()

    def prepare(self):
        return preparation.prepare_bounded(
            self.output, date.fromisoformat(DAY), [QUERY], 4, 90, previous_weather=self.output,
        )

    def test_next_run_reuses_forecast_without_network_or_timestamp_renewal(self):
        sites = [SimpleNamespace(weather_query=QUERY)]
        with (
            patch.object(preparation, "load_sites", return_value=sites),
            patch.object(preparation.subprocess, "run", side_effect=self.run_worker),
            patch.object(state, "utc_now", return_value=NOW) as now,
            patch.object(core, "datetime", wraps=datetime) as clock,
            patch.object(core, "fetch_json", return_value=daily_response()) as fetch,
        ):
            clock.now.return_value = NOW
            first = self.prepare()
            self.assertEqual(fetch.call_count, 1)
            fetch.reset_mock()
            now.return_value = NOW + timedelta(minutes=20)
            clock.now.return_value = now.return_value
            second = self.prepare()
            fetch.assert_not_called()
        first_day = first["forecasts"][QUERY][DAY]
        second_day = second["forecasts"][QUERY][DAY]
        self.assertEqual(second_day["fetched_at"], first_day["fetched_at"])
        self.assertFalse(first_day["reused"])
        self.assertTrue(second_day["reused"])
        self.assertEqual(second["preparation"]["reused_locations"], [QUERY])

    def test_rate_limit_survives_next_run_without_forecasts_or_sliding_deadline(self):
        sites = [SimpleNamespace(weather_query=QUERY)]
        error = HTTPError("https://weather.invalid", 429, "Limited", {}, None)
        with (
            patch.object(preparation, "load_sites", return_value=sites),
            patch.object(preparation.subprocess, "run", side_effect=self.run_worker),
            patch.object(state, "utc_now", return_value=NOW) as now,
            patch.object(core, "fetch_json", side_effect=error) as fetch,
        ):
            first = self.prepare()
            self.assertEqual(fetch.call_count, 1)
            fetch.reset_mock()
            now.return_value = NOW + timedelta(minutes=20)
            second = self.prepare()
            fetch.assert_not_called()
        self.assertEqual(second["rate_limit"], first["rate_limit"])
        self.assertEqual(second["forecasts"], {QUERY: {}})

    def test_parent_drops_forecast_that_expires_during_worker(self):
        previous = {"schema": 1, "forecasts": {QUERY: {DAY: forecast((NOW - timedelta(minutes=59)).isoformat())}}}
        self.output.write_text(json.dumps(previous), encoding="utf-8")
        with patch.object(state, "utc_now", return_value=NOW) as now:
            def finish(*args, **kwargs):
                now.return_value = NOW + timedelta(seconds=90)
            with patch.object(preparation.subprocess, "run", side_effect=finish):
                result = self.prepare()
        self.assertEqual(result["forecasts"], {QUERY: {}})
        self.assertEqual(result["preparation"]["status"], "partial")

    def test_restore_failure_skips_network_worker_and_reports_state_unavailable(self):
        with patch.object(preparation.subprocess, "run") as worker:
            result = preparation.prepare_bounded(
                self.output, date.fromisoformat(DAY), [QUERY], 4, 90, skip_fetch=True,
            )
        worker.assert_not_called()
        self.assertEqual(result["preparation"]["status"], "state_unavailable")
        self.assertEqual(result["forecasts"], {QUERY: {}})

    def test_reuse_requires_the_requested_day_even_with_recent_other_days(self):
        previous = {"schema": 1, "forecasts": {QUERY: {"2026-10-06": forecast()}}}
        self.assertEqual(state.reusable_forecasts(previous, [QUERY], NOW, required_date=DAY), {})

    def test_real_hung_worker_retains_forecast_and_429_checkpoint(self):
        # Run the actual worker and request gate in a killable process, with all
        # network calls replaced before it starts its pool.
        source = textwrap.dedent("""
            import sys, time
            from types import SimpleNamespace
            from unittest.mock import patch
            from urllib.error import HTTPError
            from urllib.parse import parse_qs, urlparse
            from app import golfhub_core as core
            from scripts import prepare_weather_cache as preparation
            response = RESPONSE
            def fetch(url):
                latitude = parse_qs(urlparse(url).query)['latitude'][0]
                if latitude == '-32.0':
                    raise HTTPError(url, 429, 'Limited', {'Retry-After':'7200'}, None)
                if latitude == '-33.0':
                    time.sleep(60)
                return response
            sites = [SimpleNamespace(weather_query=f'coords:-{n}.0,115.0') for n in (31,32,33)]
            sys.argv = ['prepare_weather_cache.py','--fetch-worker','--base-date',DAY,
                        '--workers','3','--output',OUTPUT]
            with patch.object(preparation,'load_sites',return_value=sites), patch.object(core,'fetch_json',side_effect=fetch):
                preparation.main()
        """).replace("RESPONSE", repr(daily_response())).replace("DAY", repr(DAY)).replace("OUTPUT", repr(str(self.output)))
        # A429 could otherwise finish before the hanging request is admitted.
        source = source.replace("response = ", "import threading\nbarrier = threading.Barrier(3)\nresponse = ")
        source = source.replace("def fetch(url):\n", "def fetch(url):\n    barrier.wait(timeout=5)\n")
        queries = [f"coords:-{n}.0,115.0" for n in (31, 32, 33)]
        started = time.monotonic()
        result = preparation.prepare_bounded(
            self.output, date.fromisoformat(DAY), queries, 3, 2,
            worker_command=[sys.executable, "-c", source],
        )
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(result["preparation"]["status"], "timed_out")
        self.assertTrue(result["forecasts"][queries[0]])
        self.assertEqual(result["forecasts"][queries[1]], {})
        self.assertEqual(result["forecasts"][queries[2]], {})
        self.assertEqual(result["rate_limit"]["retry_after"], "7200")
        self.assertEqual((state.timestamp(result["rate_limit"]["cooldown_until"])
                          - state.timestamp(result["rate_limit"]["observed_at"])).total_seconds(), 7200)


if __name__ == "__main__":
    unittest.main()
