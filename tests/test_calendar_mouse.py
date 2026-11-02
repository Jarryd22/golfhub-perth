"""Offline actual-pointer regressions for calendar cell/date correspondence."""
import os
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-calendar-mouse-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView

from app import qt_golfhub_app as ui
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class CalendarMouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                       "socket.getaddrinfo", "webbrowser.open", "app.qt_golfhub_app.CacheWorker",
                       "app.qt_golfhub_app.ScanWorker"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline calendar test")))
        self.callback_errors = []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *args: self.callback_errors.append(str(args[1]))))

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [], "Qt callbacks must not raise")

    def settle(self):
        for _ in range(8):
            self.app.processEvents()

    def popup(self, minimum, maximum, selected):
        popup = ui.MultiDatePopup(minimum, maximum, selected)
        popup.setFixedSize(640, 600)
        popup.show()
        self.settle()
        view = popup.calendar.findChild(QTableView, "qt_calendar_calendarview")
        self.assertIsNotNone(view)
        return popup, view

    def click_date(self, popup, view, target):
        # Obtain the actual Qt cell, independently of GolfHub's hit-test formula.
        # Focusing a date does not add it to the popup's chosen-date set.
        popup.calendar.setSelectedDate(target)
        self.settle()
        index = view.currentIndex()
        self.assertEqual(popup.calendar.selectedDate(), target)
        self.assertEqual(index.data(), target.day())
        self.assertTrue(index.flags() & Qt.ItemIsEnabled)
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
        self.settle()

    def test_monday_month_last_week_mouse_selects_and_removes_dates(self):
        for year, month in ((2027, 2), (2032, 11), (2032, 3)):
            first = QDate(year, month, 1)
            last = QDate(year, month, first.daysInMonth())
            minimum = last.addDays(-27)
            self.assertEqual(first.dayOfWeek(), 1)
            for offset in range(6, -1, -1):
                target = last.addDays(-offset)
                with self.subTest(date=target.toString("yyyy-MM-dd")):
                    popup, view = self.popup(minimum, last, [minimum])
                    try:
                        self.click_date(popup, view, target)
                        self.assertEqual(popup.selected_dates(), [minimum, target])
                        self.click_date(popup, view, target)
                        self.assertEqual(popup.selected_dates(), [minimum])
                    finally:
                        cleanup_qt_widgets()

    def test_monday_preceding_padding_does_not_navigate_or_toggle(self):
        for action in (QTest.mouseClick, QTest.mouseDClick):
            with self.subTest(action=action.__name__):
                minimum, selected = QDate(2032, 2, 23), QDate(2032, 3, 1)
                popup, view = self.popup(minimum, minimum.addDays(27), [selected])
                try:
                    index = view.model().index(1, 0)
                    self.assertEqual(index.data(), 23)  # Qt's preceding Monday.
                    self.assertTrue(index.flags() & Qt.ItemIsEnabled)  # In range, but painted over.
                    action(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
                    self.settle()
                    self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2032, 3))
                    self.assertEqual(popup.selected_dates(), [selected])
                finally:
                    cleanup_qt_widgets()

    def test_monday_following_padding_does_not_navigate_or_toggle(self):
        for action in (QTest.mouseClick, QTest.mouseDClick):
            with self.subTest(action=action.__name__):
                minimum = QDate(2027, 2, 15)
                popup, view = self.popup(minimum, minimum.addDays(27), [minimum])
                try:
                    index = view.model().index(view.model().rowCount() - 1, 0)
                    self.assertEqual(index.data(), 1)  # Following Monday, March 1.
                    self.assertTrue(index.flags() & Qt.ItemIsEnabled)
                    action(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
                    self.settle()
                    self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2027, 2))
                    self.assertEqual(popup.selected_dates(), [minimum])
                finally:
                    cleanup_qt_widgets()

    def test_non_monday_month_last_date_remains_mouse_selectable(self):
        for month in (2, 6, 9, 4, 1, 5):
            first = QDate(2033, month, 1)
            last = QDate(2033, month, first.daysInMonth())
            minimum = last.addDays(-27)
            with self.subTest(month=month, first_weekday=first.dayOfWeek()):
                self.assertNotEqual(first.dayOfWeek(), 1)
                popup, view = self.popup(minimum, last, [minimum])
                try:
                    self.click_date(popup, view, last)
                    self.assertEqual(popup.selected_dates(), [minimum, last])
                finally:
                    cleanup_qt_widgets()

    def test_disabled_dates_outside_bounds_remain_unselected(self):
        minimum, maximum, selected = QDate(2032, 3, 5), QDate(2032, 3, 20), QDate(2032, 3, 10)
        popup, view = self.popup(minimum, maximum, [selected])
        model = view.model()
        for day in (4, 21):
            with self.subTest(day=day):
                index = next(model.index(row, column) for row in range(1, model.rowCount())
                             for column in range(model.columnCount()) if model.index(row, column).data() == day)
                self.assertFalse(index.flags() & Qt.ItemIsEnabled)
                QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
                self.settle()
                self.assertEqual(popup.selected_dates(), [selected])
                self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2032, 3))

    def test_weekday_header_click_does_not_change_dates(self):
        selected = QDate(2027, 2, 1)
        popup, view = self.popup(selected, selected.addDays(27), [selected])
        index = view.model().index(0, 2)
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
        self.settle()
        self.assertEqual(popup.selected_dates(), [selected])
        self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2027, 2))

    def test_next_month_navigation_then_last_week_mouse_selection(self):
        minimum, target = QDate(2027, 1, 30), QDate(2027, 2, 25)
        popup, view = self.popup(minimum, minimum.addDays(27), [minimum])
        QTest.mouseClick(popup.next_month_button, Qt.LeftButton)
        self.settle()
        self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2027, 2))
        self.click_date(popup, view, target)
        self.assertEqual(popup.selected_dates(), [minimum, target])
        self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2027, 2))

    def test_actual_app_popup_applies_last_date_to_submitted_search(self):
        today, target = QDate(2027, 2, 1), QDate(2027, 2, 28)
        self.enterContext(patch.object(ui, "perth_today", return_value=today))
        with patch.object(ui.GolfHub, "show_initial_cache"):
            window = ui.GolfHub()
        window._stop_deferred_timers()
        window.resize(980, 640)
        window.date.setDate(today)
        window.show()
        self.settle()
        QTest.mouseClick(window.date, Qt.LeftButton)
        self.settle()
        popup = window.date.picker_popup()
        view = popup.calendar.findChild(QTableView, "qt_calendar_calendarview")
        self.click_date(popup, view, target)
        self.assertEqual(popup.selected_dates(), [today, target])
        QTest.mouseClick(popup.done_button, Qt.LeftButton)
        self.settle()
        self.assertEqual(window.selected_dates(), ["2027-02-01", "2027-02-28"])
        self.assertFalse(window.live_button.isEnabled())
        with patch.object(window, "_start_cache_search") as launch:
            QTest.mouseClick(window.search_button, Qt.LeftButton)
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[0]["dates"], ["2027-02-01", "2027-02-28"])
        self.assertEqual(launch.call_args.args[0]["date"], "2027-02-01")


if __name__ == "__main__":
    unittest.main()
