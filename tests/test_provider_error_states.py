"""Offline source-widget regressions for unavailable provider observations."""
import os
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-provider-errors-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.golfhub_core import COLLIER_PUBLIC_CALENDAR_URL
from app.qt_golfhub_app import GolfHub, ResultCard, TeeTimeCard
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class ProviderErrorStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.callback_errors = []
        self.enterContext(patch("socket.create_connection", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Offline test")))
        self.browser = self.enterContext(patch("app.qt_golfhub_app.webbrowser.open", return_value=True))
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callback_errors.append(str(a[1]))))
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.sites = {site.name: site for site in self.window.sites}
        self.live = self.sites["Araluen"]
        self.collier = self.sites["Collier Park"]
        self.wembley = self.sites["Wembley"]
        self.direct = next(site for site in self.window.sites if site.provider == "direct" and "18" in site.holes)
        self.dates = ["2030-01-02", "2030-01-04", "2030-01-07"]
        self.window.context = {
            "sites": [self.live, self.collier, self.wembley, self.direct],
            "date": self.dates[0], "dates": self.dates[:1], "holes": "18",
            "players": None, "from": None, "to": None,
        }

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [], "Qt callbacks must not raise")

    @staticmethod
    def row(minutes=540, spots=4):
        hour, minute = divmod(minutes, 60)
        return {"time": f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}",
                "minutes": minutes, "spots": spots}

    def result(self, site, rows=(), **extra):
        return {"site_name": site.name, "url": "https://example.invalid/booking",
                "hole_label": "18 holes", "decorated_rows": list(rows),
                "weather": None, "error": None, **extra}

    def failure(self, site=None):
        return self.result(site or self.live, error="Synthetic provider failure")

    @staticmethod
    def payload(*results):
        return {"generated_at": "2030-01-01T00:00:00Z", "results": list(results)}

    @staticmethod
    def texts(widget):
        return [label.text() for label in widget.findChildren(QLabel)]

    def summary(self):
        return self.window.results_layout.itemAt(0).widget()

    def headline(self):
        return self.summary().findChild(QLabel, "SummaryValue").text()

    def summary_warnings(self):
        return self.summary().findChildren(QLabel, "Warning")

    def assert_warning_fits_compact_window(self):
        self.window.resize(980, 640)
        self.window.show()
        self.app.processEvents()
        warning = self.summary_warnings()[0]
        self.window.results_scroll.ensureWidgetVisible(warning)
        self.app.processEvents()
        self.assertTrue(warning.isVisible())
        self.assertGreater(warning.width(), 0)
        self.assertGreaterEqual(warning.height(), warning.heightForWidth(warning.width()))
        self.assertLessEqual(warning.geometry().right(), self.summary().width())

    def assert_single_warning(self, count):
        noun = "course" if count == 1 else "courses"
        warnings = self.summary_warnings()
        self.assertEqual([label.text() for label in warnings], [
            f"Availability could not be checked for {count} {noun}. Open the course cards for details."
        ])
        self.assertTrue(warnings[0].wordWrap())

    def assert_multi_warning(self, count):
        noun = "day" if count == 1 else "days"
        warnings = self.summary_warnings()
        self.assertEqual([label.text() for label in warnings], [
            f"Availability could not be checked for some courses on {count} {noun}. Open the date sections for details."
        ])
        self.assertTrue(warnings[0].wordWrap())

    def render(self, results):
        self.window.render_results(results, "Synthetic cache")

    def render_days(self, results_by_day):
        self.window.context["dates"] = self.dates[:len(results_by_day)]
        self.window.render_snapshot_batch(
            {date: self.payload(*results) for date, results in zip(self.dates, results_by_day) if results is not None},
            {date: "Shared cache" for date in self.dates},
        )

    def test_all_failed_single_day_is_incomplete_instead_of_zero_matches(self):
        self.render([self.failure(), self.failure(self.collier)])
        self.assertEqual(self.headline(), "Availability incomplete")
        self.assertEqual(self.window.status.text(), "Availability could not be checked for 2 courses")
        self.assert_single_warning(2)
        self.assert_warning_fits_compact_window()
        self.assertEqual(len(self.window.findChildren(ResultCard)), 2)
        self.assertEqual(len(self.window.findChildren(TeeTimeCard)), 0)

    def test_error_with_empty_or_filtered_results_does_not_claim_complete_no_match(self):
        self.window.context.update(players=4, **{"from": 540, "to": 600})
        for rows in ([], [self.row(539), self.row(550, 3), self.row(601)]):
            with self.subTest(rows=rows):
                self.render([self.failure(), self.result(self.collier, rows)])
                self.assertEqual(self.headline(), "Availability incomplete")
                self.assertEqual(self.window.status.text(), "Availability could not be checked for 1 course")
                self.assert_single_warning(1)
                self.assertEqual(len(self.window.findChildren(TeeTimeCard)), 0)

    def test_successful_exact_times_keep_counts_and_add_partial_error_warning(self):
        self.window.context.update(players=4, **{"from": 540, "to": 600})
        self.render([self.failure(), self.result(self.collier, [self.row(), self.row(550, 3), self.row(601)])])
        self.assertEqual(self.headline(), "1 matching time")
        self.assertEqual(self.window.status.text(), "1 matching tee time across 1 course")
        self.assertEqual(len(self.window.findChildren(TeeTimeCard)), 1)
        self.assert_single_warning(1)

    def test_calendar_states_keep_cards_and_available_calendar_keeps_its_headline(self):
        for state in ("available", "full", "unreleased"):
            with self.subTest(state=state):
                self.render([self.failure(), self.result(self.wembley, calendar_availability=state)])
                self.assertEqual(len(self.window.findChildren(ResultCard)), 2)
                self.assert_single_warning(1)
                if state == "available":
                    self.assertEqual(self.headline(), "Wembley bookings available")
                    self.assertEqual(self.window.status.text(), "Wembley has booking availability - open it to view exact times")
                else:
                    self.assertEqual(self.headline(), "Availability incomplete")
                    self.assertEqual(self.window.status.text(), "Availability could not be checked for 1 course")
                    self.assertTrue(any(("round as full" if state == "full" else "not released yet") in text
                                        for text in self.texts(self.window.results_body)))

    def test_multi_day_failures_count_error_days_and_keep_lazy_date_context(self):
        self.render_days([[self.failure()], [self.failure(), self.failure(self.collier)]])
        self.assertEqual(self.headline(), "Availability incomplete across 2 days")
        self.assertEqual(self.window.status.text(), "Availability incomplete across 2 days")
        self.assert_multi_warning(2)
        self.assert_warning_fits_compact_window()
        first, second = self.window.day_sections
        self.assertIn("Availability incomplete - 1 course unavailable", first.toggle.text())
        self.assertIn("Availability incomplete - 2 courses unavailable", second.toggle.text())
        self.assertFalse(second._built)
        self.window.players.setCurrentText("4")
        self.window.time_preset.setCurrentText("Afternoon")
        self.window.set_all(False)
        second.set_expanded(True)
        self.assertEqual(len(second.body.findChildren(ResultCard)), 2)
        self.assertTrue(all(card.date_str == self.dates[1] for card in second.body.findChildren(ResultCard)))
        self.assertIn("Availability incomplete - 2 courses unavailable", second.toggle.text())

    def test_provider_error_and_missing_snapshot_remain_distinct(self):
        self.render_days([[self.failure()], None, [self.result(self.collier)]])
        self.assertEqual(self.headline(), "Availability incomplete across 2 loaded days")
        self.assertEqual(self.window.status.text(), "Availability incomplete across 2 loaded days")
        self.assert_multi_warning(1)
        failed, missing, empty = self.window.day_sections
        self.assertIn("Availability incomplete - 1 course unavailable", failed.toggle.text())
        self.assertIn("Availability not checked", missing.toggle.text())
        self.assertIn("No matching live times", empty.toggle.text())
        missing.set_expanded(True)
        self.assertTrue(any("Availability could not be checked for this date" in text
                            for text in self.texts(missing.body)))

    def test_multi_day_positive_results_preserve_headlines_with_error_warning(self):
        for positive in ("row", "calendar"):
            with self.subTest(positive=positive):
                result = (self.result(self.collier, [self.row()]) if positive == "row"
                          else self.result(self.wembley, calendar_availability="available"))
                self.render_days([[self.failure(), result], [self.result(self.live)]])
                self.assert_multi_warning(1)
                if positive == "row":
                    self.assertEqual(self.headline(), "1 matching time across 2 days")
                    self.assertEqual(self.window.status.text(), "1 matching tee time across 2 days")
                    self.assertIn("1 time across 1 course", self.window.day_sections[0].toggle.text())
                else:
                    self.assertEqual(self.headline(), "Wembley bookings available across 1 date")
                    self.assertEqual(self.window.status.text(), "Wembley has bookings available on 1 selected date")
                    self.assertIn("Bookings shown on 1 official calendar", self.window.day_sections[0].toggle.text())

    def test_saved_fallback_preserves_error_state_and_successful_empty_state(self):
        for failed in (True, False):
            with self.subTest(failed=failed):
                saved = self.payload(self.failure() if failed else self.result(self.live))
                with patch("app.qt_golfhub_app.load_local_snapshot", return_value=saved), \
                        patch.object(self.window, "search_live") as live_search:
                    self.window.cache_finished({})
                live_search.assert_not_called()
                self.assertTrue(any("Saved on this device" in text for text in self.texts(self.summary())))
                if failed:
                    self.assertEqual(self.headline(), "Availability incomplete")
                    self.assert_single_warning(1)
                else:
                    self.assertEqual(self.headline(), "0 matching times")
                    self.assertEqual(self.summary_warnings(), [])

    def test_unselected_and_direct_link_errors_do_not_mark_feed_availability_incomplete(self):
        self.window.context["sites"] = [self.live, self.direct]
        self.render([self.result(self.live), self.failure(self.wembley),
                     self.result(self.direct, direct_booking=True, error="Synthetic link error")])
        self.assertEqual(self.headline(), "0 matching times")
        self.assertEqual(self.summary_warnings(), [])
        self.render_days([[self.result(self.live), self.failure(self.wembley),
                           self.result(self.direct, direct_booking=True, error="Synthetic link error")]])
        self.assertEqual(self.headline(), "0 matching times across 1 day")
        self.assertEqual(self.summary_warnings(), [])

    def test_collier_provider_error_keeps_unknown_meta_and_official_calendar_handoff(self):
        self.render([self.failure(self.collier)])
        card = self.window.findChild(ResultCard)
        labels = self.texts(card)
        self.assertIn("Could not read live availability - direct booking is still available", labels)
        self.assertFalse(any("No public tee times showing" in text for text in labels))
        button = next(button for button in card.findChildren(QPushButton) if button.text() == "VIEW OFFICIAL CALENDAR")
        self.assertIn("Collier Park", button.accessibleName())
        button.click()
        self.browser.assert_called_once_with(COLLIER_PUBLIC_CALENDAR_URL)

    def test_genuine_empty_collier_keeps_existing_empty_notice_without_error_warning(self):
        self.render([self.result(self.collier)])
        card = self.window.findChild(ResultCard)
        self.assertIn("No public tee times showing for this date - 18 holes", self.texts(card))
        self.assertTrue(any("8 days in advance at 12:00 pm" in text for text in self.texts(card)))
        self.assertEqual(self.headline(), "0 matching times")
        self.assertEqual(self.summary_warnings(), [])


if __name__ == "__main__":
    unittest.main()
