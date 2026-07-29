from __future__ import annotations

import unittest

from app.booking_assist import BookingAssistError, build_booking_assist_plan


class ConfirmedHoldGuardTests(unittest.TestCase):
    def test_generated_script_respects_miclub_minimum_limit_state(self):
        plan = build_booking_assist_plan(
            source_url=(
                "https://araluenestategolfcourse.miclub.com.au/guests/bookings/"
                "ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-07-16&feeGroupId=102807"
            ),
            tee_time="7:00 am",
            players=1,
            available_spots=4,
            temporary_hold_confirmed=True,
        )
        script = plan.temporary_hold_script or ""
        self.assertIn('document.getElementById("bookNowBtn")', script)
        self.assertIn("bookButton.click()", script)
        self.assertIn("bookButton.disabled", script)
        self.assertIn("minimum_booking_limit_not_met", script)
        self.assertIn("releaseSelected()", script)

    def test_confirmed_hold_requires_resource_date_and_product_ids(self):
        incomplete_urls = (
            "https://example.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp",
            "https://example.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp?bookingResourceId=1",
            (
                "https://example.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp"
                "?bookingResourceId=1&selectedDate=2026-07-16"
            ),
        )
        for url in incomplete_urls:
            with self.subTest(url=url):
                with self.assertRaisesRegex(BookingAssistError, "resource, date, and product"):
                    build_booking_assist_plan(
                        source_url=url,
                        tee_time="7:00 am",
                        players=2,
                        available_spots=4,
                        temporary_hold_confirmed=True,
                    )

    def test_failure_cleanup_removes_golfhub_hold_marker(self):
        plan = build_booking_assist_plan(
            source_url=(
                "https://example.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp"
                "?bookingResourceId=1&selectedDate=2026-07-16&feeGroupId=2"
            ),
            tee_time="7:00 am",
            players=2,
            available_spots=4,
            temporary_hold_confirmed=True,
        )
        self.assertIn(
            "delete globalThis.__golfHubTemporaryHold",
            plan.temporary_hold_script or "",
        )


if __name__ == "__main__":
    unittest.main()

