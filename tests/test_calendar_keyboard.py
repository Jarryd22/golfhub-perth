"""Real Qt input regressions for keyboard multi-date selection."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView, QVBoxLayout, QWidget

from app.qt_golfhub_app import MultiDateButton, MultiDatePopup


class CalendarKeyboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.minimum = QDate(2026, 7, 15)
        self.host = QWidget()
        layout = QVBoxLayout(self.host)
        self.button = MultiDateButton(self.minimum, self.minimum.addDays(27), [self.minimum])
        layout.addWidget(self.button)
        self.host.show()
        self.button.setFocus()
        self.app.processEvents()
        QTest.keyClick(self.button, Qt.Key_Space)
        self.app.processEvents()
        self.popup = self.button.picker_popup()
        self.view = self.popup.calendar.findChild(QTableView, "qt_calendar_calendarview")

    def tearDown(self):
        self.host.close()
        self.app.processEvents()

    def test_arrow_navigation_alone_does_not_change_chosen_dates(self):
        QTest.keyClick(self.view, Qt.Key_Right)
        self.assertEqual(self.popup.calendar.selectedDate(), self.minimum.addDays(1))
        self.assertEqual(self.popup.selected_dates(), [self.minimum])

    def test_numeric_keys_cannot_start_a_delayed_date_edit(self):
        QTest.keyClick(self.view, Qt.Key_Right)
        focused_date = self.popup.calendar.selectedDate()
        QTest.keyClicks(self.view, "20")
        QTest.keyClick(self.view, Qt.Key_Return)
        QTest.qWait(self.popup.calendar.dateEditAcceptDelay() + 20)
        self.assertEqual(self.popup.calendar.selectedDate(), focused_date)
        self.assertEqual(self.popup.selected_dates(), [self.minimum, focused_date])

    def test_return_enter_and_space_toggle_once_and_keep_last_date(self):
        for key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            with self.subTest(key=key):
                self.popup.calendar.setSelectedDate(self.minimum.addDays(2))
                QTest.keyClick(self.view, key)
                self.assertEqual(self.popup.selected_dates(), [self.minimum, self.minimum.addDays(2)])
                self.assertEqual(self.popup.count_label.text(), "2 dates selected")
                self.assertTrue(self.popup.isVisible())
                QTest.keyClick(self.view, key)
                self.assertEqual(self.popup.selected_dates(), [self.minimum])
                self.popup.calendar.setSelectedDate(self.minimum)
                QTest.keyClick(self.view, key)
                self.assertEqual(self.popup.selected_dates(), [self.minimum])

    def test_keyboard_navigation_crosses_month_and_respects_bounds(self):
        self.popup.calendar.setSelectedDate(QDate(2026, 7, 31))
        QTest.keyClick(self.view, Qt.Key_Right)
        QTest.keyClick(self.view, Qt.Key_Return)
        self.assertEqual(self.popup.selected_dates(), [self.minimum, QDate(2026, 8, 1)])
        self.assertEqual(self.popup.month_label.text(), "August 2026")
        self.popup.calendar.setSelectedDate(self.minimum.addDays(27))
        QTest.keyClick(self.view, Qt.Key_Right)
        self.assertEqual(self.popup.calendar.selectedDate(), self.minimum.addDays(27))
        QTest.keyClick(self.view, Qt.Key_Return)
        self.assertEqual(self.popup.selected_dates()[-1], self.minimum.addDays(27))
        self.popup.calendar.setSelectedDate(self.minimum)
        QTest.keyClick(self.view, Qt.Key_Left)
        self.assertEqual(self.popup.calendar.selectedDate(), self.minimum)

    def test_held_activation_key_does_not_toggle_repeatedly(self):
        self.popup.calendar.setSelectedDate(self.minimum.addDays(1))
        QTest.keyPress(self.view, Qt.Key_Space)
        repeat = QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier, " ", True, 1)
        QApplication.sendEvent(self.view, repeat)
        QTest.keyRelease(self.view, Qt.Key_Space)
        self.assertEqual(self.popup.selected_dates(), [self.minimum, self.minimum.addDays(1)])

    def test_keyboard_can_apply_selected_dates_by_tab_and_space(self):
        QTest.keyClick(self.view, Qt.Key_Right)
        QTest.keyClick(self.view, Qt.Key_Return)
        for _ in range(10):
            if self.popup.done_button.hasFocus():
                break
            QTest.keyClick(QApplication.focusWidget(), Qt.Key_Tab)
        self.assertTrue(self.popup.done_button.hasFocus(), "Apply must be reachable by Tab")
        QTest.keyClick(self.popup.done_button, Qt.Key_Space)
        self.app.processEvents()
        self.assertEqual(self.button.selected_qdates(), [self.minimum, self.minimum.addDays(1)])

    def test_escape_discards_pending_keyboard_selection(self):
        QTest.keyClick(self.view, Qt.Key_Right)
        QTest.keyClick(self.view, Qt.Key_Return)
        self.assertEqual(len(self.popup.selected_dates()), 2)
        QTest.keyClick(self.view, Qt.Key_Escape)
        self.app.processEvents()
        self.assertEqual(self.button.selected_qdates(), [self.minimum])
        self.assertIsNone(self.button.picker_popup())

    def test_mouse_click_then_double_click_does_not_add_a_second_toggle(self):
        target = next(
            index for row in range(1, self.view.model().rowCount())
            for col in range(self.view.model().columnCount())
            if str((index := self.view.model().index(row, col)).data()) == "25"
        )
        position = self.view.visualRect(target).center()
        with patch.object(self.popup, "refresh_highlights", wraps=self.popup.refresh_highlights) as refresh:
            QTest.mouseClick(self.view.viewport(), Qt.LeftButton, pos=position)
            QTest.mouseDClick(self.view.viewport(), Qt.LeftButton, pos=position)
            QTest.mouseRelease(self.view.viewport(), Qt.LeftButton, pos=position)
            self.app.processEvents()
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(self.popup.selected_dates(), [self.minimum, QDate(2026, 7, 25)])


if __name__ == "__main__":
    unittest.main()
