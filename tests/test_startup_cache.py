"""Offscreen startup/fallback checks with actual files and intercepted scheduling."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-cached-startup-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

from app import shared_cache as cache
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
