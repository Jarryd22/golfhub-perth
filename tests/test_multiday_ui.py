import os
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QTableView, QVBoxLayout, QWidget
from tests.qt_test_support import cleanup_qt_widgets

from app.qt_golfhub_app import (
    CacheWorker,
    DaySection,
    GolfHub,
    MAX_SEARCH_DAYS,
    MultiDateButton,
    MultiDatePopup,
    ResultCard,
    consecutive_date_strings,
    perth_today,
)


class MultiDayUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls):
        cleanup_qt_widgets()

    def make_window(self):
        with patch.object(GolfHub, "show_initial_cache"):
            return GolfHub()

    def test_consecutive_dates_are_bounded_to_cache_window(self):
        start = QDate(2026, 7, 15)
        maximum = start.addDays(27)
        values = consecutive_date_strings(start, 99, maximum)
        self.assertEqual(len(values), MAX_SEARCH_DAYS)
        self.assertEqual(values[0], "2026-07-15")
        self.assertEqual(values[-1], "2026-08-11")
        self.assertEqual(consecutive_date_strings(start, 0, start.addDays(2)), ["2026-07-15"])
        self.assertEqual(len(consecutive_date_strings(start, 7, start.addDays(2))), 3)

    def test_calendar_keeps_single_day_default_and_accepts_nonconsecutive_dates(self):
        window = self.make_window()
        try:
            window.date.setDate(window.date.minimumDate())
            self.assertEqual(window.day_count(), 1)
            self.assertEqual(window.params()["dates"], [window.date.date().toString("yyyy-MM-dd")])

            chosen = [
                window.date.minimumDate(),
                window.date.minimumDate().addDays(2),
                window.date.minimumDate().addDays(5),
                window.date.minimumDate().addDays(9),
            ]
            window.date.set_dates(chosen)
            expected = [value.toString("yyyy-MM-dd") for value in chosen]
            self.assertEqual(window.params()["dates"], expected)
            self.assertFalse(window.live_button.isEnabled())
            self.assertIn("Searching 4 selected dates", window.search_helper.text())

            window.date.setDate(window.date.minimumDate())
            self.assertTrue(window.live_button.isEnabled())
        finally:
            window.close()

    def test_multi_date_dropdown_toggles_dates_and_keeps_one_selected(self):
        minimum = QDate(2026, 7, 15)
        selected = [minimum.addDays(1), minimum.addDays(3)]
        popup = MultiDatePopup(minimum, minimum.addDays(27), selected)
        try:
            self.assertEqual(popup.selected_dates(), selected)
            popup.toggle_date(minimum.addDays(3))
            popup.toggle_date(minimum.addDays(7))
            self.assertEqual(popup.selected_dates(), [minimum.addDays(1), minimum.addDays(7)])
            popup.clear_dates()
            self.assertEqual(popup.selected_dates(), [minimum.addDays(1)])
            self.assertTrue(popup.done_button.isEnabled())
            popup.toggle_date(minimum.addDays(1))
            self.assertEqual(popup.selected_dates(), [minimum.addDays(1)])
        finally:
            popup.close()

    def test_calendar_hides_week_numbers_and_blocks_adjacent_month_dates(self):
        minimum = QDate(2026, 7, 15)
        selected = [QDate(2026, 8, 3)]
        popup = MultiDatePopup(minimum, minimum.addDays(27), selected)
        try:
            popup.show()
            self.app.processEvents()
            self.assertEqual(
                popup.calendar.verticalHeaderFormat(),
                popup.calendar.VerticalHeaderFormat.NoVerticalHeader,
            )
            self.assertEqual(popup.month_label.text(), "August 2026")
            self.assertFalse(popup.calendar.is_displayed_month_date(QDate(2026, 7, 30)))
            self.assertTrue(popup.calendar.is_displayed_month_date(QDate(2026, 8, 3)))

            view = popup.calendar.findChild(QTableView, "qt_calendar_calendarview")
            adjacent_july_30 = view.model().index(1, 3)
            self.assertEqual(str(adjacent_july_30.data()), "30")
            QTest.mouseClick(
                view.viewport(),
                Qt.LeftButton,
                pos=view.visualRect(adjacent_july_30).center(),
            )
            self.app.processEvents()
            self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2026, 8))
            self.assertEqual(popup.selected_dates(), selected)
        finally:
            popup.close()

    def test_calendar_stays_on_second_month_after_selecting_a_date(self):
        minimum = QDate(2026, 7, 16)
        popup = MultiDatePopup(minimum, minimum.addDays(27), [minimum])
        try:
            popup.show()
            popup.calendar.showNextMonth()
            self.app.processEvents()
            view = popup.calendar.findChild(QTableView, 'qt_calendar_calendarview')
            august_3 = view.model().index(2, 0)
            self.assertEqual(str(august_3.data()), '3')
            QTest.mouseClick(
                view.viewport(),
                Qt.LeftButton,
                pos=view.visualRect(august_3).center(),
            )
            self.app.processEvents()
            self.assertEqual((popup.calendar.yearShown(), popup.calendar.monthShown()), (2026, 8))
            self.assertEqual(popup.selected_dates(), [minimum, QDate(2026, 8, 3)])
        finally:
            popup.close()

    def test_date_control_opens_an_anchored_dropdown_and_marks_today(self):
        today = perth_today()
        host = QWidget()
        layout = QVBoxLayout(host)
        button = MultiDateButton(today, today.addDays(27), [today.addDays(1)])
        layout.addWidget(button)
        try:
            host.show()
            self.app.processEvents()
            QTest.mouseClick(button, Qt.LeftButton)
            self.app.processEvents()
            popup = button.picker_popup()
            self.assertIsInstance(popup, MultiDatePopup)
            self.assertTrue(popup.isVisible())
            self.assertTrue(bool(popup.windowFlags() & Qt.WindowType.Popup))
            self.assertIs(popup.parentWidget(), host)
            anchor_bottom = button.mapToGlobal(button.rect().bottomLeft())
            self.assertGreaterEqual(popup.y(), anchor_bottom.y())
            self.assertLessEqual(abs(popup.x() - anchor_bottom.x()), 12)
            self.assertIn("TODAY", popup.today_label.text())
            self.assertIn(today.toString("dddd, d MMMM yyyy").upper(), popup.today_label.text())
            self.assertTrue(popup.calendar.dateTextFormat(today).fontUnderline())
            self.assertTrue(button.text().startswith("Tomorrow"))
            popup.cancel_button.click()
            self.app.processEvents()
            self.assertEqual(button.selected_qdates(), [today.addDays(1)])
        finally:
            host.close()
            self.app.processEvents()

    def test_multi_date_dropdown_accepts_a_real_mouse_click_and_applies(self):
        minimum = QDate(2026, 7, 15)
        host = QWidget()
        layout = QVBoxLayout(host)
        button = MultiDateButton(minimum, minimum.addDays(27), [minimum])
        layout.addWidget(button)
        try:
            host.show()
            self.app.processEvents()
            QTest.mouseClick(button, Qt.LeftButton)
            self.app.processEvents()
            popup = button.picker_popup()
            view = popup.calendar.findChild(QTableView, "qt_calendar_calendarview")
            target = next(
                index
                for row in range(view.model().rowCount())
                for column in range(view.model().columnCount())
                if str((index := view.model().index(row, column)).data()) == "25"
            )
            QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(target).center())
            self.app.processEvents()
            self.assertEqual(popup.selected_dates(), [minimum, QDate(2026, 7, 25)])
            self.assertEqual(popup.count_label.text(), "2 dates selected")
            self.assertIn("Wed, 15 Jul 2026", popup.summary_label.text())
            self.assertIn("Sat, 25 Jul 2026", popup.summary_label.text())
            QTest.mouseClick(popup.done_button, Qt.LeftButton)
            self.app.processEvents()
            self.assertEqual(button.selected_qdates(), [minimum, QDate(2026, 7, 25)])
            self.assertTrue(button.text().startswith("2 dates"))
        finally:
            host.close()
            self.app.processEvents()

    def test_cache_worker_fetches_each_date_and_returns_keyed_snapshots(self):
        dates = ["2026-07-20", "2026-07-21", "2026-07-22"]
        emitted = []
        worker = CacheWorker(dates, "18")
        worker.finished.connect(emitted.append)
        with patch(
            "app.qt_golfhub_app.fetch_shared_snapshot",
            side_effect=lambda date_str, holes: {"date": date_str, "holes": holes},
        ) as fetch:
            worker.run()
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(set(emitted[0]), set(dates))
        self.assertEqual(emitted[0]["2026-07-21"]["holes"], "18")

    def test_results_are_grouped_by_day_and_only_open_day_is_built(self):
        window = self.make_window()
        try:
            site = next(site for site in window.sites if site.provider != "direct" and "18" in site.holes)
            dates = ["2026-07-20", "2026-07-21", "2026-07-22"]
            window.context = {
                "sites": [site],
                "date": dates[0],
                "dates": dates,
                "holes": "18",
                "players": None,
                "from": None,
                "to": None,
            }

            def result(rows):
                return {
                    "site_name": site.name,
                    "url": "https://example.com",
                    "hole_label": "18 holes",
                    "decorated_rows": rows,
                    "weather": None,
                    "error": None,
                }

            days = [
                {"date": dates[0], "results": [result([])], "source": "Shared cache"},
                {
                    "date": dates[1],
                    "results": [result([{"time": "8:00 am", "minutes": 480, "spots": 4}])],
                    "source": "Shared cache",
                },
                {
                    "date": dates[2],
                    "results": [result([{"time": "9:00 am", "minutes": 540, "spots": 2}])],
                    "source": "Shared cache",
                },
            ]
            window.render_multi_results(days, "3 of 3 dates loaded")
            sections = window.findChildren(DaySection)
            self.assertEqual(len(sections), 3)
            self.assertFalse(sections[0]._built)
            self.assertTrue(sections[1]._built)
            self.assertFalse(sections[2]._built)
            self.assertEqual(len(window.findChildren(ResultCard)), 1)
            self.assertIn("TUESDAY, 21 JULY 2026", sections[1].toggle.text())

            sections[2].set_expanded(True)
            self.assertTrue(sections[2]._built)
            self.assertEqual(len(window.findChildren(ResultCard)), 2)
        finally:
            window.close()

    def test_partial_cache_still_labels_every_requested_day(self):
        window = self.make_window()
        try:
            site = next(site for site in window.sites if site.provider != "direct" and "18" in site.holes)
            dates = ["2026-07-20", "2026-07-21", "2026-07-22"]
            window.context = {
                "sites": [site],
                "date": dates[0],
                "dates": dates,
                "holes": "18",
                "players": None,
                "from": None,
                "to": None,
            }
            payload = {"generated_at": "2026-07-15T00:00:00Z", "results": []}
            window.render_snapshot_batch(
                {dates[0]: payload, dates[2]: payload},
                {dates[0]: "Shared cache", dates[2]: "Saved on this device"},
            )
            self.assertEqual(len(window.findChildren(DaySection)), 3)
            sources = [label.text() for label in window.findChildren(QLabel, "DaySource")]
            self.assertIn("Cache unavailable for this date", sources)
            self.assertEqual(window.header_status.text(), "SHARED CACHE / 2 OF 3 DAYS")
        finally:
            window.close()


    def test_twenty_eight_day_result_view_builds_only_one_day_body(self):
        window = self.make_window()
        try:
            site = next(site for site in window.sites if site.provider != "direct" and "18" in site.holes)
            dates = [QDate(2026, 7, 15).addDays(offset).toString("yyyy-MM-dd") for offset in range(28)]
            window.context = {
                "sites": [site],
                "date": dates[0],
                "dates": dates,
                "holes": "18",
                "players": None,
                "from": None,
                "to": None,
            }
            result = {
                "site_name": site.name,
                "url": "https://example.com",
                "hole_label": "18 holes",
                "decorated_rows": [{"time": "8:00 am", "minutes": 480, "spots": 4}],
                "weather": None,
                "error": None,
            }
            window.render_multi_results(
                [{"date": date_str, "results": [result], "source": "Shared cache"} for date_str in dates],
                "28 of 28 dates loaded",
            )
            sections = window.findChildren(DaySection)
            self.assertEqual(len(sections), 28)
            self.assertEqual(sum(section._built for section in sections), 1)
            self.assertEqual(len(window.findChildren(ResultCard)), 1)
        finally:
            window.close()


    def test_each_day_renders_course_cards_alphabetically(self):
        window = self.make_window()
        try:
            sites = [site for site in window.sites if site.provider != "direct" and "18" in site.holes][:3]
            window.context = {
                "sites": sites,
                "date": "2026-07-20",
                "dates": ["2026-07-20"],
                "holes": "18",
                "players": None,
                "from": None,
                "to": None,
            }
            results = [
                {
                    "site_name": site.name,
                    "url": "https://example.com",
                    "hole_label": "18 holes",
                    "decorated_rows": [{"time": "8:00 am", "minutes": 480, "spots": 4}],
                    "weather": None,
                    "error": None,
                }
                for site in reversed(sites)
            ]
            window.render_multi_results(
                [{"date": "2026-07-20", "results": results, "source": "Shared cache"}],
                "1 of 1 dates loaded",
            )
            cards = window.day_sections[0].body.findChildren(ResultCard)
            names = [card.result["site_name"] for card in cards]
            self.assertEqual(names, sorted(names, key=str.casefold))
        finally:
            window.close()


