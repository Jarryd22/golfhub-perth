import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app import golfhub_core
from app.golfhub_core import (
    CONFIG_FILE,
    DATA_DIR,
    fetch_site_result,
    load_sites,
    parse_wembley_calendar_availability,
)
from app.shared_cache import make_snapshot
from scripts import build_cache_index, prepare_weather_cache, refresh_cache_shard


class WeatherCacheTests(unittest.TestCase):
    def setUp(self):
        with golfhub_core.WEATHER_CACHE_LOCK:
            golfhub_core.WEATHER_CACHE.clear()
            golfhub_core.WEATHER_INFLIGHT.clear()
        golfhub_core.GEOCODE_CACHE.clear()

    def test_one_forecast_response_serves_multiple_dates(self):
        query = "coords:-31.95,115.86"
        daily = {
            "time": ["2026-07-14", "2026-07-15"],
            "weather_code": [0, 61],
            "temperature_2m_max": [20, 18],
            "temperature_2m_min": [10, 9],
            "precipitation_probability_max": [0, 80],
            "precipitation_sum": [0, 4.2],
            "wind_speed_10m_max": [12, 25],
        }
        with (
            patch.object(golfhub_core, "geocode_location", return_value=(-31.95, 115.86)),
            patch.object(golfhub_core, "fetch_json", return_value={"daily": daily}) as fetch,
        ):
            first = golfhub_core.get_weather_for_date(query, "2026-07-14", "Course A")
            second = golfhub_core.get_weather_for_date(query, "2026-07-15", "Course B")
            outside = golfhub_core.get_weather_for_date(query, "2026-07-30", "Course C")
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(first["location_name"], "Course A")
        self.assertEqual(second["rain_chance"], 80)
        self.assertIsNone(outside)

    def test_preloaded_empty_forecast_prevents_shard_network_retry(self):
        query = "coords:-31.95,115.86"
        golfhub_core.preload_weather_cache({query: {}})
        with patch.object(golfhub_core, "fetch_json") as fetch:
            self.assertIsNone(golfhub_core.get_weather_for_date(query, "2026-07-14", "Course"))
        fetch.assert_not_called()

    def test_empty_weather_forecasts_are_retried_sequentially(self):
        first = {"a": {}, "b": {"2026-07-14": {"label": "Clear"}}}
        recovered = {
            "a": {"2026-07-14": {"label": "Rain"}},
            "b": first["b"],
        }
        with (
            patch.object(prepare_weather_cache, "get_weather_for_date") as fetch,
            patch.object(prepare_weather_cache, "weather_cache_snapshot", side_effect=[first, recovered]),
            patch.object(prepare_weather_cache, "preload_weather_cache") as preload,
            patch.object(prepare_weather_cache, "sleep") as pause,
        ):
            result = prepare_weather_cache.prepare_forecasts(
                ["a", "b"], date(2026, 7, 14), 2, retry_delays=(0.0,)
            )
        self.assertEqual(result, recovered)
        self.assertEqual(fetch.call_count, 3)
        preload.assert_called_once_with({"b": first["b"]})
        pause.assert_called_once_with(0.0)

    def test_weather_exception_does_not_suppress_tee_time_result(self):
        site = next(site for site in load_sites(DATA_DIR / CONFIG_FILE) if site.name == "Araluen")
        with (
            patch.object(golfhub_core, "get_weather_for_date", side_effect=RuntimeError("weather offline")),
            patch.object(golfhub_core, "fetch_site_text", return_value="<html><body>No times</body></html>"),
        ):
            result = fetch_site_result(site, "2026-07-14", "18", None, None, None)
        self.assertIsNone(result["weather"])
        self.assertIsNone(result["error"])


