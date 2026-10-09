import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import golfhub_core as core
from app.shared_cache import make_snapshot, validate_snapshot
from scripts import prepare_weather_cache as preparation
from scripts import weather_state as state
from scripts.refresh_cache_shard import load_weather_artifact, reuse_prior_good_result


NOW = datetime(2026, 10, 9, 16, 37, tzinfo=timezone.utc)
DAY = "2026-10-24"
MISSING_DAY = "2026-10-25"
LATER_DAY = "2026-10-26"
QUERY = "coords:-31.95,115.86"
DAILY_VALUES = {
    "weather_code": 61,
    "temperature_2m_max": 18,
    "temperature_2m_min": 9,
    "precipitation_probability_max": 80,
    "precipitation_sum": 4.2,
    "wind_speed_10m_max": 25,
}


def daily_response(days=(DAY,), *, zero=False):
    return {"daily": {
        "time": list(days),
        **{field: [0 if zero else value] * len(days)
           for field, value in DAILY_VALUES.items()},
    }}


class IncompleteWeatherTests(unittest.TestCase):
    def setUp(self):
        core.preload_weather_cache({})
        self.addCleanup(core.preload_weather_cache, {})
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "weather.json"
        self.site = SimpleNamespace(name="Course", provider="miclub", domain="course.example",
                                    weather_query=QUERY)
        # Even an accidental lookup outside a fixture must remain offline.
        self.geocode = self.enterContext(patch.object(core, "geocode_location", return_value=(-31.95, 115.86)))
        self.enterContext(patch.object(core, "fetch_json", side_effect=AssertionError("Unexpected provider request")))
        self.enterContext(patch.object(core.logging, "warning"))

    def test_each_incomplete_field_omits_day_in_direct_and_retry_enabled_lookups(self):
        invalid_arrays = ([], None, "0", 0, True, {"0": 0})
        invalid_values = (None, "0", True, False, float("nan"), float("inf"), -float("inf"))
        for retry_enabled in (False, True):
            for field in DAILY_VALUES:
                for kind, value in (
                    [("missing", None)]
                    + [("array", value) for value in invalid_arrays]
                    + [("value", value) for value in invalid_values]
                ):
                    with self.subTest(retry_enabled=retry_enabled, field=field, kind=kind, value=value):
                        response = daily_response()
                        if kind == "missing":
                            del response["daily"][field]
                        else:
                            response["daily"][field] = [value] if kind == "value" else value
                        core.preload_weather_cache({})
                        budget = core.WeatherRetryBudget() if retry_enabled else None
                        with patch.object(core, "fetch_json", return_value=response) as fetch, patch.object(core, "sleep") as pause:
                            self.assertIsNone(core.get_weather_for_date(QUERY, DAY, "Course", retry_budget=budget))
                            self.assertIsNone(core.get_weather_for_date(QUERY, DAY, "Course", retry_budget=budget))
                        self.assertEqual(core.weather_cache_snapshot(), {QUERY: {}})
                        fetch.assert_called_once()
                        pause.assert_not_called()

    def test_short_arrays_keep_complete_days_without_fabricating_the_tail(self):
        for field in DAILY_VALUES:
            with self.subTest(field=field):
                response = daily_response((DAY, MISSING_DAY))
                response["daily"][field].pop()
                core.preload_weather_cache({})
                with patch.object(core, "fetch_json", return_value=response) as fetch:
                    first = core.get_weather_for_date(QUERY, DAY, "Course")
                    self.assertIsNone(core.get_weather_for_date(QUERY, MISSING_DAY, "Course"))
                self.assertEqual(first["label"], "Light rain")
                self.assertEqual(set(core.weather_cache_snapshot()[QUERY]), {DAY})
                fetch.assert_called_once()

    def test_bad_middle_row_does_not_discard_later_complete_days(self):
        for field in DAILY_VALUES:
            for invalid in (None, "invalid", float("nan")):
                with self.subTest(field=field, invalid=invalid):
                    response = daily_response((DAY, MISSING_DAY, LATER_DAY))
                    response["daily"][field][1] = invalid
                    core.preload_weather_cache({})
                    with patch.object(core, "fetch_json", return_value=response) as fetch:
                        first = core.get_weather_for_date(QUERY, DAY, "Course")
                        self.assertIsNone(core.get_weather_for_date(QUERY, MISSING_DAY, "Course"))
                        later = core.get_weather_for_date(QUERY, LATER_DAY, "Course")
                    self.assertEqual(first, later)
                    self.assertEqual(set(core.weather_cache_snapshot()[QUERY]), {DAY, LATER_DAY})
                    fetch.assert_called_once()

    def test_invalid_middle_row_does_not_hide_complete_neighboring_days(self):
        invalid_fields = (
            ("weather_code", 0.5), ("weather_code", 999),
            ("temperature_2m_max", 10 ** 400),
            ("precipitation_probability_max", -1), ("precipitation_probability_max", 101),
            ("precipitation_sum", -0.1), ("wind_speed_10m_max", -1),
            ("time", None), ("time", 20261025), ("time", "20261025"),
            ("time", "2026-02-30"), ("time", "2026-10-25T00:00:00"),
        )
        for field, value in invalid_fields:
            with self.subTest(field=field, value=value):
                response = daily_response((DAY, MISSING_DAY, LATER_DAY))
                response["daily"][field][1] = value
                core.preload_weather_cache({})
                with patch.object(core, "fetch_json", return_value=response) as fetch:
                    first = core.get_weather_for_date(QUERY, DAY, "Course")
                    self.assertIsNone(core.get_weather_for_date(QUERY, MISSING_DAY, "Course"))
                    later = core.get_weather_for_date(QUERY, LATER_DAY, "Course")
                self.assertEqual(first["tmax"], 18)
                self.assertEqual(first, later)
                self.assertEqual(set(core.weather_cache_snapshot()[QUERY]), {DAY, LATER_DAY})
                fetch.assert_called_once()

    def test_absent_or_malformed_daily_and_time_containers_remain_unavailable(self):
        responses = ({}, {"daily": None}, {"daily": []}, {"daily": {}},
                     {"daily": {"time": None}}, {"daily": {"time": DAY}})
        for response in responses:
            with self.subTest(response=response):
                core.preload_weather_cache({})
                with patch.object(core, "fetch_json", return_value=response) as fetch:
                    self.assertIsNone(core.get_weather_for_date(QUERY, DAY, "Course"))
                    self.assertIsNone(core.get_weather_for_date(QUERY, LATER_DAY, "Course"))
                self.assertEqual(core.weather_cache_snapshot(), {QUERY: {}})
                fetch.assert_called_once()

    def test_all_null_october_25_fixture_never_becomes_clear_and_zero(self):
        # This is an inferred upstream fixture, not a captured provider response.
        response = daily_response((DAY, MISSING_DAY))
        for field in DAILY_VALUES:
            response["daily"][field][1] = None
        with patch.object(core, "fetch_json", return_value=response) as fetch:
            self.assertIsNone(core.get_weather_for_date(QUERY, MISSING_DAY, "Course"))
            earlier = core.get_weather_for_date(QUERY, DAY, "Course")
        self.assertEqual(earlier["rain_mm"], 4.2)
        self.assertEqual(set(core.weather_cache_snapshot()[QUERY]), {DAY})
        fetch.assert_called_once()

    def test_genuine_numeric_zero_remains_a_valid_forecast(self):
        for retry_enabled, zero in ((False, 0), (False, 0.0), (True, 0), (True, 0.0)):
            with self.subTest(retry_enabled=retry_enabled, zero=zero):
                core.preload_weather_cache({})
                budget = core.WeatherRetryBudget() if retry_enabled else None
                response = daily_response(zero=True)
                for field in DAILY_VALUES:
                    response["daily"][field] = [zero]
                with patch.object(core, "fetch_json", return_value=response):
                    weather = core.get_weather_for_date(QUERY, DAY, "Course", retry_budget=budget)
                self.assertEqual(weather["label"], "Clear")
                self.assertEqual(weather["rain_amount_label"], "0 mm")
                for field in ("tmax", "tmin", "rain_chance", "rain_mm", "wind"):
                    self.assertEqual(weather[field], 0)

    def run_worker(self, command, **kwargs):
        self.assertEqual(kwargs, {"timeout": 90, "check": True})
        with patch("sys.argv", command[1:]):
            return preparation.main()

    def prepare(self):
        return preparation.prepare_bounded(
            self.output, date.fromisoformat(DAY), [QUERY], 1, 90, previous_weather=self.output,
        )

    def test_incomplete_policy_response_is_negative_cached_through_artifact_and_shard(self):
        response = daily_response()
        response["daily"]["temperature_2m_min"] = [None]
        with (
            patch.object(preparation, "load_sites", return_value=[self.site]),
            patch.object(preparation.subprocess, "run", side_effect=self.run_worker),
            patch.object(core, "fetch_json", return_value=response) as fetch,
            patch.object(core, "sleep") as pause,
            patch.object(state, "utc_now", return_value=NOW),
        ):
            payload = self.prepare()
        fetch.assert_called_once()
        pause.assert_not_called()
        self.assertEqual(payload["preparation"]["status"], "partial")
        self.assertEqual(payload["preparation"]["unavailable_locations"], [QUERY])
        self.assertEqual(payload["forecasts"], {QUERY: {}})
        self.assertEqual(json.loads(self.output.read_text())["forecasts"], {QUERY: {}})

        core.preload_weather_cache({})
        self.geocode.reset_mock()
        with patch.object(core, "fetch_json") as shard_fetch:
            load_weather_artifact(self.output, date.fromisoformat(DAY), [self.site])
            current_weather = core.get_weather_for_date(QUERY, DAY, self.site.name)
            self.assertIsNone(core.get_weather_for_date(QUERY, MISSING_DAY, self.site.name))
        shard_fetch.assert_not_called()
        self.geocode.assert_not_called()
        self.assertIsNone(current_weather)
        self.assertIn("Weather unavailable", core.weather_summary_text(current_weather))

        prior_weather = {"label": "Rain", "tmax": 18, "fetched_at": NOW.isoformat()}
        previous = make_snapshot(DAY, "18", [{"site_name": self.site.name, "error": None,
                                              "decorated_rows": [{"time": "7:00 am"}],
                                              "weather": prior_weather}])
        fresh = {"site_name": self.site.name, "error": "temporary timeout",
                 "decorated_rows": [], "weather": current_weather}
        result, reused = reuse_prior_good_result(self.site, fresh, previous)
        self.assertTrue(reused)
        self.assertEqual(result["decorated_rows"], [{"time": "7:00 am"}])
        encoded = json.dumps(make_snapshot(DAY, "18", [result]), allow_nan=False)
        self.assertIn('"weather": null', encoded)
        restored = validate_snapshot(json.loads(encoded), DAY, "18")
        self.assertIsNone(restored["results"][0]["weather"])
        self.assertEqual(previous["results"][0]["weather"], prior_weather)

    def test_zero_forecast_survives_prepare_checkpoints_reuse_and_shard_loading(self):
        with (
            patch.object(preparation, "load_sites", return_value=[self.site]),
            patch.object(preparation.subprocess, "run", side_effect=self.run_worker),
            patch.object(preparation, "write_artifact", wraps=preparation.write_artifact) as write,
            patch.object(state, "utc_now", return_value=NOW) as now,
            patch.object(core, "datetime", wraps=datetime) as clock,
            patch.object(core, "fetch_json", return_value=daily_response(zero=True)) as fetch,
        ):
            clock.now.return_value = NOW
            first = self.prepare()
            fetch.assert_called_once()
            checkpoints = [call.args[3] for call in write.call_args_list]
            self.assertTrue(any(days.get(QUERY, {}).get(DAY, {}).get("tmax") == 0
                                for days in checkpoints))
            fetch.reset_mock()
            now.return_value = NOW + timedelta(minutes=20)
            clock.now.return_value = now.return_value
            second = self.prepare()
            core.preload_weather_cache({})
            load_weather_artifact(self.output, date.fromisoformat(DAY), [self.site])
            weather = core.get_weather_for_date(QUERY, DAY, self.site.name)
            fetch.assert_not_called()
        self.assertEqual(first["preparation"]["status"], "complete")
        self.assertEqual(second["preparation"]["status"], "complete")
        self.assertEqual(second["preparation"]["reused_locations"], [QUERY])
        self.assertEqual(weather["fetched_at"], first["forecasts"][QUERY][DAY]["fetched_at"])
        self.assertIs(weather["reused"], True)
        self.assertEqual(weather["label"], "Clear")
        restored = json.loads(json.dumps(make_snapshot(DAY, "18", [{"weather": weather}]), allow_nan=False))
        for field in ("tmax", "tmin", "rain_chance", "rain_mm", "wind"):
            self.assertEqual(restored["results"][0]["weather"][field], 0)


if __name__ == "__main__":
    unittest.main()
