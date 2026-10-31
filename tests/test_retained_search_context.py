"""Retained source-widget results keep their submitted filters and booking context."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-retained-context-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.booking_assist import build_booking_assist_plan
from app.qt_golfhub_app import GolfHub, TeeTimeCard
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class RetainedSearchContextTests(unittest.TestCase):
    old_date = "2033-01-02"
    next_date = "2033-01-03"
    new_date = "2033-01-05"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(patch("socket.create_connection", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Offline test")))
        self.browser = self.enterContext(patch("app.qt_golfhub_app.webbrowser.open", return_value=True))
        self.enterContext(patch("app.qt_golfhub_app.BookingAssistDialog", side_effect=AssertionError("No holds")))
        self.enterContext(patch("app.qt_golfhub_app.QMessageBox.information", side_effect=AssertionError("Unexpected fallback")))
        self.error_dialog = self.enterContext(patch("app.qt_golfhub_app.QMessageBox.critical"))
        self.enterContext(patch("app.qt_golfhub_app.perth_today", return_value=QDate(2033, 1, 2)))
        self.callback_errors = []
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callback_errors.append(str(a[1]))))
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.window.set_all(False)
        next(r for r in self.window.course_rows if r.site.name == "Araluen").check.setChecked(True)
        self.thread = MagicMock()
        self.thread.isRunning.return_value = True
        self.thread.wait.return_value = False
        self.enterContext(patch("app.qt_golfhub_app.QThread", return_value=self.thread))
        self.worker_type = self.enterContext(patch("app.qt_golfhub_app.ScanWorker"))
        self.plan_builder = self.enterContext(patch(
            "app.qt_golfhub_app.build_booking_assist_plan", wraps=build_booking_assist_plan))
        self.choice = self.enterContext(patch.object(self.window, "_booking_choice", return_value="cancel"))
        self.save = self.enterContext(patch("app.qt_golfhub_app.save_local_snapshot"))

    def tearDown(self):
        # The substituted worker/thread never execute; clear the stand-ins
        # before the real widget cleanup inspects native lifecycle state.
        self.window.scan_thread = None
        self.window.scan_worker = None
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [], "Qt callbacks must not raise")

    def controls(self, dates, players, time="Any time"):
        self.window.date.set_dates([QDate.fromString(value, "yyyy-MM-dd") for value in dates])
        self.window.players.setCurrentText("Any" if players is None else str(players))
        self.window.time_preset.setCurrentText(time)

    @staticmethod
    def result(date, *, spots=4, minutes=540):
        url = ("https://araluenestategolfcourse.miclub.com.au/guests/bookings/"
               f"ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate={date}&feeGroupId=102807")
        hour, minute = divmod(minutes, 60)
        row = {"time": f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}",
               "minutes": minutes, "spots": spots, "source_url": url}
        return {"site_name": "Araluen", "url": url, "hole_label": "18 holes",
                "decorated_rows": [row], "weather": None, "error": None}

    def saved_single(self, players=1):
        self.controls([self.old_date], players)
        self.window.context = self.window.params()
        result = self.result(self.old_date)
        self.window.render_results([result], "Synthetic saved snapshot")
        return result

    def saved_multi(self, players=1, *, spots=2, time="Morning"):
        self.controls([self.old_date, self.next_date], players, time)
        self.window.context = self.window.params()
        days = [{"date": date, "results": [self.result(date, spots=spots)],
                 "source": "Synthetic saved snapshot"} for date in (self.old_date, self.next_date)]
        self.window.render_multi_results(days, "Synthetic saved dates")

    def start_new_live(self, players=4, time="Afternoon"):
        self.controls([self.new_date], players, time)
        self.window.search_live()
        self.worker_type.assert_called_once()
        self.thread.start.assert_called_once()
        self.assertEqual(self.window.context["date"], self.new_date)
        self.assertEqual(self.window.context["players"], players)

    def book(self, parent=None):
        parent = parent or self.window.results_body
        button = next(b for b in parent.findChildren(QPushButton) if b.text() == "BOOK")
        self.assertTrue(button.isEnabled())
        button.click()
        return button

    def assert_plan(self, players, date):
        self.plan_builder.assert_called_once()
        self.assertEqual(self.plan_builder.call_args.kwargs["players"], players)
        self.assertIn(f"selectedDate={date}", self.plan_builder.call_args.kwargs["source_url"])
        self.choice.assert_called_once()
        self.browser.assert_not_called()

    def test_retained_book_during_new_live_search_uses_displayed_group(self):
        self.saved_single(players=1)
        self.start_new_live(players=4)
        button = self.book()
        self.assertIn("2 January 2033", button.accessibleName())
        self.assert_plan(1, self.old_date)
        self.assertEqual(self.window.context["players"], 4)

    def test_retained_book_after_failed_refresh_uses_displayed_group(self):
        self.saved_single(players=1)
        self.start_new_live(players=4)
        self.window.scan_failed("Synthetic offline failure")
        self.error_dialog.assert_called_once()
        self.book()
        self.assert_plan(1, self.old_date)
        self.save.assert_not_called()

    def test_retained_book_after_cancelled_refresh_uses_displayed_group(self):
        self.saved_single(players=1)
        self.start_new_live(players=4)
        self.window.scan_finished([], True)
        self.book()
        self.assert_plan(1, self.old_date)
        self.save.assert_not_called()

    def test_retained_any_players_keeps_direct_handoff_after_new_group_search(self):
        result = self.saved_single(players=None)
        self.start_new_live(players=4)
        self.book()
        self.plan_builder.assert_not_called()
        self.choice.assert_not_called()
        self.browser.assert_called_once_with(result["url"])

    def test_retained_explicit_group_is_not_replaced_by_new_any_players(self):
        self.saved_single(players=4)
        self.start_new_live(players=None)
        self.book()
        self.assert_plan(4, self.old_date)

    def test_lazy_date_keeps_original_player_time_filters_and_booking_date(self):
        self.saved_multi(players=1, spots=2, time="Morning")
        section = self.window.day_sections[1]
        self.assertFalse(section._built)
        self.assertIn("1 time across 1 course", section.toggle.text())
        self.start_new_live(players=4, time="Afternoon")
        section.set_expanded(True)
        cards = section.findChildren(TeeTimeCard)
        self.assertEqual([(c.row["minutes"], c.row["spots"]) for c in cards], [(540, 2)])
        self.assertNotIn("No live tee times matched these filters on this day.",
                         [label.text() for label in section.findChildren(QLabel)])
        button = self.book(section)
        self.assertIn("3 January 2033", button.accessibleName())
        self.assert_plan(1, self.next_date)
        self.assertEqual(self.window.context["date"], self.new_date)
        self.assertEqual((self.window.context["from"], self.window.context["to"]), (900, 1110))

    def test_already_built_multiday_card_keeps_original_group(self):
        self.saved_multi(players=1, spots=4)
        section = self.window.day_sections[0]
        self.assertTrue(section._built)
        self.start_new_live(players=4)
        self.book(section)
        self.assert_plan(1, self.old_date)

    def test_successful_replacement_adopts_new_filters_and_booking_context(self):
        self.saved_single(players=1)
        self.start_new_live(players=4, time="Afternoon")
        result = self.result(self.new_date, minutes=960)
        self.window.scan_finished([result], False)
        button = self.book()
        self.assertIn("5 January 2033", button.accessibleName())
        self.assert_plan(4, self.new_date)
        self.save.assert_called_once()
        self.assertEqual(self.save.call_args.args[0]["date"], self.new_date)
        self.assertEqual(self.save.call_args.args[0]["results"], [result])

    def test_pending_controls_alone_do_not_change_retained_handoff(self):
        self.saved_single(players=1)
        self.controls([self.new_date], 4, "Afternoon")
        self.book()
        self.assert_plan(1, self.old_date)
        self.worker_type.assert_not_called()

    def test_legacy_direct_open_tee_time_uses_current_context(self):
        self.saved_single(players=1)
        self.controls([self.new_date], 4)
        self.window.context = self.window.params()
        result = self.result(self.new_date)
        self.window.open_tee_time(result, result["decorated_rows"][0])
        self.assert_plan(4, self.new_date)
