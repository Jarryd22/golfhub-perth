from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from app.booking_assist import (
    AssistMode,
    BookingAssistError,
    PreselectionPolicy,
    build_booking_assist_plan,
    inspect_miclub_row,
    sanitise_booking_url,
)


MICLUB_HTML = """
<!doctype html>
<html>
<body>
  <div id="row-178397" class="row row-time am_row" data-value="178397">
    <div class="row-heading"><h3>07:00 am</h3></div>
    <div class="records-wrapper">
      <div id="178397_0" class="cell cell-available" data-value="178397">Available</div>
      <div id="178397_1" class="cell cell-taken" data-value="178397">Taken</div>
      <div id="178397_2" class="cell cell-available" data-value="178397">Available</div>
      <div id="178397_3" class="cell cell-available" data-value="178397">Available</div>
    </div>
  </div>
  <div id="row-178398" class="row row-time am_row" data-value="178398">
    <div class="row-heading"><h3>07:10 AM </h3></div>
    <div class="records-wrapper">
      <div id="178398_0" class="cell cell-selected" data-value="178398">Player Selected</div>
      <div id="178398_1" class="cell cell-available" data-value="178398">Available</div>
      <div id="178398_2" class="cell cell-available" data-value="178398">Available</div>
      <div id="178398_3" class="cell cell-available" data-value="178398">Available</div>
    </div>
  </div>
  <script>
    let minimumBookingLimitJson = JSON.parse('{"178397":2,"178398":1}');
    function selectCell(cell, lockRow) {
      return '/guests/Ajax?doAction=lockCell&rowXIndex=' + cell.attr('id');
    }
    function confirmBooking() { sendCommonUpdate('addToCart', 'cells=example'); }
  </script>
</body>
</html>
"""


class BookingAssistPlanTests(unittest.TestCase):
    def test_miclub_plan_opens_exact_timesheet_but_never_preselects(self):
        plan = build_booking_assist_plan(
            source_url=(
                "https://araluenestategolfcourse.miclub.com.au/guests/bookings/"
                "ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-07-16&feeGroupId=102807"
            ),
            tee_time="7:00 AM",
            players=4,
            available_spots=4,
            course_name="Araluen",
        )

        self.assertEqual(plan.provider, "miclub")
        self.assertEqual(plan.capability.mode, AssistMode.EXACT_TIMESHEET)
        self.assertEqual(plan.capability.preselection_policy, PreselectionPolicy.USER_SELECTS)
        self.assertFalse(plan.automatic_preselection_allowed)
        self.assertTrue(plan.capability.preselection_has_side_effects)
        self.assertEqual(plan.automatic_actions, ("open_public_booking_page",))
        self.assertEqual(plan.stop_before, "Confirm Booking")
        self.assertEqual(plan.tee_time, "07:00 am")
        self.assertEqual(plan.requested_players, 4)

    def test_captcha_and_action_parameters_are_never_replayed(self):
        url = (
            "https://www.wembleygolf.com.au/guests/bookings/ViewPublicTimesheet.msp"
            "?bookingResourceId=3000000&selectedDate=2026-07-23&feeGroupId=102193"
            "&recaptchaResponse=short-lived-token&cells=123_0&rowXIndex=123_0"
        )
        plan = build_booking_assist_plan(
            source_url=url,
            tee_time="12:12 pm",
            players=2,
            available_spots=4,
        )

        query = parse_qs(urlsplit(plan.open_url).query)
        self.assertEqual(query["selectedDate"], ["2026-07-23"])
        self.assertEqual(query["feeGroupId"], ["102193"])
        self.assertNotIn("recaptchaResponse", query)
        self.assertNotIn("cells", query)
        self.assertNotIn("rowXIndex", query)
        self.assertEqual(
            plan.stripped_query_parameters,
            ("recaptchaResponse", "cells", "rowXIndex"),
        )

    def test_quick18_uses_honest_provider_search_fallback(self):
        plan = build_booking_assist_plan(
            source_url="https://hamersley.quick18.com/teetimes/searchmatrix?teedate=20260723",
            tee_time="09:30 am",
            players=3,
            available_spots=4,
        )
        self.assertEqual(plan.provider, "quick18")
        self.assertEqual(plan.capability.mode, AssistMode.PROVIDER_SEARCH)
        self.assertFalse(plan.automatic_preselection_allowed)

    def test_unknown_provider_uses_direct_fallback(self):
        plan = build_booking_assist_plan(
            source_url="https://example-golf.test/bookings/",
            tee_time="1:05 pm",
            players=1,
        )
        self.assertEqual(plan.provider, "direct")
        self.assertEqual(plan.capability.mode, AssistMode.PROVIDER_HOME)
        self.assertEqual(plan.capability.preselection_policy, PreselectionPolicy.UNSUPPORTED)

    def test_player_count_and_availability_are_validated(self):
        kwargs = {
            "source_url": "https://example.test/book",
            "tee_time": "8:00 am",
        }
        for invalid in (0, 5, True, 2.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BookingAssistError):
                    build_booking_assist_plan(players=invalid, **kwargs)

        with self.assertRaisesRegex(BookingAssistError, "2 available"):
            build_booking_assist_plan(players=3, available_spots=2, **kwargs)

    def test_invalid_time_is_rejected(self):
        with self.assertRaises(BookingAssistError):
            build_booking_assist_plan(
                source_url="https://example.test/book",
                tee_time="25:72",
                players=1,
            )

    def test_checkout_ajax_and_credential_urls_are_rejected(self):
        unsafe = (
            "https://example.test/guests/Ajax?doAction=lockCell&rowXIndex=1_0",
            "https://example.test/guests/bookings/Checkout.msp",
            "https://user:password@example.test/book",
        )
        for url in unsafe:
            with self.subTest(url=url):
                with self.assertRaises(BookingAssistError):
                    sanitise_booking_url(url)


