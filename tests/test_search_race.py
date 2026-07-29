import os
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

from app.qt_golfhub_app import DaySection, GolfHub, ResultCard, TeeTimeCard


class _SignalHarness:
    """Small signal stand-in used to observe a queued cache launch."""

    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _FakeCacheThread:
    instances = []

    def __init__(self):
        self.started = _SignalHarness()
        self.finished = _SignalHarness()
        self.running = False
        self.start_calls = 0
        self.__class__.instances.append(self)

    def isRunning(self):
        return self.running

    def start(self):
        self.start_calls += 1
        self.running = True

    def quit(self):
        self.running = False

    def deleteLater(self):
        pass


class _FakeCacheWorker:
    instances = []

    def __init__(self, date_strings, hole_type):
        self.date_strings = list(date_strings)
        self.hole_type = hole_type
        self.finished = _SignalHarness()
        self.thread = None
        self.__class__.instances.append(self)

    def moveToThread(self, thread):
        self.thread = thread

    def run(self):
        pass

    def deleteLater(self):
        pass


class _ActiveStartupThread:
    def __init__(self):
        self.running = True

    def isRunning(self):
        return self.running


class SearchRaceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        with patch.object(GolfHub, "show_initial_cache"):
            window = GolfHub()
        window._initial_cache_timer.stop()
        window._cache_search_timer.stop()
        return window

    @staticmethod
    def _integrated_site(window):
        return next(
            site
            for site in window.sites
            if site.provider != "direct" and "18" in site.holes
        )

    @staticmethod
    def _live_result(site, rows):
        return {
            "site_name": site.name,
            "url": "https://example.com/guests/bookings/ViewPublicTimesheet.msp",
            "hole_label": "18 holes",
            "decorated_rows": rows,
            "weather": None,
            "error": None,
        }

    def test_multiday_results_apply_player_filter_to_summary_and_lazy_day_cards(self):
        window = self.make_window()
        try:
            site = self._integrated_site(window)
            dates = ["2026-07-16", "2026-07-23"]
            window.context = {
                "sites": [site],
                "date": dates[0],
                "dates": dates,
                "holes": "18",
                "players": 4,
                "from": None,
                "to": None,
            }
            days = [
                {
                    "date": dates[0],
                    "source": "Shared cache",
                    "results": [
                        self._live_result(
                            site,
                            [
                                {"time": "7:30 am", "minutes": 450, "spots": 1},
                                {"time": "8:20 am", "minutes": 500, "spots": 4},
                            ],
                        )
                    ],
                },
                {
                    "date": dates[1],
                    "source": "Shared cache",
                    "results": [
                        self._live_result(
                            site,
                            [
                                {"time": "7:40 am", "minutes": 460, "spots": 2},
                                {"time": "8:00 am", "minutes": 480, "spots": 3},
                            ],
                        )
                    ],
                },
            ]

            window.render_multi_results(days, "2 of 2 dates loaded")

            summary = next(
                label.text()
                for label in window.findChildren(QLabel)
                if label.objectName() == "SummaryValue"
            )
            self.assertEqual(summary, "1 matching time across 2 days")
            self.assertEqual(window.status.text(), "1 matching tee time across 2 days")
            self.assertEqual(
                [card.row["spots"] for card in window.findChildren(TeeTimeCard)],
                [4],
            )
            self.assertEqual(len(window.findChildren(ResultCard)), 1)

            sections = window.findChildren(DaySection)
            self.assertEqual(len(sections), 2)
            sections[1].set_expanded(True)
            self.assertEqual(
                [card.row["spots"] for card in window.findChildren(TeeTimeCard)],
                [4],
            )
            empty_labels = [label.text() for label in sections[1].findChildren(QLabel)]
            self.assertIn("No live tee times matched these filters on this day.", empty_labels)
        finally:
            window.cache_thread = None
            window.close()

    def test_explicit_search_is_queued_while_startup_cache_is_active(self):
        window = self.make_window()
        _FakeCacheThread.instances.clear()
        _FakeCacheWorker.instances.clear()
        active = _ActiveStartupThread()
        try:
            site = self._integrated_site(window)
            first = window.date.minimumDate().addDays(1)
            requested_qdates = [first, first.addDays(7)]
            requested_dates = [value.toString("yyyy-MM-dd") for value in requested_qdates]
            window.context = {
                "sites": [site],
                "date": requested_dates[0],
                "dates": [requested_dates[0]],
                "holes": "18",
                "players": None,
                "from": None,
                "to": None,
            }
            window.cache_thread = active

            window.date.set_dates(requested_qdates)
            window.players.setCurrentText("4")

            with (
                patch("app.qt_golfhub_app.QThread", _FakeCacheThread),
                patch("app.qt_golfhub_app.CacheWorker", _FakeCacheWorker),
                patch("app.qt_golfhub_app.load_local_snapshot", return_value=None),
            ):
                window.search_cache()
                self.assertEqual(_FakeCacheWorker.instances, [])

                active.running = False
                window.cache_thread_done()
                self.app.processEvents()

            self.assertEqual(len(_FakeCacheWorker.instances), 1)
            worker = _FakeCacheWorker.instances[0]
            self.assertEqual(worker.date_strings, requested_dates)
            self.assertEqual(worker.hole_type, "18")
            self.assertEqual(worker.thread.start_calls, 1)
            self.assertEqual(window.context["dates"], requested_dates)
            self.assertEqual(window.context["players"], 4)
        finally:
            for thread in _FakeCacheThread.instances:
                thread.running = False
            window.cache_thread = None
            window.cache_worker = None
            window.close()

    def test_old_cache_completion_cannot_render_over_a_newer_queued_search(self):
        window = self.make_window()
        try:
            site = self._integrated_site(window)
            old_context = {
                "sites": [site],
                "date": "2026-07-16",
                "dates": ["2026-07-16"],
                "holes": "18",
                "players": None,
                "from": None,
                "to": None,
            }
            newer_context = {
                "sites": [site],
                "date": "2026-07-23",
                "dates": ["2026-07-23", "2026-07-25"],
                "holes": "18",
                "players": 4,
                "from": None,
                "to": None,
            }
            window.context = old_context
            window._active_cache_context = old_context
            window._pending_cache_context = newer_context
            window.search_button.setText("SEARCH QUEUED")
            window.status.setText("Your updated search is next...")
            window.header_status.setText("UPDATING SEARCH")
            old_snapshots = {
                "2026-07-16": {
                    "generated_at": "2026-07-15T00:00:00Z",
                    "results": [
                        self._live_result(
                            site,
                            [{"time": "7:30 am", "minutes": 450, "spots": 1}],
                        )
                    ],
                }
            }

            with (
                patch.object(window, "render_snapshot") as render_snapshot,
                patch.object(window, "render_snapshot_batch") as render_snapshot_batch,
                patch.object(window, "search_live") as search_live,
            ):
                window.cache_finished(old_snapshots)

            render_snapshot.assert_not_called()
            render_snapshot_batch.assert_not_called()
            search_live.assert_not_called()
            self.assertIs(window._pending_cache_context, newer_context)
            self.assertEqual(window.context, old_context)
            self.assertEqual(window.search_button.text(), "SEARCH QUEUED")
            self.assertEqual(window.status.text(), "Loading your updated search...")
            self.assertEqual(window.header_status.text(), "UPDATING SEARCH")
        finally:
            window.cache_thread = None
            window.cache_worker = None
            window.close()

    def test_clear_results_hides_and_detaches_stale_cards_immediately(self):
        window = self.make_window()
        try:
            site = self._integrated_site(window)
            window.context = {
                "sites": [site],
                "date": "2026-07-23",
                "dates": ["2026-07-23"],
                "holes": "18",
                "players": 4,
                "from": None,
                "to": None,
            }
            result = self._live_result(
                site,
                [{"time": "8:20 am", "minutes": 500, "spots": 4}],
            )
            window.show()
            window.render_results([result], "Test cache")
            self.app.processEvents()

            old_card = window.findChildren(ResultCard)[0]
            self.assertIsNotNone(old_card.parentWidget())
            self.assertTrue(old_card.isVisible())

            window.clear_results()

            # These assertions deliberately run before processing deferred
            # deletes: a replaced search must disappear in the same UI turn.
            self.assertTrue(old_card.isHidden())
            self.assertIsNone(old_card.parentWidget())
        finally:
            window.cache_thread = None
            window.cache_worker = None
            window.close()


if __name__ == "__main__":
    unittest.main()

