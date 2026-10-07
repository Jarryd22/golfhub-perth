"""Offline integration of rendered Wembley rows with core and cache output."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app import golfhub_core as core
from app.shared_cache import make_snapshot, validate_snapshot
from scripts.refresh_cache_shard import reuse_prior_good_result


class WembleyRenderedIntegrationTests(unittest.TestCase):
    now = datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc)
    product_labels = {
        "102184": "OLD Course 18 Holes", "102193": "TUART Course 18H",
        "102211": "OLD Course 9 Holes", "102202": "TUART Course 9H",
    }

    @classmethod
    def setUpClass(cls):
        cls.site = next(site for site in core.load_sites(core.DATA_DIR / core.CONFIG_FILE) if site.name == "Wembley")

    def products(self, date_str, holes):
        return dict(zip(self.site.holes[holes].resolve_fee_group_ids(date_str), self.site.build_urls(date_str, holes)))

    def calendar(self, date_str, holes, *, available=None, omit=()):
        fee_ids = self.site.holes[holes].resolve_fee_group_ids(date_str)
        available = set(fee_ids) if available is None else set(available)
        header = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %b")
        html = f'<script>var publicCaptchaEnabled = true;</script><div class="cell-heading"><p>{header}</p></div>'
        for fee in fee_ids:
            if fee in omit:
                continue
            cell = (
                f'<div onclick="redirectToTimesheet(\'{fee}\',\'{date_str}\');"></div>'
                if fee in available else '<div class="cell cell-na">Timesheet Full</div>'
            )
            html += f'<div class="row feeGroupRow" data-feeid="{fee}"><h3>{self.product_labels[fee]}</h3>{cell}</div>'
        return html

    def rendered_rows(self, date_str, holes, fee_ids=None):
        products = self.products(date_str, holes)
        return [
            {
                "time": "05:48 am" if fee in {"102184", "102211"} else "06:04 am",
                "spots": 3 if fee in {"102184", "102211"} else 4,
                "course_raw": "Old Course" if fee in {"102184", "102211"} else "Tuart Course",
                "source_url": products[fee],
            }
            for fee in (fee_ids if fee_ids is not None else products)
        ]

    def fetch(self, html, date_str, holes, rendered):
        with (
            patch.object(core, "_wembley_now", return_value=self.now),
            patch.object(core, "get_weather_for_date", return_value=None),
            patch.object(core, "fetch_text", return_value=html) as calendar_fetch,
            patch.object(
                core, "collect_wembley_rows",
                **({"side_effect": rendered} if isinstance(rendered, Exception) else {"return_value": rendered}),
            ) as browser,
            patch.object(core, "fetch_site_text") as direct_fetch,
            patch.object(core, "save_debug_html") as debug,
        ):
            result = core.fetch_site_result(self.site, date_str, holes, None, None, None)
        calendar_fetch.assert_called_once_with(core.wembley_calendar_url(self.site, date_str))
        direct_fetch.assert_not_called()
        debug.assert_not_called()
        return result, browser

    def test_protected_browser_rows_cover_old_and_tuart_in_both_rounds(self):
        for date_str in ("2026-10-08", "2026-10-09"):
            for holes in ("18", "9"):
                with self.subTest(date=date_str, holes=holes):
                    products = self.products(date_str, holes)
                    result, browser = self.fetch(self.calendar(date_str, holes), date_str, holes, {
                        "rows": self.rendered_rows(date_str, holes),
                        "completed_products": list(products), "stop_reason": None,
                    })
                    browser.assert_called_once_with(
                        core.wembley_calendar_url(self.site, date_str), date_str, "3000000", products,
                    )
                    self.assertIsNone(result["error"])
                    self.assertNotIn("calendar_availability", result)
                    self.assertEqual(result["wembley_collection"], "complete")
                    self.assertEqual({row["course"] for row in result["decorated_rows"]}, {"Old Course", "Tuart Course"})
                    self.assertEqual([(row["time"], row["spots"]) for row in result["decorated_rows"]], [("05:48 am", 3), ("06:04 am", 4)])
                    self.assertEqual({row["source_url"] for row in result["decorated_rows"]}, set(products.values()))

    def test_only_available_products_are_sent_to_browser(self):
        date_str = "2026-10-08"
        for holes, available_fee in (("18", "102184"), ("9", "102202")):
            with self.subTest(holes=holes):
                products = self.products(date_str, holes)
                result, browser = self.fetch(self.calendar(date_str, holes, available={available_fee}), date_str, holes, {
                    "rows": self.rendered_rows(date_str, holes, [available_fee]),
                    "completed_products": [available_fee], "stop_reason": None,
                })
                self.assertEqual(browser.call_args.args[3], {available_fee: products[available_fee]})
                self.assertEqual(result["wembley_collection"], "complete")
                self.assertEqual(result["wembley_product_status"][available_fee], "available")
                self.assertEqual(set(result["wembley_product_status"].values()), {"available", "full"})

    def test_partial_collection_keeps_current_rows_with_notice(self):
        date_str, holes = "2026-10-08", "18"
        current_rows = self.rendered_rows(date_str, holes, ["102184"])
        result, _ = self.fetch(self.calendar(date_str, holes), date_str, holes, {
            "rows": current_rows, "completed_products": ["102184"], "stop_reason": "interactive_challenge",
        })
        self.assertIsNone(result["error"])
        self.assertNotIn("calendar_availability", result)
        self.assertEqual(result["rows"], current_rows)
        self.assertEqual(result["wembley_collection"], "partial")
        self.assertIn("Only some Wembley course times", result["booking_note"])
        self.assertEqual(result["wembley_completed_products"], ["102184"])

    def test_missing_other_product_cannot_claim_complete_exact_coverage(self):
        date_str, holes = "2026-10-08", "9"
        result, browser = self.fetch(self.calendar(date_str, holes, omit={"102202"}), date_str, holes, {
            "rows": self.rendered_rows(date_str, holes, ["102211"]),
            "completed_products": ["102211"], "stop_reason": None,
        })
        self.assertEqual(set(browser.call_args.args[3]), {"102211"})
        self.assertEqual(result["wembley_collection"], "partial")
        self.assertEqual(result["wembley_product_status"]["102202"], "unknown")
        self.assertIn("Only some Wembley course times", result["booking_note"])

    def test_empty_or_stopped_collection_keeps_fresh_calendar_without_stale_exact_rows(self):
        date_str, holes = "2026-10-08", "18"
        previous = make_snapshot(date_str, holes, [{
            "site_name": "Wembley", "error": None,
            "decorated_rows": [{"time": "07:07 am", "spots": 4}],
        }])
        previous["generated_at"] = (self.now - timedelta(minutes=1)).isoformat()
        for reason in (None, "interactive_challenge", "access_denied", "browser_disabled", "browser_unavailable"):
            with self.subTest(reason=reason):
                completed = list(self.products(date_str, holes)) if reason is None else []
                result, _ = self.fetch(self.calendar(date_str, holes), date_str, holes, {
                    "rows": [], "completed_products": completed, "stop_reason": reason,
                })
                self.assertEqual(result["calendar_availability"], "available")
                self.assertEqual(result["wembley_collection"], "calendar_only")
                self.assertEqual(result["wembley_stop_reason"], reason)
                self.assertEqual(result["decorated_rows"], [])
                self.assertIsNone(result["error"])
                reused, did_reuse = reuse_prior_good_result(self.site, result, previous, now=self.now)
                self.assertIs(reused, result)
                self.assertFalse(did_reuse)
                self.assertNotIn("stale", reused)

    def test_unexpected_browser_exception_retains_calendar_without_sensitive_error(self):
        date_str, holes = "2026-10-08", "18"
        result, browser = self.fetch(self.calendar(date_str, holes), date_str, holes, RuntimeError(
            "Failed https://www.wembleygolf.com.au/guests/bookings/ViewPublicTimesheet.msp?recaptchaResponse=FAKE_TEST_TOKEN",
        ))
        browser.assert_called_once()
        self.assertEqual(result["calendar_availability"], "available")
        self.assertEqual(result["wembley_collection"], "calendar_only")
        self.assertEqual(result["wembley_stop_reason"], "browser_error")
        self.assertIsNone(result["error"])
        self.assertEqual(result["decorated_rows"], [])
        previous = make_snapshot(date_str, holes, [{
            "site_name": "Wembley", "error": None,
            "decorated_rows": [{"time": "07:07 am", "spots": 4}],
        }])
        previous["generated_at"] = self.now.isoformat()
        reused, did_reuse = reuse_prior_good_result(self.site, result, previous, now=self.now)
        self.assertFalse(did_reuse)
        self.assertIs(reused, result)
        encoded = json.dumps(make_snapshot(date_str, holes, [result]))
        self.assertNotIn("recaptchaResponse", encoded)
        self.assertNotIn("FAKE_TEST_TOKEN", encoded)

    def test_full_unreleased_and_missing_products_skip_browser(self):
        for date_str, holes, html, expected in (
            ("2026-10-10", "18", self.calendar("2026-10-10", "18", available=set()), "full"),
            ("2026-10-10", "9", self.calendar("2026-10-10", "9", available=set()), "full"),
            ("2026-10-18", "18", '<p>No rows meeting selected criteria</p>', "unreleased"),
            ("2026-10-18", "9", '<p>No rows meeting selected criteria</p>', "unreleased"),
            ("2026-10-08", "18", self.calendar("2026-10-08", "9"), "unknown"),
        ):
            with self.subTest(date=date_str, holes=holes, expected=expected):
                result, browser = self.fetch(html, date_str, holes, {})
                browser.assert_not_called()
                self.assertEqual(result["calendar_availability"], expected)
                self.assertEqual(result["decorated_rows"], [])

    def test_snapshot_retains_safe_exact_rows_and_coverage_without_booking_state(self):
        date_str, holes = "2026-10-08", "18"
        result, _ = self.fetch(self.calendar(date_str, holes), date_str, holes, {
            "rows": self.rendered_rows(date_str, holes),
            "completed_products": list(self.products(date_str, holes)), "stop_reason": None,
        })
        payload = make_snapshot(date_str, holes, [result])
        encoded = json.dumps(payload)
        restored = validate_snapshot(json.loads(encoded), date_str, holes)["results"][0]
        self.assertEqual(restored["wembley_collection"], "complete")
        self.assertEqual(len(restored["decorated_rows"]), 2)
        self.assertNotIn("site", restored)
        for forbidden in ("recaptchaResponse", "g-recaptcha-response", "booking_row_id", "available_slot_ids", "minimum_booking_limit", "sessionId"):
            self.assertNotIn(forbidden.lower(), encoded.lower())
        for row in restored["decorated_rows"]:
            self.assertEqual(set(parse_qs(urlparse(row["source_url"]).query)), {"bookingResourceId", "selectedDate", "feeGroupId"})


if __name__ == "__main__":
    unittest.main()
