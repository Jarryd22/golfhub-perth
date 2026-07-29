from __future__ import annotations

import unittest

from app.booking_assist import BookingAssistError, build_booking_assist_plan


MICLUB_URL = (
    "https://araluenestategolfcourse.miclub.com.au/guests/bookings/"
    "ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-07-16&feeGroupId=102807"
)


class ConfirmedTemporaryHoldTests(unittest.TestCase):
    def build_plan(self, **overrides):
        values = {
            "source_url": MICLUB_URL,
            "tee_time": "7:00 am",
            "players": 3,
            "available_spots": 4,
            "course_name": "Araluen",
        }
        values.update(overrides)
        return build_booking_assist_plan(**values)

    def test_default_plan_remains_open_only(self):
        plan = self.build_plan()
        self.assertFalse(plan.temporary_hold_confirmed)
        self.assertFalse(plan.automatic_preselection_allowed)
        self.assertIsNone(plan.temporary_hold_script)
        self.assertIsNone(plan.rollback_script)
        self.assertEqual(plan.rollback_guidance, ())
        self.assertEqual(plan.automatic_actions, ("open_public_booking_page",))

    def test_explicit_confirmation_enables_exact_count_and_details_only(self):
        plan = self.build_plan(temporary_hold_confirmed=True)
        self.assertTrue(plan.temporary_hold_confirmed)
        self.assertTrue(plan.automatic_preselection_allowed)
        self.assertTrue(plan.capability.confirmed_temporary_hold_supported)
        self.assertIsNotNone(plan.temporary_hold_script)
        self.assertIsNotNone(plan.rollback_script)
        self.assertEqual(
            plan.automatic_actions,
            (
                "open_public_booking_page",
                "run_user_confirmed_temporary_hold_script",
                "open_player_details_only",
            ),
        )

        script = plan.temporary_hold_script or ""
        self.assertIn('"teeTime":"07:00 am"', script)
        self.assertIn('"players":3', script)
        self.assertIn('querySelectorAll("div.row-time")', script)
        self.assertIn('querySelectorAll("div.cell.cell-available")', script)
        self.assertIn('document.querySelectorAll(".cell-selected")', script)
        self.assertIn("available.slice(0, intent.players)", script)
        self.assertIn("cell.click()", script)
        self.assertIn("bookButton.click()", script)
        self.assertIn("releaseSelected()", script)
        self.assertIn("tee_time_not_unique", script)
        self.assertIn("not_enough_spots", script)
        self.assertIn("spot_changed", script)

    def test_hold_and_release_scripts_exclude_irreversible_actions(self):
        plan = self.build_plan(temporary_hold_confirmed=True)
        combined = f"{plan.temporary_hold_script}\n{plan.rollback_script}".lower()
        forbidden = (
            "confirmbooking",
            "sendcommonupdate",
            "addtocart",
            "checkout.msp",
            "recaptcha",
            "g-recaptcha",
            "h-captcha",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_release_script_only_targets_cells_recorded_by_golfhub(self):
        plan = self.build_plan(temporary_hold_confirmed=True)
        script = plan.rollback_script or ""
        self.assertIn("__golfHubTemporaryHold", script)
        self.assertIn("state.selectedCellIds.slice().reverse()", script)
        self.assertIn('classList.contains("cell-selected")', script)
        self.assertIn("cell.click()", script)
        self.assertIn('modal.modal("hide")', script)
        self.assertIn("waitBeforeCloseMs:1500", script)
        self.assertGreaterEqual(len(plan.rollback_guidance), 2)
        self.assertTrue(any("1.5 seconds" in line for line in plan.rollback_guidance))

    def test_confirmation_must_be_an_actual_boolean(self):
        for value in (1, "yes", object()):
            with self.subTest(value=value):
                with self.assertRaisesRegex(BookingAssistError, "must be a boolean"):
                    self.build_plan(temporary_hold_confirmed=value)

    def test_confirmed_assist_rejects_unsupported_provider(self):
        with self.assertRaisesRegex(BookingAssistError, "not supported for quick18"):
            self.build_plan(
                source_url="https://hamersley.quick18.com/teetimes/searchmatrix?teedate=20260716",
                provider="quick18",
                temporary_hold_confirmed=True,
            )

    def test_confirmed_assist_requires_an_exact_timesheet(self):
        with self.assertRaisesRegex(BookingAssistError, "exact public timesheet"):
            self.build_plan(
                source_url=(
                    "https://www.wembleygolf.com.au/guests/bookings/"
                    "ViewPublicCalendar.msp?bookingResourceId=3000000&selectedDate=2026-07-23"
                ),
                temporary_hold_confirmed=True,
            )


if __name__ == "__main__":
    unittest.main()