class MiClubInspectionTests(unittest.TestCase):
    def test_extracts_target_cell_metadata_without_approving_automation(self):
        target = inspect_miclub_row(MICLUB_HTML, tee_time="7:00 am", players=3)
        self.assertIsNotNone(target)
        assert target is not None

        self.assertEqual(target.row_id, "178397")
        self.assertEqual(target.available_cell_ids, ("178397_0", "178397_2", "178397_3"))
        self.assertEqual(target.selected_cell_ids, ())
        self.assertEqual(target.minimum_booking_limit, 2)
        self.assertTrue(target.enough_available_spots)
        self.assertTrue(target.meets_minimum_booking_limit)
        self.assertTrue(target.technically_selectable)
        self.assertFalse(target.automatic_preselection_safe)
        self.assertIn("lockCell", target.side_effect_endpoint)
        self.assertEqual(target.stop_control, "Confirm Booking")

    def test_minimum_booking_limit_is_respected(self):
        target = inspect_miclub_row(MICLUB_HTML, tee_time="07:00 AM", players=1)
        self.assertIsNotNone(target)
        assert target is not None
        self.assertFalse(target.meets_minimum_booking_limit)
        self.assertFalse(target.technically_selectable)

    def test_selected_cells_are_read_but_not_counted_as_freely_available(self):
        target = inspect_miclub_row(MICLUB_HTML, tee_time="7:10 am", players=3)
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target.selected_cell_ids, ("178398_0",))
        self.assertEqual(target.available_cell_ids, ("178398_1", "178398_2", "178398_3"))
        self.assertTrue(target.technically_selectable)
        self.assertFalse(target.automatic_preselection_safe)

    def test_missing_time_returns_none(self):
        self.assertIsNone(inspect_miclub_row(MICLUB_HTML, tee_time="8:00 am", players=2))

    def test_inspection_validates_players(self):
        with self.assertRaises(BookingAssistError):
            inspect_miclub_row(MICLUB_HTML, tee_time="7:00 am", players=8)


if __name__ == "__main__":
    unittest.main()

