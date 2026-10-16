import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication, QMessageBox

from app.qt_golfhub_app import GolfHub


class TimeRangeUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.window.show()
        self.app.processEvents()
        self.window.time_preset.setCurrentText("Custom range")

    def tearDown(self):
        self.window.cache_thread = None
        self.window.close()
        self.app.processEvents()

    def set_range(self, start, end):
        self.window.time_from.setCurrentText(start)
        self.window.time_to.setCurrentText(end)

    def test_reversed_range_does_not_launch_cache_or_live_search(self):
        self.set_range("3:00 pm", "9:00 am")
        original = {"date": "2026-10-17", "marker": "previous results"}
        self.window.context = original
        with (
            patch("app.qt_golfhub_app.QMessageBox.exec", autospec=True) as message,
            patch.object(self.window, "_start_cache_search") as start_cache,
            patch("app.qt_golfhub_app.QThread") as thread,
            patch("app.qt_golfhub_app.ScanWorker") as scan,
        ):
            self.window.search_cache()
            self.window.search_live()
        start_cache.assert_not_called()
        thread.assert_not_called()
        scan.assert_not_called()
        self.assertEqual(message.call_count, 2)
        self.assertIn("end time", self.window.findChildren(QMessageBox)[-1].text())
        self.assertIs(self.window.context, original)
        self.assertTrue(self.window.time_to.hasFocus())
        self.assertEqual(self.window.time_from.currentText(), "3:00 pm")
        self.assertEqual(self.window.time_to.currentText(), "9:00 am")

    def test_invalid_range_does_not_replace_a_queued_search(self):
        self.window.cache_thread = Mock()
        pending = {"marker": "valid queued search"}
        self.window._pending_cache_context = pending
        self.set_range("3:00 pm", "9:00 am")
        with patch("app.qt_golfhub_app.QMessageBox.exec", autospec=True):
            self.window.search_cache()
        self.assertIs(self.window._pending_cache_context, pending)

    def test_equal_and_open_bounds_remain_valid(self):
        for start, end, bounds in [
            ("9:00 am", "9:00 am", (540, 540)),
            ("Any", "9:00 am", (None, 540)),
            ("3:00 pm", "Any", (900, None)),
            ("Any", "Any", (None, None)),
        ]:
            with self.subTest(start=start, end=end):
                self.set_range(start, end)
                with patch("app.qt_golfhub_app.QMessageBox.exec", autospec=True) as message:
                    params = self.window.params()
                message.assert_not_called()
                self.assertEqual((params["from"], params["to"]), bounds)

    def test_correction_restores_search_and_inclusive_filtering(self):
        self.set_range("3:00 pm", "9:00 am")
        with patch("app.qt_golfhub_app.QMessageBox.exec", autospec=True):
            self.assertIsNone(self.window.params())
        self.set_range("9:00 am", "3:00 pm")
        with patch.object(self.window, "_start_cache_search") as start:
            self.window.search_cache()
        self.window.context = start.call_args.args[0]
        rows = [{"minutes": n, "spots": 4} for n in (539, 540, 600, 900, 901)]
        self.assertEqual([r["minutes"] for r in self.window.filtered_rows(rows)], [540, 600, 900])

    def test_time_controls_have_distinct_accessible_names(self):
        for control, name in [(self.window.time_from, "Start time"), (self.window.time_to, "End time")]:
            interface = QAccessible.queryAccessibleInterface(control)
            self.assertEqual(interface.text(QAccessible.Name), name)


if __name__ == "__main__":
    unittest.main()
