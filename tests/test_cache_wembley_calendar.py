"""Calendar cases modeled on Wembley's public desktop/mobile markup."""

import unittest
from datetime import datetime, timezone

from app import golfhub_core as core


class WembleyCalendarDateTests(unittest.TestCase):
    now = datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc)
    products = {
        "18": (("102184", "OLD Course 18 Holes"), ("102193", "TUART Course 18H")),
        "9": (("102211", "OLD Course 9 Holes"), ("102202", "TUART Course 9H")),
    }
    empty_calendar = """
        <script>var publicCaptchaEnabled = true;</script>
        <div class="calendar"><p>No rows meeting selected criteria</p></div>
    """

    @classmethod
    def setUpClass(cls):
        cls.site = next(site for site in core.load_sites(core.DATA_DIR / core.CONFIG_FILE) if site.name == "Wembley")

    def full_calendar(self, header, holes="18"):
        return f'<div class="cell-heading"><p>{header}</p></div>' + "".join(
            f'<div class="row feeGroupRow" data-feeid="{fee_id}"><h3>{label}</h3>'
            '<div class="cell cell-na" data-date="0">Timesheet Full</div></div>'
            for fee_id, label in self.products[holes]
        )

    def result(self, html, date_str, holes="18", now=None):
        return core.fetch_wembley_calendar_result(
            self.site, date_str, holes, None, calendar_html=html,
            now=self.now if now is None else now,
        )

    def test_live_abbreviated_headings_preserve_full_rounds(self):
        for date_str, header, holes in (
            ("2026-10-10", "10 Oct", "18"),
            ("2026-10-10", "10 Oct", "9"),
            ("2026-10-11", "11 Oct", "18"),
            ("2026-10-07", "07 Oct", "18"),
            ("2026-10-08", "8 October", "9"),
            ("2026-10-08", "08&nbsp;<span>Oct</span>", "18"),
        ):
            with self.subTest(date=date_str, holes=holes, header=header):
                result = self.result(self.full_calendar(header, holes), date_str, holes)
                self.assertEqual(result["calendar_availability"], "full")
                self.assertEqual(result["calendar_courses"], [label for _, label in self.products[holes]])
                self.assertIsNone(result["error"])
                self.assertNotIn("calendar_error_kind", result)

    def test_empty_mobile_calendar_outside_horizon_is_unreleased_for_both_rounds(self):
        for holes in self.products:
            with self.subTest(holes=holes):
                result = self.result(self.empty_calendar, "2026-10-18", holes)
                self.assertEqual(result["calendar_availability"], "unreleased")
                self.assertEqual(result["calendar_courses"], [])
                self.assertIsNone(result["error"])
                self.assertNotIn("calendar_error_kind", result)

    def test_perth_six_am_boundary_uses_aware_clock(self):
        # Oct 17 opens Oct 7 at 06:00 Perth = Oct 6 at 22:00 UTC.
        for now, expected in (
            (datetime(2026, 10, 6, 21, 59, 59, tzinfo=timezone.utc), "unreleased"),
            (datetime(2026, 10, 6, 22, 0, tzinfo=timezone.utc), "unknown"),
            (datetime(2026, 10, 6, 22, 0, 1, tzinfo=timezone.utc), "unknown"),
        ):
            with self.subTest(now=now):
                result = self.result(self.empty_calendar, "2026-10-17", now=now)
                self.assertEqual(result["calendar_availability"], expected)

    def test_missing_or_wrong_date_inside_window_is_unknown(self):
        for header in ("", "09 Oct", "10 Sep"):
            with self.subTest(header=header):
                result = self.result(self.full_calendar(header), "2026-10-10")
                self.assertEqual(result["calendar_availability"], "unknown")
                self.assertEqual(result["calendar_error_kind"], "products_missing")

    def test_empty_or_error_page_is_not_assumed_unreleased(self):
        for html in ("", "<h1>Access denied</h1>", "<p>Service unavailable</p>"):
            with self.subTest(html=html):
                result = self.result(html, "2026-10-18")
                self.assertEqual(result["calendar_availability"], "unknown")
                self.assertEqual(result["calendar_error_kind"], "products_missing")

    def test_within_window_empty_calendar_and_missing_round_remain_unknown(self):
        for html in (self.empty_calendar, self.full_calendar("10 Oct", "9")):
            with self.subTest(html=html):
                result = self.result(html, "2026-10-10")
                self.assertEqual(result["calendar_availability"], "unknown")
                self.assertEqual(result["calendar_error_kind"], "products_missing")

    def test_partial_products_do_not_establish_full(self):
        html = self.full_calendar("10 Oct").split('<div class="row feeGroupRow" data-feeid="102193">')[0]
        result = self.result(html, "2026-10-10")
        self.assertEqual(result["calendar_availability"], "unknown")
        self.assertEqual(result["calendar_error_kind"], "products_missing")

    def test_official_full_message_with_no_bookings_suffix_is_full(self):
        for message in ("Timesheet Full - No Bookings Available", "Timesheet Full-No Bookings Available"):
            with self.subTest(message=message):
                html = self.full_calendar("10 Oct").replace("Timesheet Full", message)
                self.assertEqual(self.result(html, "2026-10-10")["calendar_availability"], "full")

    def test_requested_heading_and_product_names_alone_do_not_establish_full(self):
        for cell in ("", '<div class="cell" data-date="0">Temporarily unavailable</div>'):
            with self.subTest(cell=cell):
                html = self.full_calendar("10 Oct").replace(
                    '<div class="cell cell-na" data-date="0">Timesheet Full</div>', cell,
                )
                self.assertEqual(self.result(html, "2026-10-10")["calendar_availability"], "unknown")

    def test_full_marker_must_belong_to_requested_day_in_every_product(self):
        headings = '<div class="cell-heading"><p>09 Oct</p></div><div class="cell-heading"><p>10 Oct</p></div>'
        html = headings + "".join(
            f'<div class="row feeGroupRow" data-feeid="{fee}"><h3>{label}</h3>'
            '<div class="cell cell-na" data-date="0">Timesheet Full</div>'
            '<div class="cell cell-na" data-date="1">Temporarily unavailable</div></div>'
            for fee, label in self.products["18"]
        )
        self.assertEqual(self.result(html, "2026-10-09")["calendar_availability"], "full")
        self.assertEqual(self.result(html, "2026-10-10")["calendar_availability"], "unknown")
        full_html = html.replace("Temporarily unavailable", "Timesheet <span>Full</span>")
        self.assertEqual(self.result(full_html, "2026-10-10")["calendar_availability"], "full")

    def test_explicit_heading_index_maps_selected_product_cells(self):
        html = self.full_calendar("10 Oct").replace(
            '<div class="cell-heading">', '<div class="cell-heading" data-date="3">',
        )
        self.assertEqual(self.result(html, "2026-10-10")["calendar_availability"], "unknown")
        html = html.replace('data-date="0"', 'data-date="3"')
        self.assertEqual(self.result(html, "2026-10-10")["calendar_availability"], "full")

    def test_unrecognized_heading_cannot_shift_ordinal_date_mapping(self):
        html = '<div class="cell-heading"><p>9 ???</p></div><div class="cell-heading"><p>10 Oct</p></div>' + "".join(
            f'<div class="row feeGroupRow" data-feeid="{fee}"><h3>{label}</h3>'
            '<div class="cell cell-na" data-date="0">Timesheet Full</div>'
            '<div class="cell cell-na" data-date="1">Temporarily unavailable</div></div>'
            for fee, label in self.products["18"]
        )
        self.assertEqual(self.result(html, "2026-10-10")["calendar_availability"], "unknown")
        explicit = html.replace('<div class="cell-heading"><p>10 Oct', '<div class="cell-heading" data-date="1"><p>10 Oct')
        self.assertEqual(self.result(explicit, "2026-10-10")["calendar_availability"], "unknown")
        explicit_full = explicit.replace("Temporarily unavailable", "Timesheet Full")
        self.assertEqual(self.result(explicit_full, "2026-10-10")["calendar_availability"], "full")

    def test_before_release_explicit_not_yet_open_is_unreleased(self):
        html = self.full_calendar("18 Oct").replace("Timesheet Full", "Not Yet Open")
        self.assertEqual(self.result(html, "2026-10-18")["calendar_availability"], "unreleased")
        unknown_html = html.replace("Not Yet Open", "Temporarily unavailable")
        self.assertEqual(self.result(unknown_html, "2026-10-18")["calendar_availability"], "unknown")

    def test_duplicate_date_headers_or_product_cells_are_ambiguous(self):
        html = self.full_calendar("10 Oct")
        duplicate_header = '<div class="cell-heading"><p>10 Oct</p></div>' + html
        self.assertEqual(self.result(duplicate_header, "2026-10-10")["calendar_availability"], "unknown")
        cell = '<div class="cell cell-na" data-date="0">Timesheet Full</div>'
        duplicate_cell = html.replace(cell, cell + cell)
        self.assertEqual(self.result(duplicate_cell, "2026-10-10")["calendar_availability"], "unknown")

    def test_month_and_year_rollover_use_release_date(self):
        now = datetime(2026, 12, 31, 22, 0, tzinfo=timezone.utc)  # Jan 1, 06:00 Perth.
        self.assertFalse(core._wembley_date_is_unreleased("2027-01-11", now))
        self.assertTrue(core._wembley_date_is_unreleased("2027-01-12", now))

    def test_naive_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "aware datetime"):
            self.result(self.empty_calendar, "2026-10-18", now=datetime(2026, 10, 7))


if __name__ == "__main__":
    unittest.main()
