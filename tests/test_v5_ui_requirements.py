import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from app.qt_golfhub_app import GolfHub, ResultCard, TeeTimeCard


class V5UIRequirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        with patch.object(GolfHub, "show_initial_cache"):
            return GolfHub()

    @staticmethod
    def live_result(name, time="8:00 am"):
        return {
            "site_name": name,
            "url": "https://example.com/guests/bookings/ViewPublicTimesheet.msp",
            "hole_label": "18 holes",
            "decorated_rows": [{"time": time, "minutes": 480, "spots": 4}],
            "weather": None,
            "error": None,
        }

    def test_single_day_course_cards_are_alphabetical(self):
        window = self.make_window()
        try:
            sites = [site for site in window.sites if site.provider != "direct" and "18" in site.holes][:4]
            window.context = {
                "sites": sites,
                "date": "2026-07-23",
                "dates": ["2026-07-23"],
                "holes": "18",
                "players": None,
                "from": None,
                "to": None,
            }
            results = [self.live_result(site.name) for site in reversed(sites)]
            window.render_results(results, "Test cache")
            names = [card.result["site_name"] for card in window.findChildren(ResultCard)]
            self.assertEqual(names, sorted(names, key=str.casefold))
        finally:
            window.close()

    def test_player_filter_and_summary_only_include_large_enough_groups(self):
        window = self.make_window()
        try:
            site = next(site for site in window.sites if site.provider != "direct" and "18" in site.holes)
            window.context = {
                "sites": [site], "date": "2026-07-23", "dates": ["2026-07-23"],
                "holes": "18", "players": 4, "from": None, "to": None,
            }
            result = self.live_result(site.name)
            result["decorated_rows"] = [
                {"time": "8:00 am", "minutes": 480, "spots": 1},
                {"time": "8:10 am", "minutes": 490, "spots": 2},
                {"time": "8:20 am", "minutes": 500, "spots": 4},
            ]
            window.render_results([result], "Test cache")
            rows = window.findChildren(TeeTimeCard)
            self.assertEqual([row.row["spots"] for row in rows], [4])
            summary = next(
                label.text() for label in window.findChildren(QLabel)
                if label.objectName() == "SummaryValue"
            )
            self.assertEqual(summary, "1 matching time")
            self.assertIn("1 matching tee time across 1 course", window.status.text())
        finally:
            window.close()

    def test_player_choice_is_clear_branded_and_has_no_warning_icon(self):
        window = self.make_window()
        plan = SimpleNamespace(
            requested_players=4,
            course_name="Links Kennedy Bay",
            tee_time="7:02 am",
        )
        try:
            captured = {}
            def make_box(parent):
                captured["box"] = QMessageBox(parent)
                return captured["box"]
            with (
                patch("app.qt_golfhub_app.QMessageBox", side_effect=make_box) as box_type,
                patch.object(QMessageBox, "exec", return_value=0),
            ):
                box_type.NoIcon = QMessageBox.NoIcon
                box_type.AcceptRole = QMessageBox.AcceptRole
                box_type.ActionRole = QMessageBox.ActionRole
                box_type.RejectRole = QMessageBox.RejectRole
                self.assertEqual(window._booking_choice(plan), "cancel")
            box = captured["box"]
            self.assertEqual(box.icon(), QMessageBox.NoIcon)
            self.assertEqual(box.windowTitle(), "Continue to the course")
            self.assertIn("How would you like to continue?", box.text())
            self.assertIn("GolfHub never confirms, checks out or pays", box.informativeText())
            self.assertEqual(
                {button.text() for button in box.buttons()},
                {"PREPARE & OPEN", "OPEN NORMALLY", "GO BACK"},
            )
            self.assertEqual(box.defaultButton().text(), "PREPARE & OPEN")
        finally:
            window.close()

    def test_protected_wembley_is_availability_not_zero_result(self):
        window = self.make_window()
        try:
            site = next(site for site in window.sites if site.name == "Wembley")
            window.context = {
                "sites": [site],
                "date": "2026-07-23",
                "dates": ["2026-07-23"],
                "holes": "18",
                "players": 4,
                "from": None,
                "to": None,
            }
            result = {
                "site_name": "Wembley",
                "url": "https://www.wembleygolf.com.au/guests/bookings/ViewPublicCalendar.msp",
                "hole_label": "18 holes",
                "decorated_rows": [],
                "weather": None,
                "error": None,
                "calendar_availability": "available",
                "calendar_captcha_enabled": True,
                "booking_note": "Open the protected official sheet to choose an exact time.",
            }
            window.render_results([result], "Test cache")
            labels = [label.text() for label in window.findChildren(QLabel)]
            buttons = [button.text() for button in window.findChildren(QPushButton)]
            self.assertIn("Wembley bookings available", labels)
            self.assertTrue(any("quick check before showing exact times" in text for text in labels))
            self.assertIn("VIEW WEMBLEY TIMES", buttons)
            self.assertIn("Wembley has booking availability", window.status.text())
            self.assertNotIn("0 matching", window.status.text())

            for captcha_value in (None, False):
                result["calendar_captcha_enabled"] = captcha_value
                window.render_results([result], "Older cache")
                summary = next(
                    label.text()
                    for label in window.results_layout.itemAt(0).widget().findChildren(QLabel)
                    if label.objectName() == "SummaryValue"
                )
                self.assertEqual(summary, "Wembley bookings available")
                self.assertNotIn("0 matching", window.status.text())
        finally:
            window.close()

    def test_multiday_protected_wembley_headline_is_honest(self):
        window = self.make_window()
        try:
            site = next(site for site in window.sites if site.name == "Wembley")
            dates = ["2026-07-23", "2026-07-24"]
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
                "site_name": "Wembley",
                "url": "https://www.wembleygolf.com.au/guests/bookings/ViewPublicCalendar.msp",
                "hole_label": "18 holes",
                "decorated_rows": [],
                "weather": None,
                "error": None,
                "calendar_availability": "available",
                "calendar_captcha_enabled": True,
            }
            window.render_multi_results(
                [
                    {"date": dates[0], "results": [result], "source": "Test cache"},
                    {"date": dates[1], "results": [result], "source": "Test cache"},
                ],
                "2 of 2 dates loaded",
            )
            labels = [label.text() for label in window.findChildren(QLabel)]
            self.assertIn("Wembley bookings available across 2 dates", labels)
            self.assertIn("Wembley has bookings available on 2 selected dates", window.status.text())

            for captcha_value in (None, False):
                result["calendar_captcha_enabled"] = captcha_value
                window.render_multi_results(
                    [
                        {"date": dates[0], "results": [result], "source": "Older cache"},
                        {"date": dates[1], "results": [result], "source": "Older cache"},
                    ],
                    "2 of 2 dates loaded",
                )
                summary = next(
                    label.text()
                    for label in window.results_layout.itemAt(0).widget().findChildren(QLabel)
                    if label.objectName() == "SummaryValue"
                )
                self.assertEqual(summary, "Wembley bookings available across 2 dates")
                self.assertNotIn("0 matching", window.status.text())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

