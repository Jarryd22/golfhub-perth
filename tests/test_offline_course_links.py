"""Configured course-link recovery when every requested date lacks cache."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-offline-course-links-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app import shared_cache as cache
from app.qt_golfhub_app import DaySection, DirectCourseCard, GolfHub, ResultCard, TeeTimeCard
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class OfflineCourseLinkTests(unittest.TestCase):
    dates = ["2033-01-02", "2033-01-04", "2033-01-07"]
    unavailable = "No cached results were available for these dates. Try a shorter range or search again shortly."

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.runtime = self.enterContext(tempfile.TemporaryDirectory(dir=_runtime.name))
        self.enterContext(patch.object(cache, "LOCAL_CACHE_DIR", Path(self.runtime) / "cache"))
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                       "socket.getaddrinfo", "app.qt_golfhub_app.CacheWorker", "app.qt_golfhub_app.ScanWorker"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline test")))
        self.weather = self.enterContext(patch("app.course_results.get_weather_for_date",
                                              side_effect=AssertionError("No weather lookup")))
        self.browser = self.enterContext(patch("app.qt_golfhub_app.webbrowser.open", return_value=True))
        self.save = self.enterContext(patch("app.qt_golfhub_app.save_local_snapshot",
                                           side_effect=AssertionError("Recovery must not write cache")))
        self.enterContext(patch("app.qt_golfhub_app.perth_today", return_value=QDate(2033, 1, 2)))
        self.callback_errors = []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callback_errors.append(str(a[1]))))
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.sites = {site.name: site for site in self.window.sites}
        self.altone = self.sites["Altone Park"]
        self.boddington = self.sites["Boddington Golf Club"]
        self.live = self.sites["Araluen"]

    def tearDown(self):
        self.weather.assert_not_called()
        self.save.assert_not_called()
        self.assertIsNone(self.window.cache_thread)
        self.assertIsNone(self.window.scan_thread)
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [])

    def controls(self, sites, holes="18", dates=None):
        (self.window.holes9 if holes == "9" else self.window.holes18).setChecked(True)
        self.window.set_all(False)
        names = {site.name for site in sites}
        for row in self.window.course_rows:
            row.check.setChecked(row.site.name in names)
        self.window.date.set_dates([QDate.fromString(date, "yyyy-MM-dd") for date in dates or self.dates])

    def submit(self, sites, holes="18", dates=None):
        self.controls(sites, holes, dates)
        context = self.window.params()
        self.window.context = context
        self.window._active_cache_context = self.window._snapshot_search_context(context)
        return context

    def finish(self, snapshots=None):
        with patch.object(self.window, "search_live", side_effect=AssertionError("No multi-date live fallback")):
            self.window.cache_finished(snapshots or {})

    def cards(self):
        return self.window.results_body.findChildren(DirectCourseCard)

    def names(self):
        return [card.result["site_name"] for card in self.cards()]

    def assert_unavailable(self):
        labels = [label.text() for label in self.window.results_body.findChildren(QLabel)]
        self.assertEqual(self.window.status.text(), "Multi-day cache temporarily unavailable")
        self.assertEqual(self.window.header_status.text(), "SHARED CACHE UNAVAILABLE")
        self.assertEqual(labels.count(self.unavailable), 1)
        self.assertFalse(any("0 matching" in text or "0 loaded days" in text for text in labels))
        self.assertEqual(self.window.results_body.findChildren(QLabel, "SummaryValue"), [])

    def assert_one_trailing_stretch(self):
        layout = self.window.results_layout
        self.assertIsNotNone(layout.itemAt(layout.count() - 1).spacerItem())
        self.assertEqual(sum(layout.itemAt(i).spacerItem() is not None for i in range(layout.count())), 1)

    def test_direct_only_all_missing_keeps_unavailable_guidance_and_official_action(self):
        self.submit([self.altone])
        self.finish()
        self.assertEqual(self.names(), [self.altone.name])
        self.assert_unavailable()
        button = self.cards()[0].findChild(QPushButton)
        self.assertTrue(button.isEnabled())
        button.click()
        self.browser.assert_called_once_with(f"https://{self.altone.domain}")
        self.assertEqual(list(Path(self.runtime).rglob("*.json")), [])

    def test_mixed_selection_shows_only_selected_static_links_once_in_name_order(self):
        dates = [QDate(2033, 1, 2).addDays(offset).toString("yyyy-MM-dd") for offset in range(28)]
        self.submit([self.boddington, self.live, self.altone], dates=dates)
        self.finish({date: None for date in dates})
        self.assertEqual(self.names(), [self.altone.name, self.boddington.name])
        self.assert_unavailable()
        self.assertEqual(self.window.results_body.findChildren(ResultCard), [])
        self.assertEqual({c.result["url"] for c in self.cards()},
                         {f"https://{s.domain}" for s in (self.altone, self.boddington)})

    def test_integrated_only_all_missing_keeps_existing_unavailable_state(self):
        self.submit([self.live])
        self.finish()
        self.assertEqual(self.cards(), [])
        self.assert_unavailable()
        self.assert_one_trailing_stretch()
        self.assertEqual(self.window.results_body.findChildren(QPushButton), [])

    def test_submitted_courses_round_and_dates_override_pending_controls(self):
        embleton = self.sites["Embleton"]
        submitted = self.submit([self.altone, embleton], holes="9")
        self.controls([self.sites["Chequers"]], holes="18", dates=["2033-01-10"])
        # Even a replaced display context cannot supersede the active request.
        self.window.context = self.window.params()
        self.finish()
        self.assertEqual(self.names(), [self.altone.name, embleton.name])
        self.assertEqual(self.window.context, submitted)
        self.assertEqual({c.result["hole_label"] for c in self.cards()}, {"9 holes"})
        self.assert_unavailable()

    def test_round_eligibility_excludes_unsupported_configured_courses(self):
        selected = [self.altone, self.sites["Chequers"], self.sites["Embleton"]]
        for holes, expected in (("18", ["Altone Park", "Chequers"]),
                                ("9", ["Altone Park", "Embleton"])):
            with self.subTest(holes=holes):
                self.submit(selected, holes=holes)
                self.finish()
                self.assertEqual(self.names(), expected)
                self.assertEqual({c.result["hole_label"] for c in self.cards()}, {f"{holes} holes"})
                self.assert_unavailable()

    def test_repeated_unavailable_completions_do_not_duplicate_cards_or_layout(self):
        self.submit([self.altone, self.boddington])
        self.finish()
        self.finish()
        self.assertEqual(self.names(), [self.altone.name, self.boddington.name])
        self.assert_unavailable()
        self.assert_one_trailing_stretch()
        self.assertEqual([r["site_name"] for r in self.window.last_results], self.names())

    def test_all_missing_replaces_previous_loaded_days_rows_and_result_state(self):
        self.submit([self.live, self.altone])
        live = {"site_name": self.live.name, "url": f"https://{self.live.domain}", "hole_label": "18 holes",
                "error": None, "weather": None,
                "decorated_rows": [{"time": "9:00 am", "minutes": 540, "spots": 4}]}
        self.finish({self.dates[0]: cache.make_snapshot(self.dates[0], "18", [live])})
        self.assertEqual(len(self.window.results_body.findChildren(DaySection)), 3)
        self.assertEqual(len(self.window.results_body.findChildren(TeeTimeCard)), 1)
        self.submit([self.boddington], dates=["2033-01-10", "2033-01-12"])
        self.finish()
        self.assertEqual(self.names(), [self.boddington.name])
        self.assertEqual(self.window.results_body.findChildren(DaySection), [])
        self.assertEqual(self.window.results_body.findChildren(TeeTimeCard), [])
        self.assertEqual(self.window.day_sections, [])
        self.assertEqual([r["site_name"] for r in self.window.last_results], [self.boddington.name])
        self.assert_unavailable()
        self.assert_one_trailing_stretch()

    def test_range_actions_expose_course_and_round_without_an_invented_date(self):
        selected = [self.altone, self.sites["Serpentine & Districts"]]
        self.submit(selected)
        self.finish()
        self.assertEqual(len(self.cards()), 2)
        for card in self.cards():
            with self.subTest(course=card.result["site_name"]):
                button = card.findChild(QPushButton)
                expected = f"View course: {card.result['site_name']}, 18 holes"
                self.assertEqual(button.accessibleName(), expected)
                self.assertEqual(QAccessible.queryAccessibleInterface(button).text(QAccessible.Name), expected)
                self.assertEqual(button.text(), "VIEW COURSE")

    def test_partial_shared_and_saved_cache_keep_cached_link_metadata_and_missing_day(self):
        self.submit([self.altone])
        saved_url = f"https://{self.altone.domain}#saved-fixture"
        saved = {"site_name": self.altone.name, "url": saved_url, "hole_label": "18 holes",
                 "direct_booking": True, "decorated_rows": [], "error": None, "weather": None,
                 "booking_note": "Synthetic saved course information"}
        cache.save_local_snapshot(cache.make_snapshot(self.dates[0], "18", [saved]))
        self.finish({self.dates[1]: cache.make_snapshot(self.dates[1], "18", [])})
        self.assertEqual(self.names(), [self.altone.name])
        self.assertEqual(self.cards()[0].result["url"], saved_url)
        self.assertEqual(self.cards()[0].result["booking_note"], saved["booking_note"])
        self.assertEqual(self.window.header_status.text(), "SHARED CACHE / 2 OF 3 DAYS")
        self.assertIn("Availability not checked", self.window.day_sections[2].toggle.text())
        self.assertNotIn("Availability not checked", self.window.day_sections[0].toggle.text())
        self.cards()[0].findChild(QPushButton).click()
        self.browser.assert_called_once_with(saved_url)

    def test_single_date_without_cache_keeps_existing_live_fallback(self):
        for site in (self.altone, self.live):
            with self.subTest(course=site.name):
                submitted = self.submit([site], dates=self.dates[:1])
                with patch.object(self.window, "search_live") as live:
                    self.window.cache_finished({})
                live.assert_called_once_with(submitted)
                self.assertEqual(self.cards(), [])
