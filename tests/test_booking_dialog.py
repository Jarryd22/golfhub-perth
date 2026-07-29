from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from app.booking_assist import build_booking_assist_plan
from app.booking_dialog import (
    DEFAULT_RELEASE_WAIT_MS,
    BookingAssistDialog,
    interpret_hold_result,
    interpret_release_result,
    is_checkout_url,
    plan_allows_temporary_hold,
)


MICLUB_URL = (
    "https://araluenestategolfcourse.miclub.com.au/guests/bookings/"
    "ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-07-16&feeGroupId=102807"
)

STATIC_TIMESHEET = """
<!doctype html>
<html>
<body>
  <div class="row-time" id="row-178397" data-value="178397">
    <h3>07:00 am</h3>
    <div id="178397_0" class="cell cell-available" onclick="toggle(this)">Available</div>
    <div id="178397_1" class="cell cell-available" onclick="toggle(this)">Available</div>
    <div id="178397_2" class="cell cell-available" onclick="toggle(this)">Available</div>
    <div id="178397_3" class="cell cell-available" onclick="toggle(this)">Available</div>
  </div>
  <button id="bookNowBtn" onclick="linkToCartModal()">Book now</button>
  <div id="detailsModal" style="display:none"></div>
  <script>
    function toggle(cell) {
      if (cell.classList.contains('cell-available')) {
        cell.classList.remove('cell-available');
        cell.classList.add('cell-selected');
      } else if (cell.classList.contains('cell-selected')) {
        cell.classList.remove('cell-selected');
        cell.classList.add('cell-available');
      }
    }
    function linkToCartModal() {
      globalThis.fixtureDetailsOpened = true;
      setTimeout(function () {
        document.getElementById('detailsModal').style.display = 'block';
      }, 80);
    }
  </script>
</body>
</html>
"""


def confirmed_plan(players: int = 3):
    return build_booking_assist_plan(
        source_url=MICLUB_URL,
        tee_time="7:00 am",
        players=players,
        available_spots=4,
        course_name="Araluen",
        temporary_hold_confirmed=True,
    )


class ResultInterpreterTests(unittest.TestCase):
    def test_hold_success_requires_exact_shape_and_player_count(self):
        outcome = interpret_hold_result(
            {"ok": True, "code": "player_details_open", "held": 3.0},
            3,
        )
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.count, 3)

        for value in (
            None,
            {"ok": True, "code": "player_details_open", "held": 2},
            {"ok": True, "code": "unexpected", "held": 3},
            {"ok": False, "code": "not_enough_spots", "held": 1},
        ):
            with self.subTest(value=value):
                self.assertFalse(interpret_hold_result(value, 3).ok)

    def test_known_failure_is_preserved_but_unknown_result_fails_closed(self):
        known = interpret_hold_result(
            {"ok": False, "code": "not_enough_spots", "held": 0, "available": 2},
            3,
        )
        self.assertFalse(known.ok)
        self.assertEqual(known.code, "not_enough_spots")
        self.assertEqual(known.available, 2)
        self.assertEqual(interpret_hold_result({"ok": True}, 3).code, "invalid_hold_result")

    def test_release_uses_returned_wait_and_safe_default(self):
        released = interpret_release_result(
            {
                "ok": True,
                "code": "release_requested",
                "released": 3,
                "remaining": 0,
                "waitBeforeCloseMs": 1750,
            }
        )
        self.assertTrue(released.ok)
        self.assertEqual(released.wait_before_close_ms, 1750)

        invalid = interpret_release_result(None)
        self.assertFalse(invalid.ok)
        self.assertEqual(invalid.wait_before_close_ms, DEFAULT_RELEASE_WAIT_MS)

    def test_checkout_detection_is_path_specific(self):
        self.assertTrue(
            is_checkout_url(
                "https://course.example/guests/bookings/Checkout.msp?bookingId=1"
            )
        )
        self.assertFalse(is_checkout_url("https://course.example/bookings?next=checkout"))

    def test_plan_guard_requires_explicit_confirmation(self):
        self.assertTrue(plan_allows_temporary_hold(confirmed_plan()))
        unconfirmed = build_booking_assist_plan(
            source_url=MICLUB_URL,
            tee_time="7:00 am",
            players=3,
            available_spots=4,
        )
        self.assertFalse(plan_allows_temporary_hold(unconfirmed))


