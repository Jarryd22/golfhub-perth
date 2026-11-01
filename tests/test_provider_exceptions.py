"""Offline producer-to-widget regressions for message-less provider failures."""
import os
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-provider-exceptions-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app import golfhub_core as core
from app.qt_golfhub_app import GolfHub, ResultCard, ScanWorker
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


class ProviderExceptionTests(unittest.TestCase):
    date = "2033-01-02"
    later_date = "2033-01-03"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(patch("socket.create_connection", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Offline test")))
        self.browser = self.enterContext(patch("app.qt_golfhub_app.webbrowser.open", return_value=True))
        self.enterContext(patch.object(core, "get_weather_for_date", return_value=None))
        self.enterContext(patch.object(core, "save_debug_html"))
        self.enterContext(patch("app.qt_golfhub_app.perth_today", return_value=QDate(2033, 1, 2)))
        self.callback_errors = []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callback_errors.append(str(a[1]))))
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.window.date.setDate(QDate(2033, 1, 2))
        self.window.set_all(False)
        next(r for r in self.window.course_rows if r.site.name == "Araluen").check.setChecked(True)
        self.sites = {site.name: site for site in self.window.sites}
        self.live = self.sites["Araluen"]
        self.wembley = self.sites["Wembley"]
        self.window.context = self.window.params()
        self.workers = []

    def tearDown(self):
        for worker in self.workers:
            worker.deleteLater()
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [], "Qt callbacks must not raise")

    def failure_result(self, site, failure, date=None):
        fetch_name = "fetch_text" if site is self.wembley else "fetch_site_text"
        with patch.object(core, fetch_name, side_effect=failure) as fetch:
            result = core.fetch_site_result(site, date or self.date, "18", None, None, None)
        fetch.assert_called_once()
        return result

    def successful_empty(self, date=None):
        with patch.object(core, "fetch_site_text", return_value="<html><body>No tee times</body></html>") as fetch:
            result = core.fetch_site_result(self.live, date or self.date, "18", None, None, None)
        fetch.assert_called_once()
        return result

    def context(self, sites, dates):
        self.window.context = {"sites": sites, "date": dates[0], "dates": dates,
                               "holes": "18", "players": None, "from": None, "to": None}

    def headline(self):
        return self.window.results_layout.itemAt(0).widget().findChild(QLabel, "SummaryValue").text()

    def test_regular_provider_keeps_empty_or_whitespace_exception_as_failure(self):
        for failure in (TimeoutError(), ValueError(" \n\t"), RuntimeError("")):
            with self.subTest(exception=repr(failure)):
                result = self.failure_result(self.live, failure)
                self.assertEqual(result["error"], type(failure).__name__)
                self.assertEqual(result["decorated_rows"], [])
                self.assertTrue(result["url"])

    def test_wembley_calendar_keeps_empty_or_whitespace_exception_as_failure(self):
        for failure in (TimeoutError(), ValueError(" \n\t")):
            with self.subTest(exception=repr(failure)):
                result = self.failure_result(self.wembley, failure)
                self.assertEqual(result["error"], type(failure).__name__)
                self.assertEqual(result["decorated_rows"], [])
                self.assertTrue(result["url"])

    def test_nonblank_provider_messages_are_preserved_exactly(self):
        message = "  Synthetic provider timeout\nrequest details  "
        for site in (self.live, self.wembley):
            with self.subTest(course=site.name):
                self.assertEqual(self.failure_result(site, TimeoutError(message))["error"], message)

    def test_successful_empty_response_remains_known_empty(self):
        result = self.successful_empty()
        self.assertIsNone(result["error"])
        self.assertEqual(result["decorated_rows"], [])
        self.context([self.live], [self.date])
        self.window.render_results([result], "Synthetic successful response")
        self.assertEqual(self.headline(), "0 matching times")
        self.assertEqual(self.window.results_body.findChildren(ResultCard), [])
        self.assertEqual(self.window.results_body.findChildren(QLabel, "Warning"), [])

    def test_successful_second_page_keeps_rows_after_first_page_exception(self):
        first = "https://example.invalid/first"
        second = "https://example.invalid/second"
        row = {"time": "9:00 am", "spots": 4, "course_raw": "Araluen"}
        with (
            patch.object(core.Site, "build_urls", return_value=[first, second]),
            patch.object(core, "fetch_site_text", side_effect=[TimeoutError(), "<html>fixture</html>"]) as fetch,
            patch.object(core, "parse_timesheet", return_value=[row]),
        ):
            result = core.fetch_site_result(self.live, self.date, "18", None, None, None)
        self.assertEqual(fetch.call_count, 2)
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["decorated_rows"]), 1)
        self.assertEqual(result["decorated_rows"][0]["source_url"], second)

    def test_core_failures_render_incomplete_with_error_card_and_booking_link(self):
        for site in (self.live, self.wembley):
            with self.subTest(course=site.name):
                result = self.failure_result(site, TimeoutError())
                self.context([site], [self.date])
                self.window.render_snapshot(make_snapshot(self.date, "18", [result]), "Shared cache")
                self.assertEqual(self.headline(), "Availability incomplete")
                self.assertEqual(self.window.status.text(), "Availability could not be checked for 1 course")
                cards = self.window.results_body.findChildren(ResultCard)
                self.assertEqual(len(cards), 1)
                button = next(b for b in cards[0].findChildren(QPushButton) if b.text() == "OPEN BOOKING PAGE")
                self.browser.reset_mock()
                button.click()
                self.browser.assert_called_once_with(result["url"])

    def test_core_failure_and_successful_empty_dates_remain_distinct(self):
        failure = self.failure_result(self.live, TimeoutError())
        empty = self.successful_empty(self.later_date)
        self.context([self.live], [self.date, self.later_date])
        self.window.render_snapshot_batch(
            {self.date: make_snapshot(self.date, "18", [failure]),
             self.later_date: make_snapshot(self.later_date, "18", [empty])},
            {self.date: "Shared cache", self.later_date: "Shared cache"},
        )
        self.assertEqual(self.headline(), "Availability incomplete across 2 days")
        self.assertIn("Availability incomplete - 1 course unavailable", self.window.day_sections[0].toggle.text())
        self.assertIn("No matching live times", self.window.day_sections[1].toggle.text())
        self.window.day_sections[1].set_expanded(True)
        self.assertIn("No live tee times matched these filters on this day.",
                      [label.text() for label in self.window.day_sections[1].findChildren(QLabel)])

    def run_worker(self, side_effect):
        worker = ScanWorker([self.live], self.date, "18", None, None, None)
        self.workers.append(worker)
        finished, failed = [], []
        worker.finished.connect(lambda results, cancelled: finished.append((results, cancelled)))
        worker.failed.connect(failed.append)
        with patch.object(worker, "_fetch", side_effect=side_effect) as fetch:
            worker.run()
        fetch.assert_called_once_with(self.live)
        self.assertEqual(failed, [])
        self.assertEqual(len(finished), 1)
        self.assertFalse(finished[0][1])
        return finished[0][0][0]

    def test_worker_escape_catch_retains_empty_or_whitespace_exception(self):
        for failure in (TimeoutError(), ValueError(" \n\t")):
            with self.subTest(exception=repr(failure)):
                result = self.run_worker(failure)
                self.assertEqual(result["error"], type(failure).__name__)
                self.context([self.live], [self.date])
                self.window.render_results([result], "Synthetic live worker")
                self.assertEqual(self.headline(), "Availability incomplete")

    def test_worker_preserves_named_failure_and_successful_empty(self):
        message = "  Synthetic timeout\nwith details  "
        result = self.run_worker(TimeoutError(message))
        self.assertEqual(result["error"], message)
        empty = self.successful_empty()
        result = self.run_worker(lambda site: empty)
        self.assertEqual(result, empty)
        self.assertIsNone(result["error"])
