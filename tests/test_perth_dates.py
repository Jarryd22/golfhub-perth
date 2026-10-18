import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from app import qt_golfhub_app as ui
from tests.qt_test_support import cleanup_qt_widgets


class PerthDateTests(unittest.TestCase):
    def test_booking_day_changes_at_perth_midnight(self):
        before = datetime(2026, 10, 16, 15, 59, 59, tzinfo=timezone.utc)
        after = before + timedelta(seconds=1)
        self.assertEqual(ui.perth_today(before), QDate(2026, 10, 16))
        self.assertEqual(ui.perth_today(after), QDate(2026, 10, 17))

    def test_utc_midnight_does_not_change_the_perth_booking_day(self):
        before = datetime(2026, 10, 16, 23, 59, 59, tzinfo=timezone.utc)
        after = before + timedelta(seconds=1)
        for instant in (before, after):
            with self.subTest(instant=instant):
                self.assertEqual(ui.perth_today(instant), QDate(2026, 10, 17))

    def test_ahead_and_behind_local_dates_resolve_to_the_same_perth_day(self):
        for hour, expected in ((12, QDate(2026, 10, 16)), (17, QDate(2026, 10, 17))):
            instant = datetime(2026, 10, 16, hour, tzinfo=timezone.utc)
            for offset in (-12, 0, 14):
                local = instant.astimezone(timezone(timedelta(hours=offset)))
                with self.subTest(hour=hour, offset=offset):
                    self.assertEqual(ui.perth_today(local), expected)

    def test_default_clock_requests_an_explicit_timezone(self):
        instant = datetime(2026, 10, 16, 17, tzinfo=timezone.utc)
        with patch.object(ui, "datetime") as clock:
            clock.now.return_value = instant
            self.assertEqual(ui.perth_today(), QDate(2026, 10, 17))
            clock.now.assert_called_once_with(timezone.utc)


class PerthDateWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls):
        cleanup_qt_widgets()

    def test_startup_window_and_default_selection_use_perth_day(self):
        today = QDate(2032, 12, 31)
        with patch.object(ui, "perth_today", return_value=today, create=True), patch.object(
            ui.GolfHub, "show_initial_cache"
        ):
            window = ui.GolfHub()
            try:
                self.assertEqual(window.date.minimumDate(), today)
                self.assertEqual(window.date.maximumDate(), today.addDays(27))
                self.assertEqual(window.selected_dates(), ["2033-01-01"])
                self.assertTrue(window.date.text().startswith("Tomorrow"))
            finally:
                window.close()

    def test_today_banner_highlight_and_relative_labels_share_perth_day(self):
        today = QDate(2032, 12, 31)
        with patch.object(ui, "perth_today", return_value=today, create=True):
            button = ui.MultiDateButton(today, today.addDays(27), [today])
            popup = ui.MultiDatePopup(today, today.addDays(27), [today.addDays(1)])
            try:
                self.assertIn(today.toString("dddd, d MMMM yyyy").upper(), popup.today_label.text())
                self.assertTrue(popup.calendar.dateTextFormat(today).fontUnderline())
                self.assertTrue(button.text().startswith("Today"))
                button.setDate(today.addDays(1))
                self.assertTrue(button.text().startswith("Tomorrow"))
                button.setDate(today.addDays(2))
                self.assertFalse(button.text().startswith(("Today", "Tomorrow")))
            finally:
                popup.close()
                button.close()


if __name__ == "__main__":
    unittest.main()
