import os
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QTableView, QVBoxLayout, QWidget

from app.qt_golfhub_app import (
    CacheWorker,
    DaySection,
    GolfHub,
    MAX_SEARCH_DAYS,
    MultiDateButton,
    MultiDatePopup,
    ResultCard,
    consecutive_date_strings,
)


class MultiDayUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

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
        today = QDate.currentDate()
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


if __name__ == "__main__":
    unittest.main()

