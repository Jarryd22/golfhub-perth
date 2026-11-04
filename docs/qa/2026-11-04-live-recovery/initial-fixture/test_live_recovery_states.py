"""Cold and retained-result recovery through synthetic live worker signals."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-live-recovery-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from app import shared_cache as cache
from app import qt_golfhub_app as ui
from app.booking_assist import build_booking_assist_plan
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class LiveRecoveryStateTests(unittest.TestCase):
    old_date, next_date, new_date = "2033-01-02", "2033-01-03", "2033-01-05"
    failed_note = "Could not load tee-time results. Try Find Tee Times or Refresh Live again."
    stopped_note = "Refresh stopped before results were available. Try Find Tee Times or Refresh Live again."

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.runtime = self.enterContext(tempfile.TemporaryDirectory(dir=_runtime.name))
        self.enterContext(patch.object(cache, "LOCAL_CACHE_DIR", Path(self.runtime) / "cache"))
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                       "socket.getaddrinfo", "app.qt_golfhub_app.fetch_site_result",
                       "app.course_results.get_weather_for_date", "app.qt_golfhub_app.BookingAssistDialog"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline recovery test")))
        self.browser = self.enterContext(patch("app.qt_golfhub_app.webbrowser.open", return_value=True))
        self.dialog = self.enterContext(patch.object(ui.QMessageBox, "critical"))
        self.save = self.enterContext(patch.object(ui, "save_local_snapshot"))
        self.enterContext(patch.object(ui, "perth_today", return_value=QDate(2033, 1, 2)))
        self.callbacks = []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callbacks.append(str(a[1]))))
        self.workers = []
        self.threads = []

        def thread_factory():
            thread = MagicMock()
            thread.isRunning.return_value = False
            thread.wait.return_value = True
            self.threads.append(thread)
            return thread

        # Use real worker QObjects/signals, but never create or start a native worker thread.
        self.enterContext(patch.object(ui, "QThread", side_effect=thread_factory))
        self.enterContext(patch.object(ui.ScanWorker, "moveToThread"))
        self.enterContext(patch.object(ui.CacheWorker, "moveToThread"))
        with patch.object(ui.GolfHub, "show_initial_cache"):
            self.window = ui.GolfHub()
        self.window._stop_deferred_timers()
        self.window.resize(1280, 800)
        self.window.show()
        self.sites = {site.name: site for site in self.window.sites}
        self.controls([self.old_date], players=1)

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

    def settle(self):
        for _ in range(3):
            self.app.processEvents()

    def controls(self, dates, players=1, time="Any time", courses=("Araluen",)):
        self.window.set_all(False)
        for row in self.window.course_rows:
            row.check.setChecked(row.site.name in courses)
        self.window.date.set_dates([QDate.fromString(value, "yyyy-MM-dd") for value in dates])
        self.window.players.setCurrentText("Any" if players is None else str(players))
        self.window.time_preset.setCurrentText(time)

    def result(self, date, *, spots=4, minutes=540):
        url = (f"https://{self.sites['Araluen'].domain}/guests/bookings/ViewPublicTimesheet.msp"
               f"?bookingResourceId=3000000&selectedDate={date}&feeGroupId=102807")
        hour, minute = divmod(minutes, 60)
        row = {"time": f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}",
               "minutes": minutes, "spots": spots, "source_url": url}
        return {"site_name": "Araluen", "url": url, "hole_label": "18 holes",
                "decorated_rows": [row], "error": None, "weather": None}

    def saved_single(self):
        self.controls([self.old_date])
        self.window.context = self.window.params()
        result = self.result(self.old_date)
        payload = cache.make_snapshot(self.old_date, "18", [result])
        cache.save_local_snapshot(payload)
        self.window.render_snapshot(payload, "Saved on this device")
        return result

    def saved_multi(self):
        self.controls([self.old_date, self.next_date], time="Morning")
        self.window.context = self.window.params()
        days = [{"date": date, "results": [self.result(date, spots=2)],
                 "source": "Synthetic saved snapshot"} for date in (self.old_date, self.next_date)]
        self.window.render_multi_results(days, "Synthetic saved dates")

    def start_live(self, *, date=None, players=4, time="Afternoon", courses=("Araluen",)):
        self.controls([date or self.new_date], players, time, courses)
        self.window.search_live()
        worker = self.window.scan_worker
        self.assertIsInstance(worker, ui.ScanWorker)
        self.workers.append(worker)
        self.window.scan_thread.start.assert_called_once()
        return worker

    def fail(self, worker):
        # This is an outer worker failure before the first request, not a provider error result.
        with patch.object(ui, "ThreadPoolExecutor", side_effect=RuntimeError("Synthetic executor setup failed")):
            worker.run()
        self.settle()

    def finish_mock_thread(self):
        # No native thread exists; simulate its completion after the tested terminal signal.
        self.window.scan_thread_done()
        self.assertIsNone(self.window.scan_thread)
        self.assertIsNone(self.window.scan_worker)

    def labels(self):
        return [label.text() for label in self.window.results_body.findChildren(QLabel)]

    def assert_cold(self, *, stopped=False):
        note = self.stopped_note if stopped else self.failed_note
        self.assertEqual(self.labels().count(note), 1)
        self.assertNotIn("Checking courses live...", self.labels())
        self.assertEqual(len(self.window.results_body.findChildren(QFrame, "EmptyState")), 1)
        self.assertEqual(self.window.results_body.findChildren(ui.TeeTimeCard), [])
        self.assertEqual(self.window.results_body.findChildren(ui.DaySection), [])
        self.assertEqual(self.window.last_results, [])
        self.assertEqual(self.window.day_sections, [])
        self.assertEqual(self.window.header_status.text(), "REFRESH STOPPED" if stopped else "LIVE REFRESH FAILED")
        self.assertEqual(self.window.status.text(), "Stopped - partial results were not saved" if stopped
                         else "Live refresh failed - no results available")
        self.assertTrue(self.window.search_button.isEnabled())
        self.assertTrue(self.window.live_button.isEnabled())
        self.assertFalse(self.window.progress.isVisible())
        self.assertFalse(self.window.stop_button.isVisible())
        self.save.assert_not_called()

    def test_empty_first_launch_cache_fallback_recovers_from_real_failed_signal(self):
        with patch.object(self.window._cache_search_timer, "start") as schedule:
            self.window.show_initial_cache()
        schedule.assert_called_once_with(100)
        self.window.context = self.window.params()
        self.window._active_cache_context = self.window._snapshot_search_context(self.window.context)
        self.window.cache_finished({})
        worker = self.window.scan_worker
        self.workers.append(worker)
        self.assertIn("Checking courses live...", self.labels())
        self.fail(worker)
        self.assert_cold()
        self.dialog.assert_called_once()
        self.assertEqual(self.dialog.call_args.args[2], self.failed_note +
                         "\n\nRuntimeError: Synthetic executor setup failed")

    def test_cold_stop_replaces_checking_view_without_claiming_saved_results(self):
        worker = self.start_live()
        self.window.stop_scan()
        worker.finished.emit([self.result(self.new_date)], True)
        self.settle()
        self.assert_cold(stopped=True)
        self.dialog.assert_not_called()

    def test_new_cache_search_clears_previous_days_before_failure_or_stop(self):
        for stopped in (False, True):
            with self.subTest(stopped=stopped):
                self.saved_multi()
                old_results, old_sections = self.window.last_results, self.window.day_sections
                self.controls([self.new_date], players=4)
                self.window.search_cache()
                self.workers.append(self.window.cache_worker)
                self.assertIn("Checking the shared cache...", self.labels())
                self.assertEqual(len(old_results), 2)
                self.assertEqual(len(old_sections), 2)
                self.assertEqual(self.window.last_results, [])
                self.assertEqual(self.window.day_sections, [])
                self.window.cache_finished({})
                worker = self.window.scan_worker
                self.workers.append(worker)
                if stopped:
                    self.window.stop_scan()
                    worker.finished.emit([], True)
                    self.settle()
                else:
                    self.fail(worker)
                self.assert_cold(stopped=stopped)
                self.finish_mock_thread()
                self.window.cache_thread_done()
                self.dialog.reset_mock()

    def test_failed_refresh_keeps_actual_saved_card_bytes_and_booking_context(self):
        self.saved_single()
        before = {path: path.read_bytes() for path in Path(self.runtime).rglob("*.json")}
        self.assertTrue(before)
        card = self.window.results_body.findChild(ui.TeeTimeCard)
        self.fail(self.start_live(players=4))
        self.assertIs(self.window.results_body.findChild(ui.TeeTimeCard), card)
        self.assertEqual(self.window.header_status.text(), "LIVE REFRESH FAILED / PREVIOUS RESULTS KEPT")
        self.assertEqual(self.window.status.text(), "Live refresh failed - previous results kept")
        self.assertTrue(self.dialog.call_args.args[2].startswith("GolfHub kept the previous results on screen.\n\n"))
        with patch.object(ui, "build_booking_assist_plan", wraps=build_booking_assist_plan) as plan, \
                patch.object(self.window, "_booking_choice", return_value="cancel"):
            next(button for button in card.findChildren(QPushButton) if button.text() == "BOOK").click()
        self.assertEqual(plan.call_args.kwargs["players"], 1)
        self.assertIn(f"selectedDate={self.old_date}", plan.call_args.kwargs["source_url"])
        self.assertEqual(self.window.context["players"], 4)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.browser.assert_not_called()
        self.save.assert_not_called()

    def test_failed_refresh_keeps_lazy_multiday_rows_and_original_date(self):
        self.saved_multi()
        sections = list(self.window.day_sections)
        self.assertFalse(sections[1]._built)
        self.fail(self.start_live())
        self.assertEqual(self.window.day_sections, sections)
        self.assertEqual(self.window.header_status.text(), "LIVE REFRESH FAILED / PREVIOUS RESULTS KEPT")
        sections[1].set_expanded(True)
        cards = sections[1].findChildren(ui.TeeTimeCard)
        self.assertEqual([(card.row["minutes"], card.row["spots"]) for card in cards], [(540, 2)])
        button = next(button for button in cards[0].findChildren(QPushButton) if button.text() == "BOOK")
        self.assertIn("3 January 2033", button.accessibleName())
        self.save.assert_not_called()

    def test_failed_refresh_keeps_static_offline_course_action(self):
        self.controls([self.old_date, self.next_date], courses=("Altone Park",))
        self.window.context = self.window.params()
        self.window._active_cache_context = self.window._snapshot_search_context(self.window.context)
        self.window.cache_finished({})
        card = self.window.results_body.findChild(ui.DirectCourseCard)
        self.assertIsNotNone(card)
        self.fail(self.start_live(courses=("Altone Park",)))
        self.assertIs(self.window.results_body.findChild(ui.DirectCourseCard), card)
        self.assertEqual(self.window.header_status.text(), "LIVE REFRESH FAILED / PREVIOUS RESULTS KEPT")
        card.findChild(QPushButton).click()
        self.browser.assert_called_once_with(f"https://{self.sites['Altone Park'].domain}")
        self.save.assert_not_called()

    def test_cancelled_refresh_keeps_previous_multiday_cards_without_saving_partial(self):
        self.saved_multi()
        sections, results = list(self.window.day_sections), list(self.window.last_results)
        worker = self.start_live()
        self.window.stop_scan()
        worker.finished.emit([self.result(self.new_date, minutes=960)], True)
        self.assertEqual(self.window.day_sections, sections)
        self.assertEqual(self.window.last_results, results)
        self.assertEqual(self.window.header_status.text(), "REFRESH STOPPED / PREVIOUS RESULTS KEPT")
        self.assertEqual(self.window.status.text(), "Stopped - partial results were not saved")
        self.assertNotIn(self.stopped_note, self.labels())
        self.dialog.assert_not_called()
        self.save.assert_not_called()

    def test_successful_retry_replaces_failure_state_with_new_results(self):
        self.fail(self.start_live())
        self.assert_cold()
        self.finish_mock_thread()
        self.window.live_button.click()
        worker = self.window.scan_worker
        self.workers.append(worker)
        result = self.result(self.new_date, minutes=960)
        worker.finished.emit([result], False)
        self.settle()
        self.assertEqual(self.window.last_results, [result])
        self.assertEqual(self.window.header_status.text(), "LIVE RESULTS / UPDATED NOW")
        self.assertEqual(self.window.status.text(), "1 matching tee time across 1 course")
        self.assertEqual(self.window.results_body.findChildren(QFrame, "EmptyState"), [])
        self.assertEqual(len(self.window.results_body.findChildren(ui.TeeTimeCard)), 1)
        self.assertNotIn(self.failed_note, self.labels())
        self.save.assert_called_once()
        self.assertEqual(self.save.call_args.args[0]["date"], self.new_date)
        self.assertEqual(self.save.call_args.args[0]["results"], [result])

    def test_repeated_cold_failures_have_one_empty_frame_and_reachable_retry(self):
        self.fail(self.start_live())
        self.finish_mock_thread()
        self.window.live_button.click()
        worker = self.window.scan_worker
        self.workers.append(worker)
        self.fail(worker)
        self.assert_cold()
        layout = self.window.results_layout
        self.assertEqual(sum(layout.itemAt(i).spacerItem() is not None for i in range(layout.count())), 1)
        self.assertEqual(self.window.results_scroll.verticalScrollBar().value(), 0)
        self.assertEqual(self.dialog.call_count, 2)

    def test_rerendering_last_results_alias_preserves_input_rows(self):
        result = self.saved_single()
        original_results = self.window.last_results
        self.window.render_results(self.window.last_results, "Re-render saved results")
        self.assertEqual(original_results, [result])
        self.assertEqual(self.window.last_results, [result])
        self.assertEqual(len(self.window.results_body.findChildren(ui.TeeTimeCard)), 1)
        self.assertEqual(self.window.status.text(), "1 matching tee time across 1 course")
        self.save.assert_not_called()

    def test_failure_while_closing_does_not_open_dialog_or_replace_body(self):
        worker = self.start_live()
        before = self.labels()
        self.window._closing = True
        self.fail(worker)
        self.assertEqual(self.labels(), before)
        self.dialog.assert_not_called()
        self.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
