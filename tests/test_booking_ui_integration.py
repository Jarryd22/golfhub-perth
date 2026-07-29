import os
import unittest
from unittest.mock import MagicMock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PySide6.QtWidgets import QApplication, QPushButton

from app.qt_golfhub_app import GolfHub, ResultCard


MICLUB_URL = (
    "https://araluenestategolfcourse.miclub.com.au/guests/bookings/"
    "ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-07-16&feeGroupId=102807"
)


class BookingUIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self, players=4):
        with patch.object(GolfHub, "show_initial_cache"):
            window = GolfHub()
        window.context["players"] = players
        return window

    @staticmethod
    def result_and_row(url=MICLUB_URL):
        row = {"time": "07:00 am", "minutes": 420, "spots": 4, "source_url": url}
        result = {
            "site_name": "Araluen",
            "url": url,
            "hole_label": "18 holes",
            "decorated_rows": [row],
            "weather": None,
            "error": None,
        }
        return result, row

    def test_selected_players_builds_confirmed_plan_and_opens_safe_dialog(self):
        window = self.make_window(players=4)
        fake_dialog = MagicMock()
        fake_dialog.isVisible.return_value = False
        result, row = self.result_and_row()
        try:
            with (
                patch.object(window, "_booking_choice", return_value="hold"),
                patch("app.qt_golfhub_app.BookingAssistDialog", return_value=fake_dialog) as dialog_type,
                patch("app.qt_golfhub_app.webbrowser.open") as browser_open,
            ):
                window.open_tee_time(result, row)

            plan = dialog_type.call_args.args[0]
            self.assertEqual(plan.requested_players, 4)
            self.assertTrue(plan.temporary_hold_confirmed)
            self.assertTrue(plan.automatic_preselection_allowed)
            self.assertIn("player-details", " ".join(plan.user_instructions))
            fake_dialog.show.assert_called_once()
            browser_open.assert_not_called()
        finally:
            window._booking_dialogs.clear()
            window.close()

    def test_manual_choice_opens_provider_without_any_hold(self):
        window = self.make_window(players=3)
        result, row = self.result_and_row()
        try:
            with (
                patch.object(window, "_booking_choice", return_value="manual"),
                patch("app.qt_golfhub_app.BookingAssistDialog") as dialog_type,
                patch("app.qt_golfhub_app.webbrowser.open") as browser_open,
            ):
                window.open_tee_time(result, row)
            browser_open.assert_called_once_with(MICLUB_URL)
            dialog_type.assert_not_called()
        finally:
            window.close()

    def test_cancel_does_not_open_or_hold_anything(self):
        window = self.make_window(players=2)
        result, row = self.result_and_row()
        try:
            with (
                patch.object(window, "_booking_choice", return_value="cancel"),
                patch("app.qt_golfhub_app.BookingAssistDialog") as dialog_type,
                patch("app.qt_golfhub_app.webbrowser.open") as browser_open,
            ):
                window.open_tee_time(result, row)
            browser_open.assert_not_called()
            dialog_type.assert_not_called()
        finally:
            window.close()

    def test_any_players_keeps_simple_official_link_behaviour(self):
        window = self.make_window(players=None)
        result, row = self.result_and_row()
        try:
            with (
                patch("app.qt_golfhub_app.build_booking_assist_plan") as builder,
                patch("app.qt_golfhub_app.webbrowser.open") as browser_open,
            ):
                window.open_tee_time(result, row)
            browser_open.assert_called_once_with(MICLUB_URL)
            builder.assert_not_called()
        finally:
            window.close()

    def test_unsupported_provider_explains_manual_player_selection(self):
        quick18 = "https://bookings.quick18.com/teetimes/searchmatrix?date=2026-07-16"
        window = self.make_window(players=4)
        result, row = self.result_and_row(quick18)
        try:
            with (
                patch("app.qt_golfhub_app.QMessageBox.information") as information,
                patch("app.qt_golfhub_app.webbrowser.open") as browser_open,
            ):
                window.open_tee_time(result, row)
            information.assert_called_once()
            self.assertIn("does not offer a verified", information.call_args.args[2])
            browser_open.assert_called_once()
        finally:
            window.close()

    def test_book_button_passes_the_exact_course_and_row_to_handler(self):
        result, row = self.result_and_row()
        calls = []
        card = ResultCard(result, [row], lambda course, tee: calls.append((course, tee)))
        try:
            book = next(button for button in card.findChildren(QPushButton) if button.text() == "BOOK")
            book.click()
            self.assertEqual(calls, [(result, row)])
        finally:
            card.deleteLater()


if __name__ == "__main__":
    unittest.main()