class WembleyCalendarTests(unittest.TestCase):
    html = """
        <div class="cell-heading"><p>15 July</p></div>
        <div class="row feeGroupRow feeGroupId-102184" data-feeid="102184">
          <h3>OLD Course 18 Holes</h3>
          <div class="cell" data-date="0" onclick="redirectToTimesheet('102184','2026-07-15');"></div>
        </div>
        <div class="row feeGroupRow feeGroupId-102193" data-feeid="102193">
          <h3>TUART Course 18H</h3>
          <div class="cell cell-na" data-date="0">Timesheet Full</div>
        </div>
    """

    def test_calendar_parser_distinguishes_available_full_and_unreleased(self):
        fee_ids = {"102184", "102193"}
        status, labels = parse_wembley_calendar_availability(self.html, "2026-07-15", fee_ids)
        self.assertEqual(status, "available")
        self.assertEqual(labels, ["OLD Course 18 Holes"])
        full_html = self.html.replace(
            'onclick="redirectToTimesheet(\'102184\',\'2026-07-15\');"',
            "",
        )
        self.assertEqual(parse_wembley_calendar_availability(full_html, "2026-07-15", fee_ids)[0], "full")
        self.assertEqual(parse_wembley_calendar_availability(self.html, "2026-07-25", fee_ids)[0], "unreleased")

    def test_wembley_result_uses_calendar_status_not_protected_timesheet(self):
        site = next(site for site in load_sites(DATA_DIR / CONFIG_FILE) if site.name == "Wembley")
        with (
            patch.object(golfhub_core, "get_weather_for_date", return_value=None),
            patch.object(golfhub_core, "fetch_text", return_value=self.html) as fetch,
        ):
            result = fetch_site_result(site, "2026-07-15", "18", None, None, None)
        self.assertEqual(result["calendar_availability"], "available")
        self.assertEqual(result["decorated_rows"], [])
        self.assertIn("selectedDate=2026-07-15", result["url"])
        self.assertEqual(fetch.call_count, 1)


class CachePipelineTests(unittest.TestCase):
    base_date = date(2026, 7, 14)

    @classmethod
    def setUpClass(cls):
        cls.sites = load_sites(DATA_DIR / CONFIG_FILE)

    def _write_complete_cache(self, root: Path) -> None:
        for offset in range(28):
            date_str = (self.base_date + timedelta(days=offset)).isoformat()
            for hole_type in ("18", "9"):
                eligible = [site for site in self.sites if hole_type in site.holes]
                live_count = sum(site.provider != "direct" for site in eligible)
                results = []
                for site in eligible:
                    result = {
                        "site_name": site.name,
                        "url": f"https://{site.domain}",
                        "hole_label": f"{hole_type} holes",
                        "decorated_rows": [],
                        "error": None,
                        "not_configured": False,
                    }
                    if site.provider == "direct":
                        result["direct_booking"] = True
                    results.append(result)
                payload = make_snapshot(date_str, hole_type, results)
                payload["health"] = {
                    "live_provider_count": live_count,
                    "fresh_live_successes": live_count,
                    "minimum_live_successes": refresh_cache_shard.minimum_live_successes(live_count),
                    "stale_fallbacks": 0,
                }
                target = root / date_str / f"{hole_type}.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(payload), encoding="utf-8")

    def test_matrix_offsets_cover_exactly_28_days(self):
        offsets = {offset for start in (0, 4, 8, 12, 16, 20, 24) for offset in range(start, start + 4)}
        self.assertEqual(offsets, set(range(28)))
        self.assertEqual(refresh_cache_shard.parse_base_date("2026-07-14"), self.base_date)

    def test_health_gate_requires_strict_live_provider_majority(self):
        self.assertEqual(refresh_cache_shard.minimum_live_successes(14), 8)
        self.assertEqual(refresh_cache_shard.minimum_live_successes(15), 8)

    def test_prior_good_live_result_is_reused_and_marked_stale(self):
        site = next(site for site in self.sites if site.provider != "direct")
        fresh = {"site_name": site.name, "error": "temporary timeout", "decorated_rows": []}
        previous = make_snapshot(
            "2026-07-14",
            "18",
            [{"site_name": site.name, "error": None, "decorated_rows": [{"time": "7:00 am"}]}],
        )
        reused, did_reuse = refresh_cache_shard.reuse_prior_good_result(site, fresh, previous)
        self.assertTrue(did_reuse)
        self.assertTrue(reused["stale"])
        self.assertEqual(reused["stale_reason"], "temporary timeout")
        self.assertIsNone(reused["error"])

    def test_strict_index_accepts_only_complete_28_day_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_complete_cache(root)
            index = build_cache_index.build_cache_index(root, self.base_date, self.sites)
            self.assertEqual(len(index["dates"]), 28)
            (root / (self.base_date + timedelta(days=27)).isoformat() / "9.json").unlink()
            with self.assertRaises(build_cache_index.CacheValidationError):
                build_cache_index.build_cache_index(root, self.base_date, self.sites)

    def test_strict_index_rejects_wrong_course_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_complete_cache(root)
            target = root / self.base_date.isoformat() / "18.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["results"].pop()
            target.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(build_cache_index.CacheValidationError, "expected"):
                build_cache_index.build_cache_index(root, self.base_date, self.sites)


if __name__ == "__main__":
    unittest.main()