import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import golfhub_core
from scripts import prepare_weather_cache as weather
from scripts.refresh_cache_shard import load_weather_artifact


class WeatherBudgetTests(unittest.TestCase):
    base_date = date(2026, 10, 4)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "weather.json"
        self.addCleanup(golfhub_core.preload_weather_cache, {})

    def prepare(self, **kwargs):
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(self.output.with_suffix(".md"))}):
            return weather.prepare_bounded(self.output, self.base_date, ["a", "b"], 4, 1, **kwargs)

    def test_hung_real_worker_is_killed_and_shards_do_not_refetch(self):
        started = time.monotonic()
        payload = self.prepare(worker_command=[sys.executable, "-c", "import time; time.sleep(60)"])
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(payload["preparation"]["status"], "timed_out")
        self.assertEqual(payload["forecasts"], {"a": {}, "b": {}})
        load_weather_artifact(self.output, self.base_date, [SimpleNamespace(weather_query=q) for q in ("a", "b")])
        with patch.object(golfhub_core, "fetch_json") as fetch:
            for query in ("a", "b"):
                self.assertIsNone(golfhub_core.get_weather_for_date(query, "2026-10-04", "Course"))
        fetch.assert_not_called()
        self.assertIn("timed_out", self.output.with_suffix(".md").read_text())

    def test_timeout_preserves_completed_checkpoint_and_completes_missing_keys(self):
        completed = {"a": {"2026-10-04": {"label": "Clear"}}}

        def checkpoint_then_timeout(*args, **kwargs):
            weather.write_artifact(self.output, self.base_date, ["a"], completed)
            raise subprocess.TimeoutExpired("worker", 1)

        with patch.object(weather.subprocess, "run", side_effect=checkpoint_then_timeout):
            payload = self.prepare()
        self.assertEqual(payload["forecasts"], {**completed, "b": {}})
        self.assertEqual(payload["preparation"]["unavailable_locations"], ["b"])
        self.assertEqual(payload["preparation"]["status"], "timed_out")

    def test_failed_worker_still_produces_complete_negative_cache(self):
        with patch.object(weather.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "worker")):
            payload = self.prepare()
        self.assertEqual(payload["preparation"]["status"], "worker_failed")
        self.assertEqual(payload["forecasts"], {"a": {}, "b": {}})

    def test_malformed_or_wrong_date_checkpoint_is_discarded(self):
        for malformed in ("null", "{", '{"schema": 1, "base_date": "2020-01-01"}',
                          json.dumps({"schema": 1, "base_date": "2026-10-04", "forecasts": {"a": {"day": 7}}})):
            with self.subTest(malformed=malformed):
                def corrupt(*args, **kwargs):
                    self.output.write_text(malformed, encoding="utf-8")
                with patch.object(weather.subprocess, "run", side_effect=corrupt):
                    payload = self.prepare()
                self.assertEqual(payload["preparation"]["status"], "invalid_checkpoint")
                self.assertEqual(payload["forecasts"], {"a": {}, "b": {}})

    def test_empty_forecasts_are_not_retried_by_default(self):
        with (
            patch.object(weather, "get_weather_for_date") as fetch,
            patch.object(weather, "weather_cache_snapshot", return_value={"a": {}, "b": {}}),
            patch.object(weather, "sleep") as pause,
        ):
            result = weather.prepare_forecasts(["a", "b"], self.base_date, 2)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(result, {"a": {}, "b": {}})
        pause.assert_not_called()

    def test_worker_checkpoints_each_completed_location(self):
        with (
            patch.object(weather, "get_weather_for_date"),
            patch.object(weather, "weather_cache_snapshot", return_value={"a": {}}),
        ):
            checkpoints = []
            weather.prepare_forecasts(["a", "b"], self.base_date, 2, checkpoint=checkpoints.append)
        self.assertEqual(len(checkpoints), 2)

    def test_successful_worker_reports_weather_availability(self):
        def complete(*args, **kwargs):
            weather.write_artifact(self.output, self.base_date, ["a", "b"],
                                   {q: {"2026-10-04": {"label": "Clear"}} for q in ("a", "b")})
        with patch.object(weather.subprocess, "run", side_effect=complete):
            payload = self.prepare()
        self.assertEqual(payload["preparation"]["status"], "complete")
        self.assertEqual(payload["preparation"]["unavailable_locations"], [])


if __name__ == "__main__":
    unittest.main()
