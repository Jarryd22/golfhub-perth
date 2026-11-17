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

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
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

    def handoff_result(self, date, holes="9"):
        url = f"https://{self.site.domain}/guests/bookings/ViewPublicTimesheet.msp?selectedDate={date}"
        return {"site_name": self.site.name, "url": url, "hole_label": f"{holes} holes",
                "decorated_rows": [{"time": "10:00 am", "minutes": 600, "spots": 4,
                                    "source_url": url}], "weather": None, "error": None}

    def terminal_live_owner(self, outcome="failure"):
        self.enterContext(patch.object(ui, "load_local_snapshot", return_value=None))
        worker, thread = self.start_live()
        thread.isRunning.return_value = False
        thread.wait.return_value = False
        if outcome == "cancelled":
            QTest.mouseClick(self.window.stop_button, Qt.LeftButton)
            self.assertTrue(worker.cancel_requested)
            worker.finished.emit([], True)
        else:
            self.emit_completion(worker, outcome)
        self.assertTrue(self.window.search_button.isEnabled(), "Find remains usable after a terminal result")
        self.assertIs(self.window.scan_thread, thread)
        self.save.reset_mock()
        return worker, thread

    def find_handoff_cache(self, *dates, holes="9", players="4", preset="Morning"):
        self.dates(*(dates or (self.new_date,)))
        QTest.mouseClick(self.window.holes9 if holes == "9" else self.window.holes18, Qt.LeftButton)
        self.window.players.setCurrentText(players)
        self.window.time_preset.setCurrentText(preset)
        submitted = self.window.params()
        self.assertTrue(self.window.search_button.isEnabled())
        QTest.mouseClick(self.window.search_button, Qt.LeftButton)
        worker, thread = self.window.cache_worker, self.window.cache_thread
        self.assertIsInstance(worker, ui.CacheWorker)
        if worker not in self.workers:
            self.workers.append(worker)
        return worker, thread, submitted

    def release_handoff_cache(self, thread):
        thread.isRunning.return_value = False
        thread.wait.return_value = True
        self.window.cache_thread_done()

    def release_handoff_scan(self, thread):
        thread.isRunning.return_value = False
        thread.wait.return_value = True
        self.window.scan_thread_done()

    def assert_handoff_worker(self, original, submitted):
        worker = self.window.scan_worker
        self.assertIsNotNone(worker, "The cache miss must eventually launch its live fallback")
        self.assertIsNot(worker, original)
        self.window.scan_thread.start.assert_called_once()
        if worker not in self.workers:
            self.workers.append(worker)
        self.assertEqual(worker.date_str, submitted["date"])
        self.assertEqual(worker.hole_type, submitted["holes"])
        self.assertEqual(worker.players, submitted["players"])
        self.assertEqual((worker.pref_from, worker.pref_to), (submitted["from"], submitted["to"]))
        self.assertEqual(worker.sites, submitted["sites"])
        self.assertEqual(self.window.context, submitted)
        return worker, self.window.scan_thread

    def exercise_terminal_cache_miss_handoff(self, outcome, cache_cleanup_first):
        old_worker, old_thread = self.terminal_live_owner(outcome)
        cache_worker, cache_thread, submitted = self.find_handoff_cache()
        cache_worker.finished.emit({})
        self.assertIs(self.window.scan_worker, old_worker)
        self.assertEqual(len(self.threads), 2, "Do not overlap live worker ownership")
        self.save.assert_not_called()
        # Unsubmitted controls must not alter the already requested fallback.
        self.dates(self.extra_date)
        self.window.holes18.click()
        self.window.players.setCurrentText("1")
        self.window.time_preset.setCurrentText("Afternoon")
        if cache_cleanup_first:
            self.release_handoff_cache(cache_thread)
            self.release_handoff_scan(old_thread)
        else:
            self.release_handoff_scan(old_thread)
            self.release_handoff_cache(cache_thread)
        next_worker, next_thread = self.assert_handoff_worker(old_worker, submitted)
        self.assertEqual(len(self.threads), 3)
        self.assertFalse(self.window.search_button.isEnabled())
        self.assertTrue(self.window.progress.isVisible())
        self.window.cache_thread_done()
        self.assertEqual(len(self.threads), 3, "Repeated cache cleanup must not duplicate fallback")
        result = self.handoff_result(submitted["date"], submitted["holes"])
        with patch.object(self.window, "open_tee_time") as booking:
            next_worker.finished.emit([result], False)
            card = self.window.results_body.findChild(ui.TeeTimeCard)
            self.assertIsNotNone(card)
            next(button for button in card.findChildren(QPushButton) if button.text() == "BOOK").click()
        booking.assert_called_once_with(result, result["decorated_rows"][0], context=submitted)
        self.save.assert_called_once()
        saved = self.save.call_args.args[0]
        self.assertEqual((saved["date"], saved["holes"], saved["results"]),
                         (submitted["date"], submitted["holes"], [result]))
        self.complete_cleanup(next_thread)
        self.assertTrue(self.window.search_button.isEnabled())
        self.assertEqual(self.window.header_status.text(), "LIVE RESULTS / UPDATED NOW")

    def test_failed_live_then_cache_miss_recovers_when_cache_cleanup_finishes_first(self):
        self.exercise_terminal_cache_miss_handoff("failure", True)

    def test_failed_live_then_cache_miss_recovers_when_live_cleanup_finishes_first(self):
        self.exercise_terminal_cache_miss_handoff("failure", False)

    def test_cancelled_live_then_cache_miss_recovers_when_cache_cleanup_finishes_first(self):
        self.exercise_terminal_cache_miss_handoff("cancelled", True)

    def test_cancelled_live_then_cache_miss_recovers_when_live_cleanup_finishes_first(self):
        self.exercise_terminal_cache_miss_handoff("cancelled", False)

    def test_successful_live_then_cache_miss_recovers_when_cache_cleanup_finishes_first(self):
        self.exercise_terminal_cache_miss_handoff("success", True)

    def test_successful_live_then_cache_miss_recovers_when_live_cleanup_finishes_first(self):
        self.exercise_terminal_cache_miss_handoff("success", False)

    def test_newest_queued_single_search_supersedes_an_older_waiting_fallback(self):
        old_worker, old_thread = self.terminal_live_owner()
        first_cache, first_thread, first = self.find_handoff_cache()
        first_cache.finished.emit({})
        queued_worker, queued_thread, newest = self.find_handoff_cache(
            self.extra_date, holes="18", players="2", preset="Afternoon")
        self.assertIs(queued_worker, first_cache)
        self.assertIs(queued_thread, first_thread)
        self.release_handoff_scan(old_thread)
        self.assertIsNone(self.window.scan_worker, "A newer explicit search supersedes the old fallback")
        self.assertEqual(len(self.threads), 2)
        self.release_handoff_cache(first_thread)
        next_cache, next_thread = self.window.cache_worker, self.window.cache_thread
        self.assertIsNot(next_cache, first_cache)
        self.workers.append(next_cache)
        self.assertEqual(next_cache.date_strings, newest["dates"])
        self.assertEqual(next_cache.hole_type, newest["holes"])
        next_cache.finished.emit({})
        fallback, _ = self.assert_handoff_worker(old_worker, newest)
        self.assertNotEqual(fallback.date_str, first["date"])
        self.release_handoff_cache(next_thread)
        self.assertEqual(len(self.threads), 4, "Only the newest cache request may launch live work")
        self.save.assert_not_called()

    def test_newer_multidate_search_cancels_waiting_single_date_fallback(self):
        old_worker, old_thread = self.terminal_live_owner()
        first_cache, first_thread, _ = self.find_handoff_cache()
        first_cache.finished.emit({})
        self.release_handoff_cache(first_thread)
        next_cache, next_thread, newest = self.find_handoff_cache(
            self.new_date, self.extra_date, holes="18", players="2")
        self.release_handoff_scan(old_thread)
        self.assertIsNone(self.window.scan_worker)
        next_cache.finished.emit({})
        self.release_handoff_cache(next_thread)
        self.assertIsNone(self.window.scan_worker)
        self.assertEqual(self.window.context, newest)
        self.assertEqual(self.window.header_status.text(), "SHARED CACHE UNAVAILABLE")
        self.assertFalse(self.window.live_button.isEnabled())
        self.assertEqual(len(self.threads), 3)
        self.save.assert_not_called()

    def test_close_cancels_waiting_live_fallback_without_launching_another_worker(self):
        old_worker, old_thread = self.terminal_live_owner()
        cache_worker, cache_thread, _ = self.find_handoff_cache()
        cache_worker.finished.emit({})
        self.window.close()
        self.assertTrue(self.window._closing)
        with patch.object(self.window._close_timer, "start") as close_schedule:
            self.release_handoff_cache(cache_thread)
            self.release_handoff_scan(old_thread)
        self.assertIsNone(self.window.scan_worker)
        self.assertIsNone(self.window.cache_worker)
        self.assertEqual(len(self.threads), 2)
        close_schedule.assert_called_once_with(0)
        self.save.assert_not_called()

    def test_cache_hit_before_old_live_cleanup_renders_without_a_fallback(self):
        old_worker, old_thread = self.terminal_live_owner()
        cache_worker, cache_thread, submitted = self.find_handoff_cache()
        result = self.handoff_result(submitted["date"])
        cache_worker.finished.emit({submitted["date"]: cache.make_snapshot(submitted["date"], "9", [result])})
        self.assertEqual(self.window.last_results, [result])
        self.assertTrue(self.window.header_status.text().startswith("SHARED CACHE / "))
        self.release_handoff_cache(cache_thread)
        self.release_handoff_scan(old_thread)
        self.assertIsNone(self.window.scan_worker)
        self.assertEqual(len(self.threads), 2)
        self.assertEqual(self.window.last_results, [result])
        self.save.assert_not_called()

    def test_invalid_new_search_does_not_discard_the_valid_waiting_fallback(self):
        old_worker, old_thread = self.terminal_live_owner()
        cache_worker, cache_thread, submitted = self.find_handoff_cache()
        cache_worker.finished.emit({})
        self.assertTrue(self.window.search_button.isEnabled())
        with patch.object(self.window, "params", return_value=None) as invalid:
            QTest.mouseClick(self.window.search_button, Qt.LeftButton)
        invalid.assert_called_once()
        self.assertEqual(len(self.threads), 2)
        self.release_handoff_cache(cache_thread)
        self.release_handoff_scan(old_thread)
        self.assert_handoff_worker(old_worker, submitted)
        self.assertEqual(len(self.threads), 3)
        self.save.assert_not_called()

    def test_cache_cleanup_keeps_new_fallback_busy_while_its_owner_is_retained(self):
        old_worker, old_thread = self.terminal_live_owner()
        cache_worker, cache_thread, submitted = self.find_handoff_cache()
        cache_worker.finished.emit({})
        self.release_handoff_scan(old_thread)
        fallback, fallback_thread = self.assert_handoff_worker(old_worker, submitted)
        # Controlled ownership interval; no native timing or shutdown assertion.
        fallback_thread.isRunning.return_value = False
        fallback_thread.wait.return_value = False
        self.release_handoff_cache(cache_thread)
        self.assertIs(self.window.scan_thread, fallback_thread)
        self.assertFalse(self.window.search_button.isEnabled())
        self.assertFalse(self.window.live_button.isEnabled())
        self.assertTrue(self.window.progress.isVisible())
        self.assertEqual(self.window.header_status.text(), "LIVE REFRESH IN PROGRESS")
        fallback.finished.emit([], True)
        self.release_handoff_scan(fallback_thread)
        self.assertTrue(self.window.search_button.isEnabled())
        self.assertTrue(self.window.live_button.isEnabled())
        self.assertFalse(self.window.progress.isVisible())
        self.assertEqual(len(self.threads), 3)
        self.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
