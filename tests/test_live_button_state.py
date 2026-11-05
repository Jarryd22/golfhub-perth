"""Refresh Live eligibility follows pending dates and retained request ownership."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-live-button-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QPushButton

from app import qt_golfhub_app as ui
from app import shared_cache as cache
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class LiveButtonStateTests(unittest.TestCase):
    old_date, new_date, extra_date = "2033-01-02", "2033-01-03", "2033-01-04"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.runtime = self.enterContext(tempfile.TemporaryDirectory(dir=_runtime.name))
        self.enterContext(patch.object(cache, "LOCAL_CACHE_DIR", Path(self.runtime) / "cache"))
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                       "socket.getaddrinfo", "webbrowser.open", "app.qt_golfhub_app.fetch_site_result",
                       "app.course_results.get_weather_for_date", "app.qt_golfhub_app.BookingAssistDialog"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline button-state test")))
        self.save = self.enterContext(patch.object(ui, "save_local_snapshot"))
        self.dialog = self.enterContext(patch.object(ui.QMessageBox, "critical"))
        self.enterContext(patch.object(ui, "perth_today", return_value=QDate(2033, 1, 2)))
        self.callbacks = []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callbacks.append(str(a[1]))))
        self.workers = []
        self.threads = []

        def thread_factory():
            thread = MagicMock()
            thread.isRunning.return_value = True
            thread.wait.return_value = True
            self.threads.append(thread)
            return thread

        # Real worker objects and signals, but no native thread or provider work.
        self.enterContext(patch.object(ui, "QThread", side_effect=thread_factory))
        self.enterContext(patch.object(ui.ScanWorker, "moveToThread"))
        self.enterContext(patch.object(ui.CacheWorker, "moveToThread"))
        with patch.object(ui.GolfHub, "show_initial_cache"):
            self.window = ui.GolfHub()
        self.window._stop_deferred_timers()
        self.window.resize(1280, 800)
        self.window.show()
        self.window.set_all(False)
        self.site = next(row.site for row in self.window.course_rows if row.site.name == "Araluen")
        next(row for row in self.window.course_rows if row.site.name == self.site.name).check.setChecked(True)
        self.dates(self.old_date)
        self.window.players.setCurrentText("1")

    def tearDown(self):
        for kind in ("scan", "cache"):
            worker = getattr(self.window, f"{kind}_worker")
            if worker is not None and worker not in self.workers:
                self.workers.append(worker)
            setattr(self.window, f"{kind}_worker", None)
            setattr(self.window, f"{kind}_thread", None)
        for worker in self.workers:
            worker.deleteLater()
        cleanup_qt_widgets()
        self.assertEqual(self.callbacks, [], "Qt callbacks must not raise")

    def dates(self, *values):
        self.window.date.set_dates([QDate.fromString(value, "yyyy-MM-dd") for value in values])

    def start_live(self):
        self.window.live_button.click()
        worker = self.window.scan_worker
        self.assertIsInstance(worker, ui.ScanWorker)
        self.workers.append(worker)
        self.window.scan_thread.start.assert_called_once()
        self.assertFalse(self.window.live_button.isEnabled())
        return worker, self.window.scan_thread

    def emit_completion(self, worker, outcome, results=None):
        if outcome == "failure":
            worker.failed.emit("RuntimeError: Synthetic worker failure")
        else:
            if outcome == "cancelled":
                self.window.stop_scan()
            worker.finished.emit(results or [], outcome == "cancelled")

    def complete_cleanup(self, thread):
        thread.isRunning.return_value = False
        thread.wait.return_value = True
        self.window.scan_thread_done()
        self.assertIsNone(self.window.scan_thread)
        self.assertIsNone(self.window.scan_worker)

    def assert_multi_completion(self, outcome):
        worker, thread = self.start_live()
        self.dates(self.new_date, self.extra_date)
        self.assertFalse(self.window.live_button.isEnabled())
        self.emit_completion(worker, outcome)
        enabled_before_cleanup = self.window.live_button.isEnabled()
        self.complete_cleanup(thread)
        self.assertFalse(self.window.live_button.isEnabled(), "Multi-date controls do not support Refresh Live")
        self.assertFalse(enabled_before_cleanup, "Retained worker ownership also prevents a new live request")
        self.assertEqual(self.window.day_count(), 2)
        self.assertIn("Multi-day", self.window.live_button.toolTip())
        self.assertIn("2 selected dates", self.window.search_helper.text())
        before = self.window.status.text()
        self.window.live_button.click()
        self.assertEqual(self.window.status.text(), before)
        self.assertIsNone(self.window.scan_thread)
        self.assertEqual(len(self.threads), 1)
        if outcome != "success":
            self.save.assert_not_called()

    def test_success_keeps_live_disabled_for_pending_multiple_dates(self):
        self.assert_multi_completion("success")

    def test_failure_keeps_live_disabled_for_pending_multiple_dates(self):
        self.assert_multi_completion("failure")

    def test_cancellation_keeps_live_disabled_for_pending_multiple_dates(self):
        self.assert_multi_completion("cancelled")

    def test_single_date_retry_is_enabled_only_after_cleanup_and_submits_current_controls(self):
        worker, thread = self.start_live()
        self.dates(self.new_date)
        self.window.players.setCurrentText("4")
        self.emit_completion(worker, "success")
        self.assertFalse(self.window.live_button.isEnabled())
        self.window.live_button.click()
        self.assertIs(self.window.scan_worker, worker)
        self.assertEqual(len(self.threads), 1)
        self.complete_cleanup(thread)
        self.assertTrue(self.window.live_button.isEnabled())
        next_worker, _ = self.start_live()
        self.assertIsNot(next_worker, worker)
        self.assertEqual(len(self.threads), 2)
        self.assertEqual(self.window.context["date"], self.new_date)
        self.assertEqual(self.window.context["players"], 4)

    def test_date_changes_during_unfinished_cleanup_cannot_enable_ignored_action(self):
        worker, thread = self.start_live()
        self.emit_completion(worker, "failure")
        thread.isRunning.return_value = False
        thread.wait.return_value = False
        self.window.scan_thread_done()
        self.assertIs(self.window.scan_thread, thread)
        self.dates(self.new_date, self.extra_date)
        self.assertFalse(self.window.live_button.isEnabled())
        self.dates(self.new_date)
        self.assertFalse(self.window.live_button.isEnabled(), "isRunning=False does not release request ownership")
        self.window.live_button.click()
        self.assertIs(self.window.scan_worker, worker)
        self.assertEqual(len(self.threads), 1)
        self.complete_cleanup(thread)
        self.assertTrue(self.window.live_button.isEnabled())
        self.save.assert_not_called()

    def test_returning_from_multiple_to_single_date_restores_action_after_completion(self):
        worker, thread = self.start_live()
        self.dates(self.new_date, self.extra_date)
        self.dates(self.extra_date)
        self.assertFalse(self.window.live_button.isEnabled())
        self.emit_completion(worker, "cancelled")
        self.assertFalse(self.window.live_button.isEnabled())
        self.complete_cleanup(thread)
        self.assertTrue(self.window.live_button.isEnabled())
        self.assertEqual(self.window.selected_dates(), [self.extra_date])
        self.assertEqual(self.window.live_button.toolTip(), "Refresh this date directly from course sites")
        self.assertIn("Fast cache first", self.window.search_helper.text())
        self.save.assert_not_called()

    def test_cache_request_keeps_live_disabled_when_previous_live_cleanup_finishes(self):
        worker, thread = self.start_live()
        self.emit_completion(worker, "success")
        self.dates(self.new_date)
        self.window.search_button.click()
        cache_worker, cache_thread = self.window.cache_worker, self.window.cache_thread
        self.assertIsInstance(cache_worker, ui.CacheWorker)
        self.workers.append(cache_worker)
        self.assertFalse(self.window.live_button.isEnabled())
        self.complete_cleanup(thread)
        self.assertFalse(self.window.live_button.isEnabled())
        self.assertIs(self.window.cache_thread, cache_thread)
        cache_worker.finished.emit({self.new_date: cache.make_snapshot(self.new_date, "18", [])})
        self.assertFalse(self.window.live_button.isEnabled())
        cache_thread.isRunning.return_value = False
        self.window.cache_thread_done()
        self.assertIsNone(self.window.cache_thread)
        self.assertTrue(self.window.live_button.isEnabled())
        self.assertEqual(len(self.threads), 2)

    def test_pending_dates_and_filters_do_not_change_submitted_result_or_saved_context(self):
        worker, thread = self.start_live()
        self.dates(self.new_date, self.extra_date)
        self.window.players.setCurrentText("4")
        self.window.time_preset.setCurrentText("Afternoon")
        result = {"site_name": self.site.name, "url": f"https://{self.site.domain}", "hole_label": "18 holes",
                  "decorated_rows": [{"time": "9:00 am", "minutes": 540, "spots": 2}],
                  "error": None, "weather": None}
        self.emit_completion(worker, "success", [result])
        self.complete_cleanup(thread)
        self.assertEqual(self.window.context["date"], self.old_date)
        self.assertEqual(self.window.context["players"], 1)
        self.assertEqual(self.window.last_results, [result])
        cards = self.window.results_body.findChildren(ui.TeeTimeCard)
        self.assertEqual([(card.row["minutes"], card.row["spots"]) for card in cards], [(540, 2)])
        self.save.assert_called_once()
        self.assertEqual(self.save.call_args.args[0]["date"], self.old_date)
        self.assertEqual(self.save.call_args.args[0]["results"], [result])
        self.assertFalse(self.window.live_button.isEnabled())

    def test_closing_window_does_not_reenable_live_on_terminal_or_cleanup_callbacks(self):
        worker, thread = self.start_live()
        self.window.close()
        self.assertTrue(self.window._closing)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.live_button.isEnabled())
        self.emit_completion(worker, "cancelled")
        terminal_enabled = self.window.live_button.isEnabled()
        with patch.object(self.window._close_timer, "start") as close_schedule:
            self.complete_cleanup(thread)
        close_schedule.assert_called_once_with(0)
        self.assertFalse(self.window.live_button.isEnabled())
        self.assertFalse(terminal_enabled)
        self.window.live_button.click()
        self.assertIsNone(self.window.scan_thread)
        self.assertEqual(len(self.threads), 1)
        self.dialog.assert_not_called()
        self.save.assert_not_called()

    def test_disabled_live_uses_existing_disabled_text_color_and_restores_enabled_color(self):
        live = self.window.live_button
        live.ensurePolished()
        enabled_text = live.palette().color(QPalette.Active, QPalette.ButtonText).name()
        reference = QPushButton("Disabled reference", self.window.centralWidget())
        reference.setEnabled(False)
        reference.ensurePolished()
        self.dates(self.new_date, self.extra_date)
        self.assertFalse(live.isEnabled())
        disabled_text = live.palette().color(QPalette.Disabled, QPalette.ButtonText).name()
        self.assertNotEqual(disabled_text, enabled_text)
        self.assertEqual(disabled_text, ui.PALETTE["faint"].lower())
        self.assertEqual(disabled_text, reference.palette().color(QPalette.Disabled, QPalette.ButtonText).name())
        self.dates(self.new_date)
        self.assertTrue(live.isEnabled())
        self.assertEqual(live.palette().color(QPalette.Active, QPalette.ButtonText).name(), enabled_text)
        self.assertEqual(enabled_text, ui.PALETTE["text"].lower())


if __name__ == "__main__":
    unittest.main()