class StaticBookingDialogTests(unittest.TestCase):
    """Exercise Qt WebEngine only against in-memory HTML; no live holds occur."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, predicate, timeout_ms=6000):
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        return False

    def javascript_value(self, dialog, script):
        values = []
        dialog.web_page.runJavaScript(script, values.append)
        self.assertTrue(self.wait_until(lambda: bool(values)))
        return values[0]

    def load_fixture(self, dialog):
        dialog.show()
        dialog.web_view.setHtml(STATIC_TIMESHEET, QUrl(dialog.plan.open_url))

    def test_confirmed_fixture_holds_exact_count_then_close_releases(self):
        dialog = BookingAssistDialog(confirmed_plan(3), auto_load=False)
        assist_events = []
        release_events = []
        dialog.assist_finished.connect(lambda *args: assist_events.append(args))
        dialog.release_finished.connect(lambda *args: release_events.append(args))
        try:
            self.assertTrue(dialog.web_profile.isOffTheRecord())
            self.load_fixture(dialog)
            self.assertTrue(self.wait_until(lambda: bool(assist_events)))
            self.assertEqual(assist_events[-1], (True, "player_details_open", 3))
            self.assertTrue(dialog.hold_active)
            self.assertEqual(
                self.javascript_value(
                    dialog,
                    "document.querySelectorAll('.cell-selected').length",
                ),
                3.0,
            )
            self.assertTrue(
                self.javascript_value(dialog, "globalThis.fixtureDetailsOpened === true")
            )

            # Escape maps to reject(); the override must take the same release
            # path as the visible Release holds & close control.
            dialog.reject()
            self.assertTrue(self.wait_until(lambda: bool(release_events)))
            self.assertEqual(release_events[-1], (True, "release_requested", 3))
            self.assertEqual(
                self.javascript_value(
                    dialog,
                    "document.querySelectorAll('.cell-selected').length",
                ),
                0.0,
            )
            self.assertTrue(self.wait_until(lambda: not dialog.isVisible(), 3000))
        finally:
            if dialog.isVisible():
                dialog._allow_close = True
                dialog.close()

    def test_checkout_navigation_closes_without_rollback(self):
        dialog = BookingAssistDialog(confirmed_plan(2), auto_load=False)
        assist_events = []
        release_events = []
        dialog.assist_finished.connect(lambda *args: assist_events.append(args))
        dialog.release_finished.connect(lambda *args: release_events.append(args))
        try:
            self.load_fixture(dialog)
            self.assertTrue(self.wait_until(lambda: bool(assist_events)))
            self.assertTrue(dialog.hold_active)

            # Emit the same signal QWebEngine emits on real navigation, without
            # requesting any live URL in this isolated test.
            checkout = QUrl(
                "https://araluenestategolfcourse.miclub.com.au/guests/bookings/Checkout.msp"
            )
            dialog.web_view.urlChanged.emit(checkout)
            self.app.processEvents()
            self.assertTrue(dialog.continued_to_checkout)
            self.assertEqual(dialog.status_code, "checkout_reached")

            dialog.request_close()
            self.assertTrue(self.wait_until(lambda: not dialog.isVisible()))
            self.assertEqual(release_events, [])
        finally:
            if dialog.isVisible():
                dialog._allow_close = True
                dialog.close()

    def test_failed_release_keeps_page_open_for_manual_deselection(self):
        dialog = BookingAssistDialog(confirmed_plan(2), auto_load=False)
        dialog.show()
        dialog._release_required = True
        dialog._release_in_progress = True
        dialog._close_after_release = True
        try:
            with patch(
                "app.booking_dialog.QTimer.singleShot",
                side_effect=lambda _delay, callback: callback(),
            ):
                dialog._handle_release_result(
                    {
                        "ok": False,
                        "code": "release_incomplete",
                        "released": 1,
                        "remaining": 1,
                    }
                )
            self.app.processEvents()
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.status_code, "release_not_verified")
            self.assertIn("deselect", dialog.status_message.lower())
        finally:
            dialog._allow_close = True
            dialog.close()

    def test_unconfirmed_plan_never_executes_hold_script(self):
        plan = build_booking_assist_plan(
            source_url=MICLUB_URL,
            tee_time="7:00 am",
            players=2,
            available_spots=4,
        )
        dialog = BookingAssistDialog(plan, auto_load=False)
        try:
            self.load_fixture(dialog)
            self.assertTrue(self.wait_until(lambda: dialog.status_code == "manual_only"))
            self.assertFalse(dialog.hold_active)
            self.assertEqual(
                self.javascript_value(
                    dialog,
                    "document.querySelectorAll('.cell-selected').length",
                ),
                0.0,
            )
        finally:
            dialog.request_close()


if __name__ == "__main__":
    unittest.main()

