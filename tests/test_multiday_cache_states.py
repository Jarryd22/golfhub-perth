"""Offline widget regressions for incomplete multi-date cache coverage."""

import os
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-cache-states-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

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


class MultiDayCacheStateTests(unittest.TestCase):
    unavailable_note = (
        "Availability could not be checked for this date. Try Find Tee Times again, "
        "or select this date alone and use Refresh Live."
    )
    empty_note = "No live tee times matched these filters on this day."

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.callback_errors = []
        self.enterContext(patch("socket.create_connection", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Offline test")))
        self.browser = self.enterContext(patch("app.qt_golfhub_app.webbrowser.open", return_value=True))
        self.enterContext(patch("sys.excepthook", side_effect=lambda *args: self.callback_errors.append(str(args[1]))))
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.site = next(site for site in self.window.sites
                         if site.provider != "direct" and site.name != "Collier Park" and "18" in site.holes)
        self.dates = ["2030-01-02", "2030-01-04", "2030-01-07"]
        self.window.context = {
            "sites": [self.site], "date": self.dates[0], "dates": self.dates,
            "holes": "18", "players": None, "from": None, "to": None,
        }

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [], "Qt callbacks must not raise")

    def result(self, rows=(), *, site=None, **extra):
        return {
            "site_name": (site or self.site).name,
            "url": "https://example.invalid/booking",
            "hole_label": "18 holes", "decorated_rows": list(rows),
            "weather": None, "error": None, **extra,
        }

    @staticmethod
    def row(minutes=540, spots=4):
        hour, minute = divmod(minutes, 60)
        return {"time": f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}",
                "minutes": minutes, "spots": spots}

    @staticmethod
    def payload(*results):
        return {"generated_at": "2030-01-01T00:00:00Z", "results": list(results)}

    @staticmethod
    def texts(widget):
        return [label.text() for label in widget.findChildren(QLabel)]

    def summary(self):
        return self.window.results_body.findChild(QLabel, "SummaryValue").text()

    def render(self, snapshots):
        self.window.render_snapshot_batch(snapshots, {date: "Shared cache" for date in snapshots})

    def test_missing_day_title_does_not_claim_no_matches(self):
        self.render({self.dates[1]: self.payload(self.result([self.row()]))})
        missing = self.window.day_sections[0]
        self.assertIn("Availability not checked", missing.toggle.text())
        self.assertNotIn("No matching", missing.toggle.text())
        self.assertIn("Cache unavailable for this date", self.texts(missing))
        self.assertEqual(self.window.header_status.text(), "SHARED CACHE / 1 OF 3 DAYS")

    def test_lazy_missing_body_retains_state_and_wraps_at_compact_size(self):
        self.render({self.dates[0]: self.payload(self.result([self.row()])),
                     self.dates[2]: self.payload(self.result())})
        missing, loaded_empty = self.window.day_sections[1:]
        self.assertFalse(missing._built)
        self.assertFalse(loaded_empty._built)
        # Pending controls must not replace the state captured for displayed dates.
        self.window.date.setDate(self.window.date.minimumDate().addDays(1))
        self.window.players.setCurrentText("2")
        self.window.time_preset.setCurrentText("Afternoon")
        missing.set_expanded(True)
        loaded_empty.set_expanded(True)
        self.assertIn(self.unavailable_note, self.texts(missing.body))
        self.assertNotIn(self.empty_note, self.texts(missing.body))
        self.assertIn(self.empty_note, self.texts(loaded_empty.body))
        self.assertNotIn(self.unavailable_note, self.texts(loaded_empty.body))
        self.window.resize(980, 640)
        self.window.show()
        self.app.processEvents()
        note = next(label for label in missing.body.findChildren(QLabel)
                    if label.text() == self.unavailable_note)
        self.window.results_scroll.ensureWidgetVisible(note)
        self.app.processEvents()
        self.assertTrue(note.isVisible())
        self.assertTrue(note.wordWrap())
        self.assertGreater(note.width(), 0)
        self.assertGreaterEqual(note.height(), note.heightForWidth(note.width()))
        self.assertLessEqual(note.geometry().right(), missing.body.width())
        self.assertEqual(missing.date_str, self.dates[1])

    def test_partial_counts_use_loaded_days_and_submitted_player_time_filters(self):
        self.window.context.update(players=4, **{"from": 480, "to": 600})
        self.render({
            self.dates[1]: self.payload(self.result([self.row(479), self.row(480, 3),
                                                    self.row(480), self.row(600), self.row(601)])),
            self.dates[2]: self.payload(self.result([self.row(540)])),
        })
        self.assertEqual(self.summary(), "3 matching times across 2 loaded days")
        self.assertEqual(self.window.status.text(), "3 matching tee times across 2 loaded days")
        self.assertFalse(self.window.day_sections[0]._built)
        self.window.day_sections[2].set_expanded(True)
        self.assertEqual([card.row["minutes"] for card in self.window.findChildren(TeeTimeCard)],
                         [480, 600, 540])

    def test_partial_zero_matches_only_describes_loaded_day(self):
        self.render({self.dates[1]: self.payload(self.result())})
        self.assertEqual(self.summary(), "0 matching times across 1 loaded day")
        self.assertEqual(self.window.status.text(), "0 matching tee times across 1 loaded day")
        loaded = self.window.day_sections[1]
        loaded.set_expanded(True)
        self.assertIn("No matching live times", loaded.toggle.text())
        self.assertIn(self.empty_note, self.texts(loaded.body))

    def test_local_fallback_is_loaded_while_remaining_missing_day_stays_unknown(self):
        saved = self.payload(self.result([self.row()]))
        with patch("app.qt_golfhub_app.load_local_snapshot",
                   side_effect=lambda date, holes: saved if date == self.dates[1] else None) as local:
            self.window.cache_finished({self.dates[0]: self.payload(self.result())})
        self.assertEqual(local.call_args_list[0].args, (self.dates[1], "18"))
        self.assertEqual(local.call_args_list[1].args, (self.dates[2], "18"))
        self.assertEqual(local.call_count, 2)
        self.assertTrue(any("Saved on this device" in text
                            for text in self.texts(self.window.day_sections[1])))
        self.assertNotIn("Availability not checked", self.window.day_sections[1].toggle.text())
        self.assertIn("Availability not checked", self.window.day_sections[2].toggle.text())
        self.assertEqual(self.summary(), "1 matching time across 2 loaded days")
        self.assertEqual(self.window.header_status.text(), "SHARED CACHE / 2 OF 3 DAYS")

    def test_all_missing_cache_keeps_actionable_unavailable_state_without_live_search(self):
        with patch("app.qt_golfhub_app.load_local_snapshot", return_value=None), \
                patch.object(self.window, "search_live") as live:
            self.window.cache_finished({})
        live.assert_not_called()
        self.assertEqual(self.window.status.text(), "Multi-day cache temporarily unavailable")
        self.assertEqual(self.window.header_status.text(), "SHARED CACHE UNAVAILABLE")
        self.assertIn("No cached results were available for these dates. Try a shorter range or search again shortly.",
                      self.texts(self.window.results_body))
        self.assertFalse(any("0 matching" in text for text in self.texts(self.window.results_body)))

    def test_loaded_provider_error_and_unreleased_calendar_remain_distinct(self):
        wembley = next(site for site in self.window.sites if site.name == "Wembley")
        self.window.context["sites"] = [self.site, wembley]
        self.render({self.dates[1]: self.payload(
            self.result(error="Offline fixture"),
            self.result(site=wembley, calendar_availability="unreleased",
                        booking_note="Timesheet not released yet."),
        )})
        loaded = self.window.day_sections[1]
        loaded.set_expanded(True)
        self.assertEqual(len(loaded.body.findChildren(ResultCard)), 2)
        self.assertIn("Live times were unavailable for this course. You can still open its official booking page.",
                      self.texts(loaded.body))
        self.assertIn("Timesheet not released yet.", self.texts(loaded.body))
        self.assertNotIn(self.unavailable_note, self.texts(loaded.body))
        self.assertIn("Availability not checked", self.window.day_sections[2].toggle.text())

    def test_calendar_availability_and_deduplicated_direct_links_survive_partial_cache(self):
        wembley = next(site for site in self.window.sites if site.name == "Wembley")
        direct = next(site for site in self.window.sites if site.provider == "direct" and "18" in site.holes)
        self.window.context["sites"] = [wembley, direct]
        self.render({self.dates[1]: self.payload(self.result(site=wembley,
                                                          calendar_availability="available"))})
        self.assertEqual(self.summary(), "Wembley bookings available across 1 date")
        self.assertEqual(self.window.status.text(), "Wembley has bookings available on 1 selected date")
        links = self.window.findChildren(DirectCourseCard)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].result["site_name"], direct.name)
        links[0].findChild(QPushButton).click()
        self.browser.assert_called_once_with(links[0].result["url"])
        self.assertIn("Availability not checked", self.window.day_sections[0].toggle.text())
        self.window.day_sections[0].set_expanded(True)
        self.assertIn(self.unavailable_note, self.texts(self.window.day_sections[0].body))

    def test_fully_loaded_empty_days_keep_existing_no_match_wording(self):
        self.render({date: self.payload(self.result()) for date in self.dates})
        self.assertEqual(self.summary(), "0 matching times across 3 days")
        self.assertEqual(self.window.status.text(), "0 matching tee times across 3 days")
        for section in self.window.day_sections:
            section.set_expanded(True)
            self.assertIn("No matching live times", section.toggle.text())
            self.assertIn(self.empty_note, self.texts(section.body))
            self.assertNotIn(self.unavailable_note, self.texts(section.body))

    def test_direct_render_callers_without_coverage_metadata_remain_loaded(self):
        self.window.render_multi_results([
            {"date": self.dates[0], "results": [self.result([self.row()])], "source": "Test cache"},
            {"date": self.dates[1], "results": [self.result()], "source": "Test cache"},
        ], "2 of 2 dates loaded")
        self.assertEqual(self.summary(), "1 matching time across 2 days")
        self.assertEqual(self.window.status.text(), "1 matching tee time across 2 days")
        empty = self.window.day_sections[1]
        empty.set_expanded(True)
        self.assertIn(self.empty_note, self.texts(empty.body))
        self.assertNotIn(self.unavailable_note, self.texts(empty.body))


if __name__ == "__main__":
    unittest.main()