class CacheWorkerCompletionTests(unittest.TestCase):
    """Executor failures use the same missing-cache contract as failed fetches."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.callback_errors = []
        for target in ("socket.create_connection", "socket.socket.connect", "socket.getaddrinfo",
                       "webbrowser.open", "app.qt_golfhub_app.fetch_shared_snapshot",
                       "app.qt_golfhub_app.save_local_snapshot"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline completion test")))
        self.enterContext(patch("sys.excepthook", side_effect=lambda *a: self.callback_errors.append(str(a[1]))))
        self.enterContext(patch("app.qt_golfhub_app.perth_today", return_value=QDate(2033, 1, 2)))
        self.dates = ["2033-01-02", "2033-01-04"]
        self.payloads = [{"schema": 1, "date": date, "holes": "18",
                          "generated_at": "2033-01-02T00:00:00Z", "results": []}
                         for date in self.dates]

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [])

    def pool(self, values):
        from concurrent.futures import Future
        from unittest.mock import MagicMock
        pool = MagicMock()
        pool.__enter__.return_value = pool
        jobs = []
        for value in values:
            job = Future()
            if isinstance(value, Exception):
                job.set_exception(value)
            else:
                job.set_result(value)
            jobs.append(job)
        pool.submit.side_effect = jobs
        return pool, jobs

    def complete(self, dates=None, receiver=None, holes="18"):
        worker = CacheWorker(self.dates if dates is None else dates, holes)
        emitted = []
        worker.finished.connect(emitted.append)
        if receiver is not None:
            worker.finished.connect(receiver)
        escaped = None
        try:
            worker.run()
        except Exception as error:
            escaped = f"{type(error).__name__}: {error}"
        self.assertIsNone(escaped, "Cache errors must complete rather than escape the Qt slot")
        self.assertEqual(len(emitted), 1, "Exactly one completion must reach the existing recovery path")
        return emitted[0]

    def window(self, dates):
        with patch.object(GolfHub, "show_initial_cache"):
            window = GolfHub()
        window._stop_deferred_timers()
        window.show()
        site = next(site for site in window.sites if site.name == "Altone Park")
        window.context = {"sites": [site], "date": dates[0], "dates": dates,
                          "holes": "18", "from": None, "to": None, "players": None}
        window._active_cache_context = window._snapshot_search_context(window.context)
        return window

    def test_executor_setup_and_submission_failures_complete_once(self):
        for stage in ("constructor", "enter", "first_submit", "second_submit"):
            with self.subTest(stage=stage):
                pool, jobs = self.pool(self.payloads)
                error = RuntimeError("Synthetic executor " + stage)
                if stage == "enter":
                    pool.__enter__.side_effect = error
                elif stage == "first_submit":
                    pool.submit.side_effect = error
                elif stage == "second_submit":
                    pool.submit.side_effect = [jobs[0], error]
                with patch("app.qt_golfhub_app.ThreadPoolExecutor", return_value=pool,
                           side_effect=error if stage == "constructor" else None):
                    self.assertEqual(self.complete(), {})

    def test_completion_iteration_failure_retains_collected_snapshot(self):
        pool, jobs = self.pool(self.payloads)
        def interrupted(_jobs):
            yield jobs[0]
            raise RuntimeError("Synthetic completion iterator failure")
        with patch("app.qt_golfhub_app.ThreadPoolExecutor", return_value=pool), \
                patch("app.qt_golfhub_app.as_completed", side_effect=interrupted):
            actual = self.complete()
        self.assertEqual(actual, {self.dates[0]: self.payloads[0]})
        self.assertIs(actual[self.dates[0]], self.payloads[0])

    def test_executor_exit_failure_retains_completed_snapshots(self):
        pool, _ = self.pool(self.payloads)
        pool.__exit__.side_effect = RuntimeError("Synthetic executor exit failure")
        with patch("app.qt_golfhub_app.ThreadPoolExecutor", return_value=pool):
            self.assertEqual(self.complete(), dict(zip(self.dates, self.payloads)))

    def test_failed_fetch_remains_missing_while_other_date_succeeds(self):
        pool, _ = self.pool([RuntimeError("Synthetic fetch failure"), self.payloads[1]])
        with patch("app.qt_golfhub_app.ThreadPoolExecutor", return_value=pool):
            self.assertEqual(self.complete(), {self.dates[0]: None, self.dates[1]: self.payloads[1]})
        self.assertEqual([call.args[1:] for call in pool.submit.call_args_list],
                         [(date, "18") for date in self.dates])

    def test_string_date_and_empty_input_preserve_success_contract(self):
        for dates, values, expected in ((self.dates[0], [self.payloads[0]], {self.dates[0]: self.payloads[0]}),
                                        ([], [], {})):
            with self.subTest(dates=dates):
                pool, _ = self.pool(values)
                with patch("app.qt_golfhub_app.ThreadPoolExecutor", return_value=pool):
                    self.assertEqual(self.complete(dates=dates, holes="9"), expected)
                self.assertEqual(pool.submit.call_count, len(values))
                if values:
                    self.assertEqual(pool.submit.call_args.args[1:], (self.dates[0], "9"))

    def test_setup_failure_reuses_saved_cache_for_submitted_context(self):
        window = self.window(self.dates[:1])
        with patch("app.qt_golfhub_app.ThreadPoolExecutor", side_effect=RuntimeError("Synthetic setup failure")), \
                patch("app.qt_golfhub_app.load_local_snapshot", return_value=self.payloads[0]) as local, \
                patch.object(window, "search_live") as live:
            self.complete(dates=self.dates[:1], receiver=window.cache_finished)
        local.assert_called_once_with(self.dates[0], "18")
        live.assert_not_called()
        self.assertTrue(window.header_status.text().startswith("SAVED CACHE / "))
        self.assertEqual(window.context, window._active_cache_context)

    def test_setup_failure_without_saved_cache_reaches_single_date_live_fallback(self):
        window = self.window(self.dates[:1])
        submitted = window._snapshot_search_context(window.context)
        with patch("app.qt_golfhub_app.ThreadPoolExecutor", side_effect=RuntimeError("Synthetic setup failure")), \
                patch("app.qt_golfhub_app.load_local_snapshot", return_value=None), \
                patch.object(window, "search_live") as live:
            self.complete(dates=self.dates[:1], receiver=window.cache_finished)
        live.assert_called_once_with(submitted)

    def test_setup_failure_without_multiday_cache_keeps_official_link_recovery(self):
        window = self.window(self.dates)
        with patch("app.qt_golfhub_app.ThreadPoolExecutor", side_effect=RuntimeError("Synthetic setup failure")), \
                patch("app.qt_golfhub_app.load_local_snapshot", return_value=None), \
                patch.object(window, "search_live") as live:
            self.complete(receiver=window.cache_finished)
        live.assert_not_called()
        self.assertEqual(window.header_status.text(), "SHARED CACHE UNAVAILABLE")
        self.assertEqual(window.status.text(), "Multi-day cache temporarily unavailable")
        self.assertEqual([result["site_name"] for result in window.last_results], ["Altone Park"])
        labels = [label.text() for label in window.results_body.findChildren(QLabel)]
        self.assertIn("Official booking links", labels)
        self.assertTrue(any("No cached results were available" in label for label in labels))


if __name__ == "__main__":
    unittest.main()

