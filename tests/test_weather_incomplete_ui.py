import copy
import os
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from app import golfhub_core as core
from app.qt_golfhub_app import WeatherBadge


DAY = "2026-10-25"
QUERY = "coords:-31.95,115.86"


def zero_daily():
    return {
        "time": [DAY],
        "weather_code": [0],
        "temperature_2m_max": [0],
        "temperature_2m_min": [0],
        "precipitation_probability_max": [0],
        "precipitation_sum": [0],
        "wind_speed_10m_max": [0],
    }


class IncompleteWeatherUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        core.preload_weather_cache({})
        self.addCleanup(core.preload_weather_cache, {})
        network = patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected live request"))
        network_mock = network.start()
        self.addCleanup(network.stop)
        self.addCleanup(network_mock.assert_not_called)

    def lookup(self, daily):
        core.preload_weather_cache({})
        with (
            patch.object(core, "geocode_location", return_value=(-31.95, 115.86)) as geocode,
            patch.object(core, "fetch_json", return_value={"daily": copy.deepcopy(daily)}) as fetch,
        ):
            weather = core.get_weather_for_date(QUERY, DAY, "Course")
        geocode.assert_called_once_with(QUERY)
        fetch.assert_called_once()
        return weather

    def badge(self, weather, compact):
        widget = WeatherBadge(weather, compact=compact)
        self.addCleanup(widget.close)
        widget.show()
        self.app.processEvents()
        title = widget.findChild(QLabel, "WeatherTitle")
        self.assertIsNotNone(title)
        self.assertTrue(title.isVisible())
        return widget, title

    def test_incomplete_provider_days_display_unavailable_in_both_layouts(self):
        all_null = {key: values if key == "time" else [None] for key, values in zero_daily().items()}
        missing_code = zero_daily()
        del missing_code["weather_code"]
        null_temperatures = {**zero_daily(), "temperature_2m_max": None}
        short_wind = {**zero_daily(), "wind_speed_10m_max": []}
        fixtures = {
            "all null values": all_null,
            "missing weather code": missing_code,
            "null temperature array": null_temperatures,
            "short wind array": short_wind,
        }
        for name, daily in fixtures.items():
            for compact in (False, True):
                with self.subTest(fixture=name, compact=compact):
                    with self.assertLogs(level="WARNING"):
                        weather = self.lookup(daily)
                    self.assertIsNone(weather)
                    widget, title = self.badge(weather, compact)
                    self.assertEqual(title.text(), "Forecast unavailable")
                    self.assertIsNone(widget.findChild(QLabel, "WeatherDetail"))
                    for label in widget.findChildren(QLabel):
                        self.assertNotIn("Clear", label.text())
                        self.assertNotIn("0 C", label.text())

    def test_genuine_zero_forecast_remains_visible_in_both_layouts(self):
        for compact in (False, True):
            with self.subTest(compact=compact):
                weather = self.lookup(zero_daily())
                self.assertIsNotNone(weather)
                widget, title = self.badge(weather, compact)
                self.assertEqual(title.text(), "Clear   0-0 C")
                detail = widget.findChild(QLabel, "WeatherDetail")
                if compact:
                    self.assertIsNone(detail)
                else:
                    self.assertIsNotNone(detail)
                    self.assertTrue(detail.isVisible())
                    self.assertEqual(detail.text(), "Rain 0%   |   Wind 0 km/h")


if __name__ == "__main__":
    unittest.main()
