import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import golfhub_core as core
from app.shared_cache import make_snapshot, validate_snapshot
from scripts import refresh_cache_shard as shard


class WembleyFallbackTests(unittest.TestCase):
    now = datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc)
    date_str = "2026-10-17"
    html = """
        <script>var publicCaptchaEnabled = true;</script>
        <div class="cell-heading"><p>17 October</p></div>
        <div class="row feeGroupRow" data-feeid="102184">
          <h3>OLD Course 18 Holes</h3>
          <div class="cell" data-date="0" onclick="redirectToTimesheet('102184','2026-10-17');"></div>
        </div>
        <div class="row feeGroupRow" data-feeid="102193">
          <h3>TUART Course 18H</h3><div class="cell cell-na" data-date="0">Timesheet Full</div>
        </div>
    """

    @classmethod
    def setUpClass(cls):
        cls.site = next(site for site in core.load_sites(core.DATA_DIR / core.CONFIG_FILE) if site.name == "Wembley")

    def failed(self, **extra):
        return {
            "site_name": self.site.name,
            "url": core.wembley_calendar_url(self.site, self.date_str),
            "hole_label": "18 holes",
            "decorated_rows": [],
            "weather": None,
            "error": "timed out",
            **extra,
        }

    def previous(self, age=timedelta(minutes=10), **extra):
        stamp = (self.now - age).isoformat()
        return {
            "date": self.date_str,
            "holes": "18",
            "generated_at": stamp,
            "results": [{
                "site_name": self.site.name,
                "url": "https://old.example/calendar",
                "hole_label": "18 holes",
                "decorated_rows": [],
                "weather": {"label": "Old forecast"},
                "error": None,
                "calendar_availability": "available",
                **extra,
            }],
        }

    def fetch_calendar(self, html, date_str=None, holes="18"):
        with (
            patch.object(core, "_wembley_now", return_value=self.now),
            patch.object(core, "get_weather_for_date", return_value=None),
            patch.object(core, "fetch_text", return_value=html) as calendar_fetch,
            patch.object(core, "fetch_site_text") as exact_fetch,
        ):
            result = core.fetch_site_result(self.site, date_str or self.date_str, holes, None, None, None)
        calendar_fetch.assert_called_once()
        exact_fetch.assert_not_called()
        return result

    def test_missing_18_hole_products_remain_unknown_without_historical_substitution(self):
        nine_html = self.html.replace("102184", "102211").replace("102193", "102202").replace("18 Holes", "9 Holes").replace("18H", "9H")
        result = self.fetch_calendar(nine_html)
        self.assertEqual(result["calendar_availability"], "unknown")
        self.assertEqual(result["calendar_error_kind"], "products_missing")
        self.assertIn("availability is unknown", result["error"])
        self.assertEqual(result["decorated_rows"], [])
        reused, did_reuse = shard.reuse_prior_good_result(self.site, result, self.previous(), now=self.now)
        self.assertFalse(did_reuse)
        self.assertIs(reused, result)
        self.assertNotIn("stale", reused)
        nine_result = self.fetch_calendar(nine_html, holes="9")
        self.assertEqual(nine_result["calendar_availability"], "available")
        self.assertIsNone(nine_result["error"])
        payload = make_snapshot(self.date_str, "18", [result])
        restored = validate_snapshot(json.loads(json.dumps(payload)), self.date_str, "18")
        self.assertEqual(restored["results"][0]["calendar_error_kind"], "products_missing")

    def test_partial_products_cannot_establish_full_or_unreleased(self):
        partial = self.html[:self.html.index('<div class="row feeGroupRow" data-feeid="102193">')]
        available = self.fetch_calendar(partial)
        self.assertEqual(available["calendar_availability"], "available")
        self.assertEqual(available["calendar_courses"], ["OLD Course 18 Holes"])
        without_available = partial.replace("redirectToTimesheet('102184','2026-10-17');", "")
        for requested_date in (self.date_str, "2026-10-25"):
            with self.subTest(date=requested_date):
                result = self.fetch_calendar(without_available, requested_date)
                self.assertEqual(result["calendar_availability"], "unknown")
                self.assertEqual(result["calendar_error_kind"], "products_missing")

    def test_complete_calendar_still_distinguishes_full_from_booking_horizon(self):
        full_html = self.html.replace("redirectToTimesheet('102184','2026-10-17');\"></div>", "\">Timesheet Full</div>")
        full = self.fetch_calendar(full_html)
        unreleased = self.fetch_calendar(self.html, "2026-10-25")
        self.assertEqual(full["calendar_availability"], "full")
        self.assertEqual(unreleased["calendar_availability"], "unreleased")
        for result in (full, unreleased):
            self.assertIsNone(result["error"])
            self.assertNotIn("calendar_error_kind", result)
            reused, did_reuse = shard.reuse_prior_good_result(self.site, result, self.previous(), now=self.now)
            self.assertFalse(did_reuse)
            self.assertIs(reused, result)

    def test_transport_failure_uses_prior_only_within_30_minutes(self):
        for age, expected in (
            (timedelta(0), True),
            (timedelta(minutes=29, seconds=59), True),
            (timedelta(minutes=30), True),
            (timedelta(minutes=30, seconds=1), False),
            (timedelta(hours=5), False),
        ):
            with self.subTest(age=age):
                fresh = self.failed()
                previous = self.previous(age)
                result, reused = shard.reuse_prior_good_result(self.site, fresh, previous, now=self.now)
                self.assertEqual(reused, expected)
                if reused:
                    self.assertTrue(result["stale"])
                    self.assertEqual(result["stale_since"], previous["generated_at"])
                    self.assertEqual(result["stale_reason"], fresh["error"])
                    self.assertEqual(result["last_refresh_attempt_at"], self.now.isoformat())
                    self.assertIsNone(result["weather"])
                    self.assertEqual(result["url"], fresh["url"])
                else:
                    self.assertIs(result, fresh)
                    self.assertNotIn("calendar_availability", result)

    def test_fallback_cannot_restore_weather_after_unexpected_fetch_failure(self):
        fresh = self.failed()
        fresh.pop("weather")
        result, reused = shard.reuse_prior_good_result(self.site, fresh, self.previous(), now=self.now)
        self.assertTrue(reused)
        self.assertIsNone(result["weather"])

    def test_republication_never_renews_original_stale_source_time(self):
        source = (self.now - timedelta(minutes=20)).isoformat()
        previous = self.previous(timedelta(minutes=1), stale=True, stale_since=source)
        result, reused = shard.reuse_prior_good_result(self.site, self.failed(), previous, now=self.now)
        self.assertTrue(reused)
        self.assertEqual(result["stale_since"], source)
        republished = {**previous, "generated_at": self.now.isoformat(), "results": [result]}
        later = self.now + timedelta(minutes=10, seconds=1)
        fresh = self.failed(error="new timeout")
        expired, reused = shard.reuse_prior_good_result(self.site, fresh, republished, now=later)
        self.assertFalse(reused)
        self.assertIs(expired, fresh)
        self.assertEqual(expired["error"], "new timeout")

    def test_invalid_source_times_fail_closed(self):
        for stamp in (None, "", "invalid", 123, "2026-10-06T23:50:00", "2026-10-07T00:00:01+00:00"):
            for stale in (False, True):
                with self.subTest(stamp=stamp, stale=stale):
                    previous = self.previous(stale=stale)
                    if stale:
                        previous["results"][0]["stale_since"] = stamp
                    else:
                        previous["generated_at"] = stamp
                    self.assertFalse(shard.reuse_prior_good_result(self.site, self.failed(), previous, now=self.now)[1])
        self.assertFalse(shard.reuse_prior_good_result(self.site, self.failed(), self.previous(stale=True), now=self.now)[1])

    def test_age_remains_absolute_across_perth_midnight(self):
        now = datetime.fromisoformat("2026-10-08T00:05:00+08:00")
        previous = self.previous()
        for stamp, expected in (
            ("2026-10-07T23:50:00+08:00", True),
            ("2026-10-07T15:50:00Z", True),
            ("2026-10-07T23:34:59+08:00", False),
        ):
            with self.subTest(stamp=stamp):
                previous["generated_at"] = stamp
                self.assertEqual(shard.reuse_prior_good_result(self.site, self.failed(), previous, now=now)[1], expected)
        self.assertEqual(shard.parse_base_date("2026-10-07").isoformat(), "2026-10-07")

    def test_other_provider_fallback_policy_is_unchanged(self):
        for provider in ("miclub", "quick18"):
            with self.subTest(provider=provider):
                other = SimpleNamespace(name=self.site.name, provider=provider, domain="other.example")
                previous = self.previous(timedelta(days=2))
                result, reused = shard.reuse_prior_good_result(other, self.failed(), previous, now=self.now)
                self.assertTrue(reused)
                self.assertEqual(result["stale_since"], previous["generated_at"])
        direct = SimpleNamespace(name=self.site.name, provider="direct", domain="other.example")
        self.assertFalse(shard.reuse_prior_good_result(direct, self.failed(), self.previous(), now=self.now)[1])

    def test_partial_exact_sheet_failure_preserves_current_rows(self):
        unprotected = self.html.replace("= true", "= false")
        rows = [{"time": "09:48 am", "spots": 1, "course_raw": "Old Course"}]
        with (
            patch.object(core, "get_weather_for_date", return_value=None),
            patch.object(core, "fetch_text", return_value=unprotected),
            patch.object(core, "fetch_site_text", side_effect=["public rows", TimeoutError("timed out")]) as fetch,
            patch.object(core, "save_debug_html"),
            patch.object(core, "parse_wembley_timesheet", return_value=rows),
        ):
            result = core.fetch_site_result(self.site, self.date_str, "18", None, None, None)
        self.assertEqual(fetch.call_count, 2)
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["decorated_rows"]), 1)
        self.assertNotIn("calendar_availability", result)

    def test_shard_publishes_unknown_for_isolated_mismatch_without_changing_gate(self):
        others = [SimpleNamespace(name=name, provider="miclub", domain=f"{name}.example", holes={"18": {}, "9": {}}) for name in ("Other", "Third")]
        sites = [self.site, *others]
        mismatch = self.failed(calendar_availability="unknown", calendar_error_kind="products_missing")

        def fetch(site, date_str, holes):
            if site is self.site and holes == "18":
                return mismatch
            return {"site_name": site.name, "error": None, "decorated_rows": []}

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            argv = ["refresh_cache_shard.py", "--start-offset", "0", "--days", "1", "--base-date", self.date_str, "--output", str(output)]
            with (
                patch("sys.argv", argv),
                patch.object(shard, "load_sites", return_value=sites),
                patch.object(shard, "fetch_one", side_effect=fetch),
                patch.object(shard, "load_previous_snapshot", return_value=self.previous()),
            ):
                self.assertEqual(shard.main(), 0)
            payload = json.loads((output / self.date_str / "18.json").read_text())
            nine = json.loads((output / self.date_str / "9.json").read_text())
        self.assertEqual(payload["health"]["fresh_live_successes"], 2)
        self.assertEqual(payload["health"]["minimum_live_successes"], 2)
        self.assertEqual(payload["health"]["stale_fallbacks"], 0)
        self.assertEqual(payload["results"][0]["calendar_availability"], "unknown")
        self.assertIsNotNone(payload["results"][0]["error"])
        self.assertEqual(nine["health"]["fresh_live_successes"], 3)


if __name__ == "__main__":
    unittest.main()
