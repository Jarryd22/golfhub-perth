"""Offline regressions for counts of courses with matching exact tee times."""
import os
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-result-counts-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from app.qt_golfhub_app import DirectCourseCard, GolfHub, ResultCard, TeeTimeCard
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class ResultCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.errors = []
        for target in ("socket.create_connection", "socket.socket.connect", "webbrowser.open"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline test")))
        self.enterContext(patch("sys.excepthook", side_effect=lambda *args: self.errors.append(str(args[1]))))
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.live = next(site for site in self.window.sites if site.name == "Araluen")
        self.wembley = next(site for site in self.window.sites if site.name == "Wembley")
        self.collier = next(site for site in self.window.sites if site.name == "Collier Park")
        self.other = next(site for site in self.window.sites
                          if site.provider != "direct" and "18" in site.holes
                          and site.name not in {self.live.name, self.wembley.name, self.collier.name})
        self.direct = next(site for site in self.window.sites if site.provider == "direct" and "18" in site.holes)
        self.window.context = {
            "sites": [self.live, self.other, self.wembley, self.collier, self.direct],
            "date": "2030-01-02", "dates": ["2030-01-02"], "holes": "18",
            "players": None, "from": None, "to": None,
        }

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.errors, [], "Qt callbacks must not raise")

    @staticmethod
    def row(minutes=540, spots=4):
        hour, minute = divmod(minutes, 60)
        return {"time": f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}",
                "minutes": minutes, "spots": spots}

    def result(self, site, rows=(), **extra):
        return {"site_name": site.name, "url": "https://example.invalid/booking",
                "hole_label": "18 holes", "decorated_rows": list(rows),
                "weather": None, "error": None, **extra}

    def render(self, results):
        self.window.render_results(results, "Synthetic cache")

    def matching_course_names(self):
        return {card.result["site_name"] for card in self.window.findChildren(ResultCard)
                if card.findChildren(TeeTimeCard)}

    def test_calendar_only_course_does_not_inflate_a_matching_course_count(self):
        for state in ("available", "full", "unreleased"):
            with self.subTest(calendar=state):
                self.render([self.result(self.live, [self.row()]),
                             self.result(self.wembley, calendar_availability=state)])
                self.assertEqual(self.matching_course_names(), {self.live.name})
                self.assertEqual(len(self.window.findChildren(ResultCard)), 2)
                self.assertEqual(self.window.status.text(), "1 matching tee time across 1 course")

    def test_full_or_unreleased_calendar_without_exact_times_has_zero_matching_courses(self):
        for state in ("full", "unreleased"):
            with self.subTest(calendar=state):
                self.render([self.result(self.wembley, calendar_availability=state)])
                self.assertEqual(self.matching_course_names(), set())
                self.assertEqual(len(self.window.findChildren(ResultCard)), 1)
                self.assertEqual(self.window.status.text(), "0 matching tee times across 0 courses")

    def test_available_calendar_only_keeps_calendar_availability_wording(self):
        self.render([self.result(self.wembley, calendar_availability="available")])
        self.assertEqual(self.matching_course_names(), set())
        self.assertEqual(self.window.findChild(QLabel, "SummaryValue").text(), "Wembley bookings available")
        self.assertEqual(self.window.status.text(), "Wembley has booking availability - open it to view exact times")

    def test_player_and_time_filters_count_only_courses_with_remaining_rows(self):
        self.window.context.update(players=4, **{"from": 540, "to": 600})
        self.render([
            self.result(self.live, [self.row(539), self.row(540), self.row(600), self.row(601)]),
            self.result(self.other, [self.row(550, 3), self.row(601, 4)]),
            self.result(self.wembley, calendar_availability="full"),
        ])
        self.assertEqual(self.matching_course_names(), {self.live.name})
        self.assertEqual([card.row["minutes"] for card in self.window.findChildren(TeeTimeCard)], [540, 600])
        self.assertEqual(self.window.status.text(), "2 matching tee times across 1 course")

    def test_many_times_count_a_course_once_through_show_all_toggle(self):
        self.render([self.result(self.live, [self.row(480 + offset * 10) for offset in range(15)]),
                     self.result(self.other, [self.row(540), self.row(600)])])
        self.assertEqual(self.matching_course_names(), {self.live.name, self.other.name})
        self.assertEqual(self.window.status.text(), "17 matching tee times across 2 courses")
        card = next(card for card in self.window.findChildren(ResultCard) if card.result["site_name"] == self.live.name)
        self.assertEqual(len(card.findChildren(TeeTimeCard)), 15)
        for _ in range(2):
            card.more_button.click()
            self.assertEqual(self.window.status.text(), "17 matching tee times across 2 courses")
            self.assertEqual(self.matching_course_names(), {self.live.name, self.other.name})

    def test_error_direct_and_empty_collier_do_not_count_as_matching_courses(self):
        self.render([self.result(self.live, [self.row()]),
                     self.result(self.other, error="Synthetic provider failure"),
                     self.result(self.collier),
                     self.result(self.direct, direct_booking=True)])
        self.assertEqual(self.matching_course_names(), {self.live.name})
        self.assertEqual(len(self.window.findChildren(DirectCourseCard)), 1)
        self.assertEqual(len(self.window.findChildren(ResultCard)), 3)
        self.assertEqual(self.window.status.text(), "1 matching tee time across 1 course")

    def test_counts_follow_submitted_context_and_exclude_unselected_results(self):
        self.window.context.update(sites=[self.live, self.wembley], players=4,
                                   **{"from": 540, "to": 600})
        self.window.players.setCurrentText("1")
        self.window.time_preset.setCurrentText("Afternoon")
        self.window.holes9.setChecked(True)
        self.window.set_all(False)
        self.render([self.result(self.live, [self.row(540), self.row(570, 2), self.row(900)]),
                     self.result(self.wembley, calendar_availability="unreleased"),
                     self.result(self.other, [self.row(540)])])
        self.assertEqual(self.matching_course_names(), {self.live.name})
        self.assertEqual(len(self.window.findChildren(TeeTimeCard)), 1)
        self.assertEqual(self.window.status.text(), "1 matching tee time across 1 course")
        self.assertEqual(self.window.context["holes"], "18")

    def test_single_and_multi_day_counts_agree_for_mixed_calendar_and_exact_results(self):
        results = [self.result(self.live, [self.row()]),
                   self.result(self.other, [self.row(600)]),
                   self.result(self.wembley, calendar_availability="available")]
        self.render(results)
        self.assertEqual(self.window.status.text(), "2 matching tee times across 2 courses")
        self.window.render_multi_results([
            {"date": "2030-01-02", "results": results, "source": "Synthetic cache", "available": True}
        ], "1 of 1 dates loaded")
        self.assertIn("2 times across 2 courses", self.window.day_sections[0].toggle.text())
        self.assertEqual(self.matching_course_names(), {self.live.name, self.other.name})


if __name__ == "__main__":
    unittest.main()
