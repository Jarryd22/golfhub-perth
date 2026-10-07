import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from app import golfhub_core as core
from app import shared_cache
from app.qt_golfhub_app import WeatherBadge


NOW = datetime(2026, 10, 7, 0, 10, tzinfo=timezone.utc)


class WeatherAgeUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        core_clock = patch.object(core, "datetime", wraps=datetime)
        core_clock.start().now.return_value = NOW
        self.addCleanup(core_clock.stop)
        display_clock = patch.object(shared_cache, "datetime", wraps=datetime)
        display_clock.start().now.return_value = NOW
        self.addCleanup(display_clock.stop)

    @staticmethod
    def forecast():
        return {
            "label": "Rain", "icon_file": "sheet_rain.png", "tmin": 9, "tmax": 18,
            "rain_chance": 80, "wind": 25,
            "fetched_at": (NOW - timedelta(minutes=20)).isoformat(), "reused": True,
        }

    def badge(self, forecast, compact):
        widget = WeatherBadge(forecast, compact=compact)
        self.addCleanup(widget.close)
        widget.show()
        self.app.processEvents()
        title = widget.findChild(QLabel, "WeatherTitle")
        self.assertIsNotNone(title)
        self.assertTrue(title.isVisible())
        return widget, title

    def test_recent_reused_forecast_is_visibly_cached_in_both_layouts(self):
        for compact in (False, True):
            with self.subTest(compact=compact):
                forecast = self.forecast()
                widget, title = self.badge(forecast, compact)
                self.assertIn("Rain (cached)", title.text())
                self.assertIn("9-18 C", title.text())
                self.assertIn("20 minutes ago", title.toolTip())
                self.assertIn(forecast["fetched_at"], title.toolTip())
                if not compact:
                    detail = widget.findChild(QLabel, "WeatherDetail")
                    self.assertTrue(detail.isVisible())
                    self.assertIn("Rain 80%", detail.text())

    def test_expired_future_and_naive_forecasts_are_unavailable_in_both_layouts(self):
        stamps = ((NOW - timedelta(hours=1)).isoformat(),
                  (NOW + timedelta(seconds=1)).isoformat(),
                  NOW.replace(tzinfo=None).isoformat())
        for compact in (False, True):
            for stamp in stamps:
                with self.subTest(compact=compact, stamp=stamp):
                    widget, title = self.badge({**self.forecast(), "fetched_at": stamp}, compact)
                    self.assertEqual(title.text(), "Forecast unavailable")
                    self.assertEqual(title.toolTip(), "")
                    self.assertIsNone(widget.findChild(QLabel, "WeatherDetail"))

    def test_new_shared_forecast_is_not_labelled_as_reused(self):
        for compact in (False, True):
            with self.subTest(compact=compact):
                forecast = {**self.forecast(), "reused": False}
                _, title = self.badge(forecast, compact)
                self.assertNotIn("(cached)", title.text())
                self.assertIn("Rain", title.text())
                self.assertIn(forecast["fetched_at"], title.toolTip())


if __name__ == "__main__":
    unittest.main()
