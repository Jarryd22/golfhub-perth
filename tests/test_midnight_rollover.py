"""Offline fake-clock checks for a desktop left open across Perth midnight.

These exercise source widgets and submitted contexts, not installed clients.
No provider request, browser handoff, or native worker runs in this module.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QEvent, QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QApplication, QPushButton

from app import qt_golfhub_app as ui
from tests.qt_test_support import cleanup_qt_widgets


class MidnightRolloverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.addCleanup(patch.stopall)
        self.now = datetime(2032, 12, 31, 15, 59, 59, tzinfo=timezone.utc)
        clock = patch.object(ui, "datetime").start()
        clock.now.side_effect = lambda tz: self.now.astimezone(tz)
        patch("socket.create_connection", side_effect=AssertionError("Offline test")).start()
        patch("socket.socket.connect", side_effect=AssertionError("Offline test")).start()
        self.browser = patch.object(ui.webbrowser, "open", side_effect=AssertionError("Offline test")).start()
        self.callback_errors = []
        patch.object(sys, "excepthook", lambda *args: self.callback_errors.append(args)).start()
        self.window = self.make_window()

    def make_window(self):
        with patch.object(ui.GolfHub, "show_initial_cache"):
            window = ui.GolfHub()
        window._initial_cache_timer.stop()
        window._cache_search_timer.stop()
        return window

    def tearDown(self):
        # Fake live-worker observations below never allocate native objects.
        self.window.scan_thread = None
        self.window.scan_worker = None
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [])
        self.browser.assert_not_called()

    def midnight(self):
        self.now += timedelta(seconds=1)

    def assert_window(self, today, selected):
        self.assertEqual(self.window.date.minimumDate(), today)
        self.assertEqual(self.window.date.maximumDate(), today.addDays(27))
        self.assertEqual(self.window.date.selected_qdates(), selected)

    def open_popup(self):
        self.window.date.open_picker()
        return self.window.date.picker_popup()

    @staticmethod
    def choose(popup, value):
        popup.calendar.setSelectedDate(value)
        popup.toggle_date(value)

    def test_new_cache_search_replaces_expired_selection_with_today(self):
        self.window.date.setDate(QDate(2032, 12, 31))
        self.midnight()
        with patch.object(self.window, "_start_cache_search") as launch:
            self.window.search_cache()
        self.assertEqual(launch.call_args.args[0]["dates"], ["2033-01-01"])
        self.assert_window(QDate(2033, 1, 1), [QDate(2033, 1, 1)])
        self.assertTrue(self.window.date.text().startswith("Today"))

    def test_new_live_search_uses_today_after_selection_expires(self):
        self.window.date.setDate(QDate(2032, 12, 31))
        self.midnight()
        with patch.object(ui, "QThread"), patch.object(ui, "ScanWorker") as worker:
            self.window.search_live()
        self.assertEqual(worker.call_args.args[1], "2033-01-01")
        self.assertEqual(self.window.context["dates"], ["2033-01-01"])

    def test_submitted_live_fallback_keeps_its_original_date(self):
        self.window.date.setDate(QDate(2032, 12, 31))
        submitted = self.window.params()
        self.midnight()
        self.window.params()
        with patch.object(ui, "QThread"), patch.object(ui, "ScanWorker") as worker:
            self.window.search_live(submitted)
        self.assertEqual(worker.call_args.args[1], "2032-12-31")
        self.assertEqual(submitted["dates"], ["2032-12-31"])

    def test_default_tomorrow_becomes_today_without_changing_absolute_selection(self):
        self.assertTrue(self.window.date.text().startswith("Tomorrow"))
        changed = Mock()
        self.window.date.datesChanged.connect(changed)
        self.midnight()
        self.window.params()
        self.assert_window(QDate(2033, 1, 1), [QDate(2033, 1, 1)])
        self.assertTrue(self.window.date.text().startswith("Today"))
        changed.assert_not_called()

    def test_all_28_dates_keep_27_valid_dates_without_selecting_the_new_day(self):
        first = QDate(2032, 12, 31)
        self.window.date.set_dates([first.addDays(i) for i in range(28)])
        changed = Mock()
        self.window.date.datesChanged.connect(changed)
        self.midnight()
        self.window.params()
        self.assert_window(first.addDays(1), [first.addDays(i) for i in range(1, 28)])
        self.assertNotIn(first.addDays(28), self.window.date.selected_qdates())
        self.assertFalse(self.window.live_button.isEnabled())
        changed.assert_called_once_with()

    def test_long_suspend_resets_only_when_no_chosen_date_remains_valid(self):
        first = QDate(2032, 12, 31)
        self.window.date.set_dates([first.addDays(2), first.addDays(7)])
        self.now += timedelta(days=4)
        self.window.params()
        self.assert_window(first.addDays(4), [first.addDays(7)])
        self.assertTrue(self.window.live_button.isEnabled())
        self.now += timedelta(days=30)
        self.window.params()
        self.assert_window(first.addDays(34), [first.addDays(34)])

    def test_utc_midnight_does_not_shift_the_perth_window(self):
        self.now = datetime(2032, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        window = self.make_window()
        before = window.params()
        changed = Mock()
        window.date.datesChanged.connect(changed)
        self.midnight()
        self.assertEqual(window.params(), before)
        self.assertEqual(window.date.minimumDate(), QDate(2033, 1, 1))
        self.assertEqual(window.date.maximumDate(), QDate(2033, 1, 28))
        changed.assert_not_called()

    def test_leap_day_and_month_end_use_the_same_28_day_rule(self):
        for instant in (
            datetime(2032, 2, 28, 15, 59, 59, tzinfo=timezone.utc),
            datetime(2032, 2, 29, 15, 59, 59, tzinfo=timezone.utc),
            datetime(2033, 4, 30, 15, 59, 59, tzinfo=timezone.utc),
        ):
            with self.subTest(instant=instant.isoformat()):
                self.now = instant
                window = self.make_window()
                first = ui.perth_today()
                window.date.setDate(first)
                self.midnight()
                self.assertEqual(window.params()["dates"], [first.addDays(1).toString("yyyy-MM-dd")])
                self.assertEqual(window.date.minimumDate(), first.addDays(1))
                self.assertEqual(window.date.maximumDate(), first.addDays(28))

    def test_opening_picker_refreshes_bounds_and_allows_new_last_day(self):
        self.midnight()
        popup = self.open_popup()
        today = QDate(2033, 1, 1)
        self.assertEqual(popup.calendar.minimumDate(), today)
        self.assertEqual(popup.calendar.maximumDate(), today.addDays(27))
        self.choose(popup, today.addDays(27))
        popup.done_button.click()
        self.assertEqual(self.window.date.selected_qdates(), [today, today.addDays(27)])

    def test_open_popup_keeps_valid_pending_dates_and_cancel_does_not_apply_them(self):
        old = QDate(2032, 12, 31)
        committed = old.addDays(2)
        pending = old.addDays(4)
        self.window.date.set_dates([old, committed])
        popup = self.open_popup()
        self.choose(popup, pending)
        self.midnight()
        self.window.params()
        self.assertEqual(popup.selected_dates(), [committed, pending])
        self.assertEqual(popup.calendar.minimumDate(), old.addDays(1))
        self.assertIn(old.addDays(1).toString("dddd, d MMMM yyyy").upper(), popup.today_label.text())
        self.assertEqual(popup.calendar.dateTextFormat(old).background().style(), Qt.BrushStyle.NoBrush)
        popup.cancel_button.click()
        self.assertEqual(self.window.date.selected_qdates(), [committed])

    def test_applying_open_popup_revalidates_before_any_timer_tick(self):
        old = QDate(2032, 12, 31)
        self.window.date.setDate(old)
        popup = self.open_popup()
        accepted = []
        self.window.date.datesChanged.connect(lambda: accepted.append(self.window.selected_dates()))
        self.midnight()
        popup.done_button.click()
        self.assert_window(old.addDays(1), [old.addDays(1)])
        self.assertEqual(accepted, [["2033-01-01"]])

    def test_applying_pending_future_date_emits_only_the_final_selection(self):
        old = QDate(2032, 12, 31)
        pending = QDate(2033, 1, 5)
        self.window.date.setDate(old)
        popup = self.open_popup()
        self.choose(popup, pending)
        self.choose(popup, old)
        self.assertEqual(popup.selected_dates(), [pending])
        accepted = []
        self.window.date.datesChanged.connect(lambda: accepted.append(self.window.selected_dates()))
        self.midnight()
        popup.done_button.click()
        self.assertEqual(self.window.date.selected_qdates(), [pending])
        self.assertEqual(accepted, [["2033-01-05"]])

    def test_idle_timer_refreshes_controls_without_launching_a_search(self):
        timer = self.window._perth_date_timer
        self.assertTrue(timer.isActive())
        self.assertLessEqual(timer.interval(), 30000)
        self.midnight()
        loop = QEventLoop()
        bound = QTimer()
        bound.setSingleShot(True)
        bound.timeout.connect(loop.quit)
        timer.setInterval(1)
        with patch.object(self.window, "_start_cache_search") as cache, patch.object(ui, "ScanWorker") as live:
            bound.start(25)
            loop.exec()
        self.assert_window(QDate(2033, 1, 1), [QDate(2033, 1, 1)])
        self.assertTrue(self.window.date.text().startswith("Today"))
        cache.assert_not_called()
        live.assert_not_called()
        self.window.close()
        self.assertFalse(timer.isActive())

    def test_activation_rechecks_clock_before_idle_timer(self):
        self.midnight()
        QApplication.sendEvent(self.window, QEvent(QEvent.Type.ActivationChange))
        self.assert_window(QDate(2033, 1, 1), [QDate(2033, 1, 1)])
        self.assertTrue(self.window.date.text().startswith("Today"))

    def test_submitted_results_and_lazy_sections_keep_their_dates_after_rollover(self):
        old = QDate(2032, 12, 31)
        dates = [old.toString("yyyy-MM-dd"), old.addDays(2).toString("yyyy-MM-dd")]
        self.window.date.set_dates([old, old.addDays(2)])
        submitted = self.window.params()
        self.window.context = submitted
        active = self.window._snapshot_search_context(submitted)
        pending = self.window._snapshot_search_context(submitted)
        self.window._active_cache_context = active
        self.window._pending_cache_context = pending
        site = next(site for site in self.window.sites if site.provider != "direct" and "18" in site.holes)
        result = {"site_name": site.name, "hole_label": "18 holes", "url": "https://example.invalid/course",
                  "decorated_rows": [{"time": "10:00 am", "minutes": 600, "spots": 4,
                                      "source_url": "https://example.invalid/row"}], "weather": None}
        self.window.render_multi_results([{"date": date, "results": [result], "source": "Fixture"}
                                          for date in dates], "Fixture")
        self.assertFalse(self.window.day_sections[1]._built)
        self.midnight()
        self.window.params()
        self.assertIs(self.window.context, submitted)
        self.assertIs(self.window._active_cache_context, active)
        self.assertIs(self.window._pending_cache_context, pending)
        for context in (submitted, active, pending):
            self.assertEqual(context["dates"], dates)
        for section, day in zip(self.window.day_sections, (old, old.addDays(2))):
            section.set_expanded(True)
            button = next(button for button in section.findChildren(QPushButton) if button.text() == "BOOK")
            self.assertIn(day.toString("d MMMM yyyy"), button.accessibleName())
        self.assertEqual(self.window.last_results, [result, result])


if __name__ == "__main__":
    unittest.main()
