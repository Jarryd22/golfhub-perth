import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app import golfhub_core as core
from app.shared_cache import make_snapshot
from scripts.refresh_cache_shard import reuse_prior_good_result


NOW = datetime(2026, 10, 7, 0, 10, tzinfo=timezone.utc)
DAY = "2026-10-07"
QUERY = "coords:-31.95,115.86"


def weather():
    return {
        "icon": "Rain", "icon_file": "sheet_rain.png", "label": "Rain",
        "tmax": 18, "tmin": 9, "rain_chance": 80, "rain_mm": 4.2,
        "rain_amount_label": "4.2 mm", "wind": 25,
        "fetched_at": (NOW - timedelta(minutes=20)).isoformat(), "reused": True,
    }


def provider_response():
    return {"daily": {
        "time": [DAY], "weather_code": [61], "temperature_2m_max": [18],
        "temperature_2m_min": [9], "precipitation_probability_max": [80],
        "precipitation_sum": [4.2], "wind_speed_10m_max": [25],
    }}


class WeatherConsumerTests(unittest.TestCase):
    def setUp(self):
        core.preload_weather_cache({})
        core.GEOCODE_CACHE.clear()
        self.addCleanup(core.preload_weather_cache, {})
        self.addCleanup(core.GEOCODE_CACHE.clear)

    def test_timestamped_weather_obeys_exact_age_boundary(self):
        for seconds_old, expected in ((0, True), (3599, True), (3600, False), (3601, False), (-1, False)):
            with self.subTest(seconds_old=seconds_old):
                forecast = {**weather(), "fetched_at": (NOW - timedelta(seconds=seconds_old)).isoformat()}
                self.assertEqual(core.weather_is_usable(forecast, now=NOW), expected)

    def test_missing_forecasts_and_invalid_or_naive_timestamps_are_unusable(self):
        self.assertFalse(core.weather_is_usable(None, now=NOW))
        self.assertFalse(core.weather_is_usable({}, now=NOW))
        for stamp in (None, 7, "", "invalid", NOW.replace(tzinfo=None).isoformat()):
            with self.subTest(stamp=stamp):
                self.assertFalse(core.weather_is_usable({**weather(), "fetched_at": stamp}, now=NOW))

    def test_aware_offsets_and_zulu_timestamps_use_the_same_instant(self):
        source = NOW - timedelta(minutes=20)
        stamps = (source.isoformat().replace("+00:00", "Z"),
                  source.astimezone(timezone(timedelta(hours=8))).isoformat())
        for stamp in stamps:
            with self.subTest(stamp=stamp):
                self.assertTrue(core.weather_is_usable({**weather(), "fetched_at": stamp}, now=NOW))

    def test_preloaded_expired_or_future_weather_never_refetches(self):
        with patch.object(core, "datetime", wraps=datetime) as clock, patch.object(core, "fetch_json") as fetch:
            clock.now.return_value = NOW
            for age in (3600, 7200, -1):
                with self.subTest(age=age):
                    stamp = (NOW - timedelta(seconds=age)).isoformat()
                    original = {QUERY: {DAY: {**weather(), "fetched_at": stamp}}}
                    core.preload_weather_cache(original)
                    self.assertIsNone(core.get_weather_for_date(QUERY, DAY, "Course"))
                    self.assertIsNone(core.get_weather_for_date(QUERY, DAY, "Course", retry_budget=core.WeatherRetryBudget()))
                    self.assertEqual(core.weather_cache_snapshot(), original)
        fetch.assert_not_called()

    def test_reused_shared_weather_keeps_source_metadata_through_lookup_and_snapshot(self):
        original = weather()
        core.preload_weather_cache({QUERY: {DAY: original}})
        with patch.object(core, "datetime", wraps=datetime) as clock, patch.object(core, "fetch_json") as fetch:
            clock.now.return_value = NOW
            selected = core.get_weather_for_date(QUERY, DAY, "Course")
            snapshot = make_snapshot(DAY, "18", [{"site_name": "Course", "weather": selected}])
        stored = json.loads(json.dumps(snapshot))["results"][0]["weather"]
        self.assertEqual(stored["fetched_at"], original["fetched_at"])
        self.assertIs(stored["reused"], True)
        self.assertEqual(stored["rain_mm"], 4.2)
        self.assertEqual(stored["location_name"], "Course")
        self.assertNotIn("location_name", core.weather_cache_snapshot()[QUERY][DAY])
        fetch.assert_not_called()

    def test_new_shared_forecast_is_stamped_once_and_keeps_fresh_metadata(self):
        with patch.object(core, "datetime", wraps=datetime) as clock, patch.object(core, "fetch_json", return_value=provider_response()) as fetch:
            clock.now.return_value = NOW
            first = core.get_weather_for_date(QUERY, DAY, "First", retry_budget=core.WeatherRetryBudget())
            clock.now.return_value = NOW + timedelta(minutes=30)
            second = core.get_weather_for_date(QUERY, DAY, "Second", retry_budget=core.WeatherRetryBudget())
        self.assertEqual(first["fetched_at"], NOW.isoformat(timespec="seconds"))
        self.assertEqual(second["fetched_at"], first["fetched_at"])
        self.assertIs(first["reused"], False)
        self.assertIs(second["reused"], False)
        self.assertEqual(second["location_name"], "Second")
        fetch.assert_called_once()

    def test_default_desktop_lookup_remains_unstamped_and_keeps_existing_cache_behavior(self):
        with patch.object(core, "datetime", wraps=datetime) as clock, patch.object(core, "fetch_json", return_value=provider_response()) as fetch:
            clock.now.return_value = NOW
            first = core.get_weather_for_date(QUERY, DAY, "Course")
            clock.now.return_value = NOW + timedelta(hours=2)
            later = core.get_weather_for_date(QUERY, DAY, "Course")
        self.assertIsNotNone(later)
        self.assertEqual(later, first)
        self.assertNotIn("fetched_at", first)
        self.assertNotIn("reused", first)
        fetch.assert_called_once()

    def test_tee_time_fallback_uses_current_weather_including_missing_or_none(self):
        site = SimpleNamespace(name="Course", provider="miclub", domain="course.example")
        prior_weather = {**weather(), "fetched_at": (NOW - timedelta(hours=2)).isoformat()}
        previous = {
            "generated_at": (NOW - timedelta(minutes=10)).isoformat(),
            "results": [{"site_name": site.name, "error": None,
                         "decorated_rows": [{"time": "7:00 am"}], "weather": prior_weather}],
        }
        current = {**weather(), "reused": False, "fetched_at": NOW.isoformat()}
        for extra, expected in (({}, None), ({"weather": None}, None), ({"weather": current}, current)):
            with self.subTest(extra=extra):
                fresh = {"site_name": site.name, "error": "temporary timeout", "decorated_rows": [], **extra}
                result, reused = reuse_prior_good_result(site, fresh, previous)
                self.assertTrue(reused)
                self.assertTrue(result["stale"])
                self.assertEqual(result["decorated_rows"], [{"time": "7:00 am"}])
                self.assertEqual(result["weather"], expected)
                self.assertEqual(previous["results"][0]["weather"], prior_weather)


if __name__ == "__main__":
    unittest.main()
