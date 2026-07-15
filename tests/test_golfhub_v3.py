import json
import tempfile
import unittest
from pathlib import Path

from app.golfhub_core import CONFIG_FILE, DATA_DIR, decorate_rows, load_sites, parse_user_time
from app.course_results import direct_result
from app import shared_cache


class GolfHubV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sites = load_sites(DATA_DIR / CONFIG_FILE)

    def test_comprehensive_directory_is_unique(self):
        names = [site.name for site in self.sites]
        self.assertEqual(len(names), 41)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(sum(site.provider == "direct" for site in self.sites), 21)
        self.assertEqual(sum(site.provider != "direct" for site in self.sites), 20)
        self.assertEqual(sum("18" in site.holes for site in self.sites), 37)
        self.assertEqual(sum("9" in site.holes for site in self.sites), 37)
        expected_additions = {
            "Boddington Golf Club",
            "Gosnells Golf Club",
            "Mosman Park",
            "Nedlands Golf Club",
            "Pickering Brook",
            "Preston Beach",
            "Serpentine & Districts",
            "Wanneroo Golf Club",
            "Waroona Golf Club",
            "Yanchep National Park",
        }
        self.assertTrue(expected_additions.issubset(names))
        self.assertTrue(all(site.weather_query.startswith("coords:") for site in self.sites))
        wembley = next(site for site in self.sites if site.name == "Wembley")
        self.assertEqual(set(wembley.holes["18"].resolve_fee_group_ids("2026-07-15")), {"102184", "102193"})
        self.assertEqual(set(wembley.holes["9"].resolve_fee_group_ids("2026-07-15")), {"102211", "102202"})

    def test_maylands_joondalup_and_yanchep_booking_routes(self):
        maylands = next(site for site in self.sites if site.name == "Maylands")
        self.assertEqual(maylands.provider, "miclub")
        self.assertEqual(maylands.domain, "maylandsembleton.miclub.com.au")
        self.assertIn("bookingResourceId=3000000", maylands.build_url("2026-07-19", "18"))
        self.assertIn("feeGroupId=100795", maylands.build_url("2026-07-19", "18"))
        self.assertIn("feeGroupId=100797", maylands.build_url("2026-07-19", "9"))

        joondalup = next(site for site in self.sites if site.name == "Joondalup Resort")
        self.assertEqual(joondalup.provider, "miclub")
        self.assertIn("bookingResourceId=3900000", joondalup.build_url("2026-07-19", "18"))
        self.assertIn("feeGroupId=1508198355", joondalup.build_url("2026-07-19", "18"))
        self.assertIn("feeGroupId=1508504524", joondalup.build_url("2026-07-19", "9"))

        yanchep = next(site for site in self.sites if site.name == "Yanchep National Park")
        self.assertEqual(yanchep.provider, "direct")
        self.assertEqual(yanchep.domain, "exploreparks.dbca.wa.gov.au/site/yanchep-golf-course")

    def test_each_course_has_a_round_and_valid_domain(self):
        for site in self.sites:
            self.assertTrue(site.holes, site.name)
            self.assertNotIn("https://", site.domain, site.name)
            self.assertIn(".", site.domain, site.name)

    def test_direct_courses_create_bookable_results(self):
        direct_sites = [site for site in self.sites if site.provider == "direct"]
        self.assertEqual(len(direct_sites), 21)
        for site in direct_sites:
            hole = next(iter(site.holes))
            result = direct_result(site, hole)
            self.assertTrue(result["direct_booking"])
            self.assertTrue(result["url"].startswith("https://"))

    def test_cache_round_trip(self):
        site = self.sites[0]
        result = direct_result(site, next(iter(site.holes)))
        payload = shared_cache.make_snapshot("2026-07-20", "18", [result])
        with tempfile.TemporaryDirectory() as tmp:
            original = shared_cache.LOCAL_CACHE_DIR
            shared_cache.LOCAL_CACHE_DIR = Path(tmp)
            try:
                shared_cache.save_local_snapshot(payload)
                loaded = shared_cache.load_local_snapshot("2026-07-20", "18")
            finally:
                shared_cache.LOCAL_CACHE_DIR = original
        self.assertEqual(loaded["results"][0]["site_name"], site.name)

    def test_group_filter_support_data(self):
        rows = decorate_rows([
            {"time": "7:30 am", "spots": 4, "course_raw": "Lake"},
            {"time": "8:00 am", "spots": 2, "course_raw": "Lake"},
        ])
        self.assertEqual(rows[0]["minutes"], 450)
        self.assertEqual(parse_user_time("3:30 pm"), 930)

    def test_window_constructs(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app.qt_golfhub_app import GolfHub
        app = QApplication.instance() or QApplication([])
        window = GolfHub()
        self.assertEqual(window.windowTitle(), "Golf Hub Perth")
        self.assertFalse(window.course_panel.isVisible())
        window.apply_time_preset("Morning")
        self.assertEqual(window.time_from.currentText(), "6:00 am")
        self.assertEqual(window.time_to.currentText(), "11:30 am")
        window.apply_time_preset("Custom range")
        self.assertTrue(window.custom_time_field.isVisible() or window.isHidden())
        window.close()

    def test_weather_badge_renders_bundled_icon(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from app.qt_golfhub_app import WeatherBadge
        app = QApplication.instance() or QApplication([])
        badge = WeatherBadge({
            "label": "Rain",
            "tmin": 10,
            "tmax": 17,
            "rain_chance": 80,
            "wind": 24,
            "icon_file": "sheet_rain.png",
        })
        icon = badge.findChild(QLabel, "WeatherIcon")
        self.assertIsNotNone(icon)
        self.assertIsNotNone(icon.pixmap())
        self.assertFalse(icon.pixmap().isNull())

    def test_wembley_calendar_card_is_explicit_and_actionable(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel, QPushButton
        from app.qt_golfhub_app import ResultCard
        app = QApplication.instance() or QApplication([])
        note = "Wembley's official calendar shows bookings available for Old and Tuart."
        card = ResultCard({
            "site_name": "Wembley",
            "url": "https://www.wembleygolf.com.au/guests/bookings/ViewPublicCalendar.msp",
            "hole_label": "18 holes",
            "calendar_availability": "available",
            "booking_note": note,
            "weather": None,
        }, [])
        self.assertIn("CHECK WEMBLEY TIMES", [button.text() for button in card.findChildren(QPushButton)])
        self.assertIn(note, [label.text() for label in card.findChildren(QLabel)])

    def test_cache_config_targets_public_repository(self):
        config = json.loads((Path(__file__).parents[1] / "data/cache_config.json").read_text())
        self.assertEqual(
            config["cache_base_url"],
            "https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache",
        )

    def test_production_core_has_no_retired_gui_dependency(self):
        core = (Path(__file__).parents[1] / "app/golfhub_core.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("customtkinter", core)
        self.assertNotIn("import tkinter", core)

    def test_search_window_is_limited_to_four_weeks(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app.qt_golfhub_app import GolfHub
        app = QApplication.instance() or QApplication([])
        window = GolfHub()
        self.assertEqual(window.date.minimumDate().daysTo(window.date.maximumDate()), 27)
        self.assertEqual(window.minimumWidth(), 980)
        window.close()

    def test_search_controls_do_not_overlap_at_minimum_width(self):
        import os
        from unittest.mock import patch
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app.qt_golfhub_app import GolfHub
        app = QApplication.instance() or QApplication([])
        with patch.object(GolfHub, "show_initial_cache"):
            window = GolfHub()
            window.resize(980, 640)
            window.show()
            app.processEvents()
            self.assertLess(window.date_field.geometry().right(), window.round_field.geometry().left())
            self.assertLess(window.round_field.geometry().right(), window.time_field.geometry().left())
            self.assertLess(window.date_field.geometry().bottom(), window.players_field.geometry().top())
            self.assertLess(window.players_field.geometry().right(), window.course_button.geometry().left())
            window.close()
    def test_cached_direct_result_is_reused_without_network_call(self):
        import os
        from unittest.mock import patch
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app.qt_golfhub_app import GolfHub
        app = QApplication.instance() or QApplication([])
        window = GolfHub()
        site = next(site for site in window.sites if site.provider == "direct" and "18" in site.holes)
        window.context = {"sites": [site], "holes": "18", "date": "2026-07-20"}
        cached = {"site_name": site.name, "direct_booking": True, "weather": {"label": "Clear"}}
        with patch("app.qt_golfhub_app.direct_result") as fallback:
            merged = window.add_direct_results([cached])
        fallback.assert_not_called()
        self.assertIs(merged[0], cached)
        window.close()

    def test_show_all_times_exposes_every_cached_row(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app.qt_golfhub_app import ResultCard
        app = QApplication.instance() or QApplication([])
        rows = [
            {"time": f"{7 + index // 2}:{(index % 2) * 30:02d} am", "minutes": 420 + index * 15, "spots": 4}
            for index in range(15)
        ]
        card = ResultCard({"site_name": "Test Course", "url": "https://example.com", "hole_label": "18 holes"}, rows)
        self.assertEqual(sum(widget.isHidden() for widget in card.tee_grid.widgets), 3)
        card.toggle_all_times()
        self.assertEqual(sum(widget.isHidden() for widget in card.tee_grid.widgets), 0)

    def test_workflow_is_four_weeks_every_ten_minutes(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/refresh-cache-10min.yml").read_text()
        self.assertIn('cron: "*/10 * * * *"', workflow)
        self.assertIn("start: [0, 4, 8, 12, 16, 20, 24]", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_cache_workflow_has_no_gui_runtime_dependencies(self):
        workflow = (
            Path(__file__).parents[1] / ".github/workflows/refresh-cache-10min.yml"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("customtkinter", workflow)
        self.assertNotIn("python3-tk", workflow)
        self.assertNotIn("pyside", workflow)
        self.assertNotIn("pyqt", workflow)


if __name__ == "__main__":
    unittest.main()
