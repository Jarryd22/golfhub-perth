"""Offline regressions for link guidance in filtered, successful empty results."""
import os
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-empty-result-links-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from app import qt_golfhub_app as ui
from app.shared_cache import make_snapshot
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class EmptyResultLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.errors = []
        for target in ("socket.create_connection", "socket.socket.connect", "socket.getaddrinfo",
                       "app.qt_golfhub_app.ScanWorker", "app.qt_golfhub_app.CacheWorker",
                       "app.course_results.get_weather_for_date", "app.qt_golfhub_app.save_local_snapshot"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline test")))
        self.browser = self.enterContext(patch("webbrowser.open", return_value=True))
        self.enterContext(patch("sys.excepthook", side_effect=lambda *args: self.errors.append(str(args[1]))))
        self.enterContext(patch.object(ui, "perth_today", return_value=QDate(2033, 1, 2)))
        with patch.object(ui.GolfHub, "show_initial_cache"):
            self.window = ui.GolfHub()
        self.window._stop_deferred_timers()
        self.sites = {site.name: site for site in self.window.sites}
        self.select(["Araluen"])

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.errors, [], "Qt callbacks must not raise")

    def select(self, names, players="Any", preset="Any time"):
        self.window.date.set_dates([QDate(2033, 1, 2)])
        self.window.set_all(False)
        for row in self.window.course_rows:
            row.check.setChecked(row.site.name in names)
        self.window.players.setCurrentText(players)
        self.window.time_preset.setCurrentText(preset)
        self.window.context = self.window.params()
        self.window._active_cache_context = self.window._snapshot_search_context(self.window.context)

    @staticmethod
    def result(name="Araluen", rows=(), **extra):
        return {"site_name": name, "url": "https://example.invalid/booking",
                "hole_label": "18 holes", "decorated_rows": list(rows),
                "weather": None, "error": None, **extra}

    @staticmethod
    def row():
        return {"time": "9:00 am", "minutes": 540, "spots": 2}

    def cached(self, rows=()):
        self.window.cache_finished({"2033-01-02": make_snapshot(
            "2033-01-02", "18", [self.result(rows=rows)])})

    def empty_message(self):
        frames = self.window.results_body.findChildren(QFrame, "EmptyState")
        self.assertEqual(len(frames), 1)
        return frames[0].findChild(QLabel, "Muted").text()

    def assert_no_link_promise(self):
        message = self.empty_message()
        self.assertIn("No live tee times matched these filters.", message)
        self.assertIn("Try Any time or Any players, or use Refresh Live.", message)
        self.assertNotIn("Official course links", message)
        self.assertEqual(self.window.results_body.findChildren(ui.DirectCourseCard), [])
        self.assertEqual(self.window.results_body.findChildren(QPushButton), [])

    def test_group_and_time_exclusions_do_not_promise_absent_links(self):
        for players, preset in (("4", "Any time"), ("Any", "Afternoon")):
            with self.subTest(players=players, preset=preset):
                self.select(["Araluen"], players, preset)
                self.cached([self.row()])
                self.assert_no_link_promise()

    def test_checked_empty_integrated_course_does_not_promise_links(self):
        self.cached()
        self.assert_no_link_promise()

    def test_mixed_selection_keeps_guidance_and_actual_link_handoff(self):
        self.select(["Araluen", "Altone Park"], "4")
        self.cached([self.row()])
        self.assertIn("Official course links remain available below.", self.empty_message())
        cards = self.window.results_body.findChildren(ui.DirectCourseCard)
        self.assertEqual(len(cards), 1)
        button = cards[0].findChild(QPushButton)
        self.assertIn("Altone Park", button.accessibleName())
        button.click()
        self.browser.assert_called_once_with("https://www.altoneparkgolfcourse.com.au")

    def test_unselected_direct_result_does_not_create_a_link_promise(self):
        self.window.render_results([
            self.result(), self.result("Altone Park", direct_booking=True)
        ], "Synthetic cache")
        self.assert_no_link_promise()

    def test_replacing_mixed_results_removes_link_and_its_promise(self):
        self.select(["Araluen", "Altone Park"], "4")
        self.cached([self.row()])
        self.assertIn("Official course links", self.empty_message())
        self.select(["Araluen"], "4")
        self.cached([self.row()])
        self.assert_no_link_promise()

    def test_direct_only_selection_retains_actionable_link_guidance(self):
        self.select(["Altone Park"])
        self.cached()
        self.assertIn("Official course links remain available below.", self.empty_message())
        self.assertEqual(len(self.window.results_body.findChildren(ui.DirectCourseCard)), 1)

    def test_matching_rows_and_provider_error_cards_do_not_show_empty_guidance(self):
        for result in (self.result(rows=[self.row()]), self.result(error="Synthetic provider failure")):
            with self.subTest(error=result["error"]):
                self.window.render_results([result], "Synthetic cache")
                self.assertEqual(self.window.results_body.findChildren(QFrame, "EmptyState"), [])
                self.assertEqual(len(self.window.results_body.findChildren(ui.ResultCard)), 1)


if __name__ == "__main__":
    unittest.main()
