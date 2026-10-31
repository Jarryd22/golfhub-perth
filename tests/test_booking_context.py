"""Offline regressions for identifying repeated booking and course actions."""
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from app.qt_golfhub_app import DirectCourseCard, GolfHub, ResultCard, TeeTimeCard
from tests.qt_test_support import cleanup_qt_widgets


class BookingContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("socket.create_connection", side_effect=AssertionError("Offline test")).start()
        patch("socket.socket.connect", side_effect=AssertionError("Offline test")).start()
        self.browser = patch("app.qt_golfhub_app.webbrowser.open").start()
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.window.context = self.window.params()
        self.window.context.update(date="2026-10-20", dates=["2026-10-20"])
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        cleanup_qt_widgets()

    def result(self, name="Araluen", holes="18", **changes):
        row = {"time": "10:00 am", "minutes": 600, "spots": 4,
               "source_url": "https://example.invalid/tee-time"}
        return {"site_name": name, "hole_label": f"{holes} holes",
                "url": "https://example.invalid/course", "decorated_rows": [row],
                "weather": None, **changes}

    def name(self, button):
        interface = QAccessible.queryAccessibleInterface(button)
        self.assertEqual(interface.text(QAccessible.Name), button.accessibleName())
        return interface.text(QAccessible.Name)

    def book_button(self, parent):
        return next(b for b in parent.findChildren(QPushButton) if b.text() == "BOOK")

    def test_single_day_book_exposes_submitted_context_and_keeps_keyboard_handoff(self):
        result = self.result()
        handler = Mock()
        submitted_context = dict(self.window.context)
        with patch.object(self.window, "open_tee_time", handler):
            self.window.render_results([result], "Fixture")
        # Changing an unsubmitted filter must not rename the displayed result.
        self.window.date.setDate(self.window.date.minimumDate().addDays(3))
        button = self.book_button(self.window.results_body)
        self.assertEqual(self.name(button), "Book: Araluen, 10:00 am, 18 holes, 20 October 2026")
        button.setFocus()
        self.app.processEvents()
        self.assertTrue(button.hasFocus())
        QTest.keyClick(button, Qt.Key_Space)
        handler.assert_called_once_with(result, result["decorated_rows"][0], context=submitted_context)
        self.browser.assert_not_called()

    def test_repeated_times_distinguish_course_and_round_without_changing_visible_text(self):
        names = []
        for course, holes in [("Araluen", "18"), ("Collier Park", "18"), ("Araluen", "9")]:
            result = self.result(course, holes)
            card = ResultCard(result, result["decorated_rows"])
            button = self.book_button(card)
            names.append(self.name(button))
            self.assertEqual(names[-1], f"Book: {course}, 10:00 am, {holes} holes")
            self.assertEqual(button.text(), "BOOK")
        self.assertEqual(len(set(names)), 3)

    def test_lazy_days_keep_their_own_dates_when_opened_after_filters_change(self):
        result = self.result()
        dates = ["2026-10-20", "2026-10-23", "2026-11-01"]
        self.window.context["dates"] = dates
        days = [{"date": date, "results": [result], "source": "Fixture"} for date in dates]
        self.window.render_multi_results(days, "Fixture")
        self.assertFalse(self.window.day_sections[1]._built)
        self.window.context = dict(self.window.context, date="2026-11-15", dates=["2026-11-15"])
        for section, date in zip(self.window.day_sections, ["20 October 2026", "23 October 2026", "1 November 2026"]):
            section.set_expanded(True)
            button = self.book_button(section)
            self.assertEqual(self.name(button), f"Book: Araluen, 10:00 am, 18 holes, {date}")
            course_button = next(b for b in section.findChildren(QPushButton) if b.text() == "OPEN BOOKING PAGE")
            self.assertEqual(self.name(course_button), f"Open booking page: Araluen, 18 holes, {date}")

    def test_course_action_variants_have_context_and_preserve_official_handoffs(self):
        cases = [
            (self.result(), "OPEN BOOKING PAGE", "Open booking page", "https://example.invalid/course"),
            (self.result(error="Offline", decorated_rows=[]), "OPEN BOOKING PAGE", "Open booking page", "https://example.invalid/course"),
            (self.result("Wembley", calendar_availability="available"), "VIEW WEMBLEY TIMES", "View Wembley times", "https://example.invalid/course"),
            (self.result("Collier Park", decorated_rows=[], official_calendar_url="https://example.invalid/calendar"), "VIEW OFFICIAL CALENDAR", "View official calendar", "https://example.invalid/calendar"),
            (self.result("Serpentine & Districts", direct_booking=True), "VIEW COURSE", "View course", "https://example.invalid/course"),
        ]
        for result, visible, action, url in cases:
            with self.subTest(action=action, course=result["site_name"], error=result.get("error")):
                card = ResultCard(result, result["decorated_rows"])
                button = next(b for b in card.findChildren(QPushButton) if b.text() == visible)
                self.assertEqual(self.name(button), f"{action}: {result['site_name']}, 18 holes")
                button.click()
                self.browser.assert_called_with(url)
        self.assertEqual(self.browser.call_count, len(cases))

    def test_direct_course_links_preserve_literal_ampersands_and_single_day_context(self):
        name = next(s.name for s in self.window.sites if "&" in s.name)
        result = self.result(name, direct_booking=True, decorated_rows=[])
        self.window.render_results([result], "Fixture")
        card = self.window.results_body.findChild(DirectCourseCard)
        button = card.findChild(QPushButton)
        self.assertEqual(button.text(), "VIEW COURSE")
        self.assertEqual(self.name(button), f"View course: {name}, 18 holes, 20 October 2026")
        button.click()
        self.browser.assert_called_once_with(result["url"])

    def test_range_course_link_has_no_invented_single_date(self):
        result = self.result(direct_booking=True, decorated_rows=[])
        self.window.context["dates"] = ["2026-10-20", "2026-10-23"]
        self.window.render_multi_results([
            {"date": date, "results": [result], "source": "Fixture"}
            for date in self.window.context["dates"]
        ], "Fixture")
        cards = self.window.results_body.findChildren(DirectCourseCard)
        self.assertEqual(len(cards), 1)
        self.assertEqual(self.name(cards[0].findChild(QPushButton)), "View course: Araluen, 18 holes")

    def test_missing_context_is_not_invented_and_row_url_still_wins(self):
        row = {"time": "9:00 am", "source_url": "https://example.invalid/row"}
        card = TeeTimeCard(row, "https://example.invalid/fallback")
        button = self.book_button(card)
        self.assertEqual(self.name(button), "Book: Golf course, 9:00 am")
        button.click()
        self.browser.assert_called_once_with(row["source_url"])
        empty = TeeTimeCard({}, None)
        self.assertEqual(self.name(self.book_button(empty)), "Book: Golf course")

    def test_show_all_action_keeps_course_date_context_after_toggle(self):
        result = self.result()
        result["decorated_rows"] = [dict(result["decorated_rows"][0]) for _ in range(13)]
        self.window.render_results([result], "Fixture")
        card = self.window.results_body.findChild(ResultCard)
        button = card.more_button
        self.assertEqual(button.text(), "SHOW ALL 13 TIMES")
        self.assertEqual(self.name(button), "Show All 13 Times: Araluen, 18 holes, 20 October 2026")
        button.click()
        self.assertTrue(card.expanded)
        self.assertEqual(button.text(), "SHOW FIRST 12")
        self.assertEqual(self.name(button), "Show First 12: Araluen, 18 holes, 20 October 2026")
        button.click()
        self.assertFalse(card.expanded)
        self.assertEqual(self.name(button), "Show All 13 Times: Araluen, 18 holes, 20 October 2026")


if __name__ == "__main__":
    unittest.main()
