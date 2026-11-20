"""Offline regressions for identifying repeated booking and course actions."""
import os
import sys
import tempfile
import unittest
import webbrowser
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from app import qt_golfhub_app as ui
from app import shared_cache as cache
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


class BrowserHandoffTests(unittest.TestCase):
    """Report failed external handoffs without retrying or creating holds."""

    booking_url = (
        "https://araluenestategolfcourse.miclub.com.au/guests/bookings/"
        "ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-07-16&feeGroupId=102807"
    )
    course_url = "https://example.invalid/course?round=18&date=2026-07-16"
    quick18_url = "https://bookings.quick18.com/teetimes/searchmatrix?date=2026-07-16"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        runtime = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(cache, "LOCAL_CACHE_DIR", Path(runtime) / "cache"))
        for target in (
            "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
            "socket.getaddrinfo", "app.qt_golfhub_app.fetch_site_result",
            "app.course_results.get_weather_for_date", "app.qt_golfhub_app.save_local_snapshot",
            "app.qt_golfhub_app.ScanWorker.run", "app.qt_golfhub_app.CacheWorker.run",
        ):
            self.enterContext(patch(target, side_effect=AssertionError("Offline browser handoff test")))
        self.enterContext(patch.object(GolfHub, "show_initial_cache"))
        self.browser = self.enterContext(patch.object(ui.webbrowser, "open", return_value=True))
        self.information = self.enterContext(patch.object(ui.QMessageBox, "information"))
        self.warning = self.enterContext(patch.object(ui.QMessageBox, "warning"))
        self.enterContext(patch.object(ui.QMessageBox, "exec"))
        self.dialog = self.enterContext(patch.object(ui, "BookingAssistDialog"))
        self.builder = self.enterContext(patch.object(ui, "build_booking_assist_plan",
                                                    wraps=ui.build_booking_assist_plan))
        self.callbacks = []
        self.enterContext(patch.object(sys, "excepthook",
                                       side_effect=lambda kind, error, trace: self.callbacks.append(error)))
        self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.window.context = dict(self.window.params(), players=4)
        self.choice = self.enterContext(patch.object(self.window, "_booking_choice", return_value="manual"))
        self.keep_dialog = self.enterContext(patch.object(self.window, "_keep_booking_dialog"))

    def tearDown(self):
        cleanup_qt_widgets()

    def action(self, route, *, missing=False):
        row = {"time": "07:00 am", "minutes": 420, "spots": 4,
               "source_url": None if missing else self.booking_url}
        result = {"site_name": "Araluen", "hole_label": "18 holes", "weather": None,
                  "error": None, "url": None if missing else self.course_url,
                  "decorated_rows": [row]}
        if route == "tee_card":
            card = TeeTimeCard(row, result["url"], result)
            return card, card.findChild(QPushButton), row["source_url"], None, None, 0, 0
        if route == "direct_card":
            card = DirectCourseCard(result)
            return card, card.findChild(QPushButton), result["url"], None, None, 0, 0
        if route == "result_card":
            card = ResultCard(result, [])
            button = next(b for b in card.findChildren(QPushButton) if b.text() == "OPEN BOOKING PAGE")
            return card, button, result["url"], None, None, 0, 0

        info_title, warning_title, builder_calls, dialog_calls = None, None, 1, 0
        if route == "any_players":
            self.window.context["players"] = None
            builder_calls = 0
        elif route == "invalid_plan":
            row["spots"] = 1
            info_title = "Open official booking page"
        elif route == "unsupported_provider":
            row["source_url"] = result["url"] = self.quick18_url
            info_title = "Select players on the official page"
        elif route == "dialog_failure":
            self.choice.return_value = "hold"
            self.dialog.side_effect = RuntimeError("Injected dialog construction failure")
            warning_title, builder_calls, dialog_calls = "Player assist unavailable", 2, 1
        elif route != "manual_choice":
            raise AssertionError(f"Unknown route: {route}")
        card = ResultCard(result, [row], self.window.open_tee_time)
        button = next(b for b in card.findChildren(QPushButton) if b.text() == "BOOK")
        # Keep the card alive until the Qt click has delivered its callback.
        card.setParent(self.window)
        return self.window, button, row["source_url"], info_title, warning_title, builder_calls, dialog_calls

    def check_route(self, route):
        outcomes = [("true", True), ("false", False),
                    ("os_error", OSError("Injected browser failure")),
                    ("browser_error", webbrowser.Error("Injected browser failure"))]
        for outcome, response in outcomes:
            with self.subTest(route=route, outcome=outcome):
                self.callbacks.clear()
                for mock in (self.browser, self.information, self.warning, self.dialog,
                             self.builder, self.choice, self.keep_dialog):
                    mock.reset_mock()
                self.window.context["players"] = 4
                self.choice.return_value = "manual"
                self.dialog.side_effect = None
                self.browser.side_effect = response if isinstance(response, Exception) else None
                self.browser.return_value = response if isinstance(response, bool) else False
                parent, button, url, info_title, prior_warning, builds, dialogs = self.action(route)
                button.click()
                self.app.processEvents()
                self.browser.assert_called_once_with(url)
                self.assertEqual(self.builder.call_count, builds)
                self.assertEqual(self.dialog.call_count, dialogs)
                self.keep_dialog.assert_not_called()
                info = self.information.call_args_list
                self.assertEqual([call.args[1] for call in info], [info_title] if info_title else [])
                failure = [call for call in self.warning.call_args_list
                           if call.args[1] == "Could not open browser"]
                previous = [call.args[1] for call in self.warning.call_args_list
                            if call.args[1] != "Could not open browser"]
                self.assertEqual(previous, [prior_warning] if prior_warning else [])
                self.assertEqual(self.callbacks, [], "A failed handoff must not escape the Qt callback")
                self.assertEqual(len(failure), 0 if response is True else 1)
                if failure:
                    self.assertIs(failure[0].args[0], parent)
                    message = failure[0].args[2]
                    self.assertIn(url, message)
                    self.assertRegex(message.lower(), r"could not|couldn't|unable|failed")
                    self.assertRegex(message.lower(), r"manual|your browser|directly|copy")

    def test_tee_card_reports_browser_failure(self):
        self.check_route("tee_card")

    def test_direct_card_reports_browser_failure(self):
        self.check_route("direct_card")

    def test_result_card_reports_browser_failure(self):
        self.check_route("result_card")

    def test_any_players_reports_browser_failure(self):
        self.check_route("any_players")

    def test_invalid_plan_fallback_reports_browser_failure(self):
        self.check_route("invalid_plan")

    def test_unsupported_provider_reports_browser_failure(self):
        self.check_route("unsupported_provider")

    def test_manual_choice_reports_browser_failure(self):
        self.check_route("manual_choice")

    def test_dialog_failure_fallback_reports_browser_failure(self):
        self.check_route("dialog_failure")

    def test_cancel_button_path_does_not_open_or_warn(self):
        self.choice.return_value = "cancel"
        _, button, *_ = self.action("manual_choice")
        button.click()
        self.browser.assert_not_called()
        self.dialog.assert_not_called()
        self.keep_dialog.assert_not_called()
        self.warning.assert_not_called()
        self.information.assert_not_called()
        self.assertEqual(self.callbacks, [])

    def test_missing_links_preserve_existing_button_guards(self):
        for route in ("tee_card", "direct_card", "result_card", "any_players"):
            with self.subTest(route=route):
                self.information.reset_mock()
                parent, button, *details = self.action(route, missing=True)
                button.click()
                self.browser.assert_not_called()
                self.dialog.assert_not_called()
                self.warning.assert_not_called()
                self.builder.assert_not_called()
                self.keep_dialog.assert_not_called()
                expected = ["Booking page unavailable"] if route == "any_players" else []
                self.assertEqual([call.args[1] for call in self.information.call_args_list], expected)
                self.assertEqual(self.callbacks, [])

    def test_confirmed_hold_button_path_keeps_dialog_handoff_without_browser(self):
        self.choice.return_value = "hold"
        _, button, *_ = self.action("manual_choice")
        button.click()
        self.dialog.assert_called_once()
        confirmed = self.dialog.call_args.args[0]
        self.assertTrue(confirmed.temporary_hold_confirmed)
        self.assertTrue(confirmed.automatic_preselection_allowed)
        self.assertIs(self.dialog.call_args.args[1], self.window)
        self.keep_dialog.assert_called_once_with(self.dialog.return_value)
        self.browser.assert_not_called()
        self.warning.assert_not_called()
        self.information.assert_not_called()
        self.assertEqual(self.callbacks, [])


if __name__ == "__main__":
    unittest.main()
