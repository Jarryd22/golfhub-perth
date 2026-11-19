"""Offscreen startup/fallback checks with actual files and intercepted scheduling."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-cached-startup-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QElapsedTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app import shared_cache as cache
from app import qt_golfhub_app as ui
from app.qt_golfhub_app import GolfHub
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class CachedStartupTests(unittest.TestCase):
    date = "2033-01-02"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.runtime = self.enterContext(tempfile.TemporaryDirectory(dir=_runtime.name))
        self.enterContext(patch.object(cache, "LOCAL_CACHE_DIR", Path(self.runtime) / "cache"))
        for target in ("socket.create_connection", "socket.socket.connect", "webbrowser.open",
                       "app.qt_golfhub_app.CacheWorker", "app.qt_golfhub_app.ScanWorker"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline test: no workers or network")))
        self.enterContext(patch("app.qt_golfhub_app.perth_today", return_value=QDate(2033, 1, 2)))
        self.callback_errors = []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *args: self.callback_errors.append(str(args[1]))))
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.schedule = self.enterContext(patch.object(self.window._cache_search_timer, "start"))
        self.window.date.setDate(QDate(2033, 1, 2))
        self.window.set_all(False)
        next(row for row in self.window.course_rows if row.site.name == "Araluen").check.setChecked(True)
        self.path = cache.local_snapshot_path(self.date, "18")

    def tearDown(self):
        self.assertIsNone(self.window.cache_thread)
        self.assertIsNone(self.window.scan_thread)
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [])

    @staticmethod
    def result(**extra):
        return {"site_name": "Araluen", "url": "https://example.invalid/booking", "hole_label": "18 holes",
                "decorated_rows": [], "weather": None, "error": None, **extra}

    def snapshot(self, *results):
        return cache.make_snapshot(self.date, "18", list(results))

    def write_raw(self, payload):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def headline(self):
        return self.window.results_layout.itemAt(0).widget().findChild(QLabel, "SummaryValue").text()

    def assert_startup_recovers(self, payload):
        self.write_raw(payload)
        original = self.path.read_bytes()
        self.schedule.reset_mock()
        self.window.show_initial_cache()
        self.schedule.assert_called_once_with(100)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertNotIn("SAVED CACHE", self.window.header_status.text())

    def test_valid_shared_data_wins_over_saved_or_missing_data_when_write_fails(self):
        self.window.players.setCurrentText("4")
        previous = self.snapshot(self.result(decorated_rows=[{"time": "8:00 am", "minutes": 480, "spots": 2}]))
        fresh = self.snapshot(self.result(decorated_rows=[{"time": "9:00 am", "minutes": 540, "spots": 4}]))
        for saved in (True, False):
            with self.subTest(saved=saved):
                if saved:
                    self.write_raw(previous)
                else:
                    self.path.unlink(missing_ok=True)
                original = self.path.read_bytes() if saved else None
                with (
                    patch.object(cache, "_cache_base_url", return_value="https://example.invalid/cache"),
                    patch.object(cache.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(fresh).encode())),
                    patch.object(Path, "write_text", side_effect=OSError("Synthetic disk full")),
                ):
                    fetched = cache.fetch_shared_snapshot(self.date, "18")
                self.window.context = self.window.params()
                with patch.object(self.window, "search_live") as live:
                    self.window.cache_finished({self.date: fetched})
                live.assert_not_called()
                self.assertEqual(self.headline(), "1 matching time")
                self.assertTrue(self.window.header_status.text().startswith("SHARED CACHE /"))
                self.assertEqual(self.window.last_results, fresh["results"])
                self.assertEqual(self.path.read_bytes() if self.path.exists() else None, original)

    def test_multiday_shared_results_remain_loaded_when_local_writes_fail(self):
        self.window.players.setCurrentText("4")
        self.window.date.set_dates([QDate(2033, 1, 2), QDate(2033, 1, 4)])
        previous = self.snapshot(self.result(decorated_rows=[{"time": "8:00 am", "minutes": 480, "spots": 2}]))
        self.write_raw(previous)
        original = self.path.read_bytes()
        fresh = {date: cache.make_snapshot(date, "18", [self.result(
            decorated_rows=[{"time": "9:00 am", "minutes": 540, "spots": 4}])])
                 for date in (self.date, "2033-01-04")}
        with (
            patch.object(cache, "_cache_base_url", return_value="https://example.invalid/cache"),
            patch.object(cache.urllib.request, "urlopen", side_effect=[io.BytesIO(json.dumps(p).encode()) for p in fresh.values()]),
            patch.object(Path, "write_text", side_effect=OSError("Synthetic disk full")),
        ):
            fetched = {date: cache.fetch_shared_snapshot(date, "18") for date in fresh}
        self.window.context = self.window.params()
        with patch.object(self.window, "search_live") as live:
            self.window.cache_finished(fetched)
        live.assert_not_called()
        self.assertEqual(self.headline(), "2 matching times across 2 days")
        self.assertEqual(self.window.header_status.text(), "SHARED CACHE / 2 OF 2 DAYS")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(cache.local_snapshot_path("2033-01-04", "18").exists())

    def test_nonobject_saved_results_do_not_abort_scheduled_shared_check(self):
        for invalid in (None, "course record"):
            with self.subTest(record=invalid):
                self.assert_startup_recovers({**self.snapshot(), "results": [invalid]})

    def test_malformed_saved_rows_do_not_abort_scheduled_shared_check(self):
        for invalid in ({"minutes": 540}, [None], ["row record"]):
            with self.subTest(rows=invalid):
                self.assert_startup_recovers(self.snapshot(self.result(decorated_rows=invalid)))

    def test_valid_saved_states_render_before_scheduled_refresh(self):
        cases = [
            ([], "0 matching times"),
            ([self.result(decorated_rows=None)], "0 matching times"),
            ([self.result(error="Provider unavailable")], "Availability incomplete"),
            ([self.result(decorated_rows=[{"time": "9:00 am", "minutes": 540, "spots": 4}])], "1 matching time"),
        ]
        for results, expected in cases:
            with self.subTest(results=results):
                self.write_raw(self.snapshot(*results))
                self.schedule.reset_mock()
                self.window.show_initial_cache()
                self.schedule.assert_called_once_with(100)
                self.assertEqual(self.headline(), expected)
                self.assertTrue(self.window.header_status.text().startswith("SAVED CACHE /"))
                self.assertEqual(self.window.context["date"], self.date)

    def test_absent_or_invalid_json_cache_still_schedules_shared_check(self):
        self.window.show_initial_cache()
        self.schedule.assert_called_once_with(100)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{unfinished", encoding="utf-8")
        self.schedule.reset_mock()
        self.window.show_initial_cache()
        self.schedule.assert_called_once_with(100)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{unfinished")

    def test_invalid_download_falls_back_to_existing_saved_result_without_live_worker(self):
        valid = self.snapshot(self.result(decorated_rows=[{"time": "9:00 am", "minutes": 540, "spots": 4}]))
        cache.save_local_snapshot(valid)
        original = self.path.read_bytes()
        invalid = {**valid, "results": [None]}
        with (
            patch.object(cache, "_cache_base_url", return_value="https://example.invalid/cache"),
            patch.object(cache.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(invalid).encode())),
        ):
            fetched = cache.fetch_shared_snapshot(self.date, "18")
        self.window.context = self.window.params()
        with patch.object(self.window, "search_live", side_effect=AssertionError("Saved fallback must avoid live search")):
            self.window.cache_finished({self.date: fetched})
        self.assertEqual(self.headline(), "1 matching time")
        self.assertTrue(self.window.header_status.text().startswith("SAVED CACHE /"))
        self.assertEqual(self.path.read_bytes(), original)


class StartupSearchSchedulingTests(unittest.TestCase):
    """Accepted searches supersede startup work without changing other timers."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.runtime = self.enterContext(tempfile.TemporaryDirectory(dir=_runtime.name))
        self.enterContext(patch.object(cache, "LOCAL_CACHE_DIR", Path(self.runtime) / "cache"))
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                       "socket.getaddrinfo", "webbrowser.open", "app.qt_golfhub_app.fetch_site_result",
                       "app.course_results.get_weather_for_date", "app.qt_golfhub_app.BookingAssistDialog",
                       "app.qt_golfhub_app.ScanWorker.run", "app.qt_golfhub_app.CacheWorker.run"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline startup scheduling test")))
        self.enterContext(patch.object(ui, "perth_today", return_value=QDate(2033, 1, 2)))
        self.enterContext(patch.object(ui.QMessageBox, "information"))
        self.enterContext(patch.object(ui.QMessageBox, "exec"))
        self.save = self.enterContext(patch.object(ui, "save_local_snapshot"))
        self.callbacks, self.threads, self.workers = [], [], []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callbacks.append(str(a[1]))))

        def thread_factory():
            thread = MagicMock()
            thread.isRunning.return_value = True
            thread.wait.return_value = True
            self.threads.append(thread)
            return thread

        def worker_factory(worker_type):
            def create(*args, **kwargs):
                worker = worker_type(*args, **kwargs)
                self.workers.append(worker)
                return worker
            return create

        self.enterContext(patch.object(ui, "QThread", side_effect=thread_factory))
        for name in ("CacheWorker", "ScanWorker"):
            worker_type = getattr(ui, name)
            self.enterContext(patch.object(worker_type, "moveToThread"))
            self.enterContext(patch.object(ui, name, side_effect=worker_factory(worker_type)))
        self.window = GolfHub()
        self.window.set_all(False)
        self.course = next(row for row in self.window.course_rows if row.site.name == "Araluen")
        self.course.check.setChecked(True)
        self.controls("2033-01-03", "18", 4)
        self.saved = cache.make_snapshot("2033-01-03", "18", [self.result()])
        self.path = cache.save_local_snapshot(self.saved)
        self.saved_bytes = self.path.read_bytes()

    def tearDown(self):
        # Workers/signals are real QObjects; no native thread/body ever runs.
        # Release inert owners before closing, so the production close guard
        # does not intentionally keep this test window alive.
        self.window.scan_thread = self.window.scan_worker = None
        self.window.cache_thread = self.window.cache_worker = None
        self.window._closing = False
        self.window._stop_deferred_timers()
        for worker in self.workers:
            worker.deleteLater()
        cleanup_qt_widgets()
        self.assertEqual(self.callbacks, [], "Qt callbacks must not raise")
        self.assertEqual(self.path.read_bytes(), self.saved_bytes)

    def controls(self, date, holes, players):
        self.window.date.set_dates([QDate.fromString(date, "yyyy-MM-dd")])
        (self.window.holes9 if holes == "9" else self.window.holes18).setChecked(True)
        self.window.players.setCurrentText(str(players))
        self.window.time_preset.setCurrentText("Any time")

    @staticmethod
    def result():
        return {"site_name": "Araluen", "url": "https://example.invalid/2033-01-03/18",
                "hole_label": "18 holes", "error": None, "weather": None,
                "decorated_rows": [{"time": "9:00 am", "minutes": 540, "spots": 4}]}

    def start_saved_phase(self):
        self.window._initial_cache_timer.stop()
        self.window.show_initial_cache()
        self.assertTrue(self.window.header_status.text().startswith("SAVED CACHE /"))
        self.assertTrue(self.window._cache_search_timer.isActive())
        self.assertEqual(self.window._cache_search_timer.interval(), 100)

    def allow_startup_deadline(self):
        # Wait for the owned 0/100ms timers to fire or be cancelled. Initial
        # saved-result layout can take time before the 100ms timer is started.
        elapsed = QElapsedTimer()
        elapsed.start()
        def startup_pending():
            return self.window._initial_cache_timer.isActive() or self.window._cache_search_timer.isActive()
        while startup_pending() and elapsed.elapsed() < 1000:
            QTest.qWait(10)
        self.assertFalse(startup_pending(), "Deferred startup must complete or be cancelled within one second")
        self.app.processEvents()
        self.assertEqual(self.callbacks, [])

    def assert_live_context_survives_startup(self):
        scroll_pending = self.window._scroll_timer.isActive()
        self.window.live_button.click()
        worker = self.window.scan_worker
        self.assertIsNotNone(worker)
        self.window.scan_thread.start.assert_called_once()
        self.assertTrue(self.window._perth_date_timer.isActive())
        self.assertEqual(self.window._scroll_timer.isActive(), scroll_pending)
        self.controls("2033-01-04", "9", 1)
        self.allow_startup_deadline()
        worker.finished.emit([self.result()], False)
        self.save.assert_called_once()
        payload = self.save.call_args.args[0]
        self.assertEqual((payload["date"], payload["holes"]), ("2033-01-03", "18"))
        self.assertEqual(payload["results"], [self.result()])
        self.assertEqual((self.window.context["date"], self.window.context["holes"], self.window.context["players"]),
                         ("2033-01-03", "18", 4))
        self.assertEqual(len(self.threads), 1)
        self.assertIsNone(self.window.cache_thread)
        book = next(b for b in self.window.results_body.findChildren(QPushButton) if b.text() == "BOOK")
        self.assertIn("3 January 2033", book.accessibleName())
        self.assertNotIn("4 January 2033", book.accessibleName())

    def assert_find_context_survives_startup(self):
        self.window.search_button.click()
        worker = self.window.cache_worker
        self.assertIsNotNone(worker)
        self.window.cache_thread.start.assert_called_once()
        self.assertTrue(self.window._perth_date_timer.isActive())
        self.controls("2033-01-04", "9", 1)
        self.allow_startup_deadline()
        self.assertIsNone(self.window._pending_cache_context, "Unsubmitted edits must not become a queued search")
        worker.finished.emit({"2033-01-03": self.saved})
        self.assertEqual(self.window.context["date"], "2033-01-03")
        self.assertEqual(self.window.context["holes"], "18")
        self.assertEqual(self.window.last_results, self.saved["results"])
        self.assertEqual(len(self.threads), 1)
        self.save.assert_not_called()

    def test_live_before_initial_callback_keeps_submitted_save_and_booking_context(self):
        self.assertTrue(self.window._initial_cache_timer.isActive())
        self.assert_live_context_survives_startup()

    def test_live_after_saved_startup_keeps_submitted_save_and_booking_context(self):
        self.start_saved_phase()
        self.assertTrue(self.window._scroll_timer.isActive())
        self.assert_live_context_survives_startup()

    def test_find_before_initial_callback_does_not_queue_unsubmitted_edits(self):
        self.assertTrue(self.window._initial_cache_timer.isActive())
        self.assert_find_context_survives_startup()

    def test_find_after_saved_startup_does_not_queue_unsubmitted_edits(self):
        self.start_saved_phase()
        self.assert_find_context_survives_startup()

    def test_explicit_queued_find_survives_later_startup_deadline(self):
        self.start_saved_phase()
        self.window._start_cache_search(self.window.params())
        old_worker = self.window.cache_worker
        self.controls("2033-01-04", "9", 1)
        self.window.search_button.click()
        self.controls("2033-01-05", "18", 4)
        self.allow_startup_deadline()
        self.assertEqual((self.window._pending_cache_context["date"], self.window._pending_cache_context["holes"]),
                         ("2033-01-04", "9"))
        old_worker.finished.emit({"2033-01-03": self.saved})
        self.window.cache_thread_done()
        self.assertEqual((self.window.context["date"], self.window.context["holes"], self.window.context["players"]),
                         ("2033-01-04", "9", 1))
        self.assertEqual(len(self.threads), 2)
        for thread in self.threads:
            thread.start.assert_called_once()
        self.assertIsNone(self.window._pending_cache_context)

    def test_uninterrupted_startup_renders_saved_data_and_starts_one_shared_search(self):
        with patch.object(self.window, "render_snapshot", wraps=self.window.render_snapshot) as render:
            self.allow_startup_deadline()
        self.assertGreaterEqual(render.call_count, 1)
        self.assertEqual(render.call_args_list[0].args, (self.saved, "Saved on this device"))
        self.assertEqual(len(self.threads), 1)
        self.window.cache_thread.start.assert_called_once()
        self.assertIsNone(self.window.scan_thread)
        self.assertEqual((self.window.context["date"], self.window.context["holes"]), ("2033-01-03", "18"))
        self.window.cache_worker.finished.emit({"2033-01-03": self.saved})
        self.assertEqual(self.window.last_results, self.saved["results"])
        self.assertTrue(self.window.header_status.text().startswith("SHARED CACHE /"))
        self.assertTrue(self.window._perth_date_timer.isActive())
        self.save.assert_not_called()

    def test_invalid_and_refused_requests_preserve_scheduled_startup(self):
        def assert_timers_unchanged(initial, shared):
            self.assertEqual(self.window._initial_cache_timer.isActive(), initial)
            self.assertEqual(self.window._cache_search_timer.isActive(), shared)
            self.assertEqual(self.threads, [])

        for phase in ("initial", "shared"):
            with self.subTest(phase=phase):
                if phase == "shared":
                    self.start_saved_phase()
                expected = (phase == "initial", phase == "shared")
                self.course.check.setChecked(False)
                self.window.search_cache()
                self.window.search_live()
                assert_timers_unchanged(*expected)
                self.course.check.setChecked(True)
                self.window.time_preset.setCurrentText("Custom range")
                self.window.time_from.setCurrentText("3:00 pm")
                self.window.time_to.setCurrentText("9:00 am")
                self.window.search_cache()
                self.window.search_live()
                assert_timers_unchanged(*expected)
                self.window.time_preset.setCurrentText("Any time")
                self.window.date.set_dates([QDate(2033, 1, 3), QDate(2033, 1, 4)])
                self.window.search_live()
                assert_timers_unchanged(*expected)
                self.window.date.set_dates([QDate(2033, 1, 3)])
                self.window.scan_thread = MagicMock()
                self.window.search_live()
                assert_timers_unchanged(*expected)
                self.window.scan_thread = None
                self.window._closing = True
                self.window.search_cache()
                self.window.search_live()
                assert_timers_unchanged(*expected)
                self.window._closing = False
        self.allow_startup_deadline()
        self.assertEqual(len(self.threads), 1)
        self.assertIsNotNone(self.window.cache_worker)

    def test_close_before_initial_callback_prevents_startup_work(self):
        self.assertTrue(self.window._initial_cache_timer.isActive())
        self.window.close()
        self.allow_startup_deadline()
        self.assertEqual(self.threads, [])
        self.assertIsNone(self.window.cache_worker)
        self.assertIsNone(self.window.scan_worker)
        self.assertFalse(self.window._initial_cache_timer.isActive())
        self.assertFalse(self.window._cache_search_timer.isActive())
        self.save.assert_not_called()
