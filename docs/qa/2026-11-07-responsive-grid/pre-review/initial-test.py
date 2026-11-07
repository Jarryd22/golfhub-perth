"""Offscreen regressions for card width after responsive column changes."""
import os
import tempfile
import unittest
from unittest.mock import patch


_runtime = tempfile.TemporaryDirectory(prefix="golfhub-responsive-grid-")
_previous_env = {key: os.environ.get(key) for key in ("LOCALAPPDATA", "TEMP", "TMP")}
for _key in _previous_env:
    os.environ[_key] = _runtime.name
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from app.qt_golfhub_app import ResponsiveCardGrid
from tests.qt_test_support import cleanup_qt_widgets


def tearDownModule():
    cleanup_qt_widgets()
    _runtime.cleanup()
    for key, previous in _previous_env.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class ResponsiveGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.callback_errors = []
        for target in ("socket.create_connection", "socket.socket.connect", "webbrowser.open"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline grid test")))
        self.enterContext(patch("sys.excepthook", side_effect=lambda *args: self.callback_errors.append(str(args[1]))))

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [])

    def settle(self, grid):
        for _ in range(3):
            self.app.processEvents()
            grid.grid.activate()

    def make_grid(self, width, count=15, minimum=250):
        grid = ResponsiveCardGrid([QWidget() for _ in range(count)], min_cell_width=minimum)
        grid.setFixedSize(width, 1000)
        grid.show()
        self.settle(grid)
        return grid

    def resize_grid(self, grid, width):
        grid.setFixedWidth(width)
        self.settle(grid)

    @staticmethod
    def first_row(grid):
        return [grid.grid.itemAt(index).widget() for index in range(grid.grid.count())
                if grid.grid.getItemPosition(index)[0] == 0]

    def assert_row_fills_grid(self, grid, columns):
        row = self.first_row(grid)
        self.assertEqual(len(row), columns)
        self.assertEqual(row[0].geometry().left(), 0)
        self.assertLessEqual(abs(row[-1].geometry().right() - grid.contentsRect().right()), 1)
        self.assertLessEqual(max(card.width() for card in row) - min(card.width() for card in row), 1)

    def test_three_to_two_columns_reclaims_space_like_a_fresh_narrow_grid(self):
        grid = self.make_grid(1372)
        self.assert_row_fills_grid(grid, 3)
        self.resize_grid(grid, 683)
        fresh = self.make_grid(683)
        self.assert_row_fills_grid(grid, 2)
        self.assertEqual([card.width() for card in self.first_row(grid)],
                         [card.width() for card in self.first_row(fresh)])

    def test_three_to_one_column_fills_width_for_tee_time_and_direct_card_sizes(self):
        for minimum in (250, 280):
            with self.subTest(minimum=minimum):
                grid = self.make_grid(1200, minimum=minimum)
                self.resize_grid(grid, 500)
                self.assert_row_fills_grid(grid, 1)

    def test_widening_restores_three_even_columns(self):
        grid = self.make_grid(500)
        self.resize_grid(grid, 1200)
        self.assert_row_fills_grid(grid, 3)
        self.assertEqual(len(grid.widgets), 15)

    def test_show_all_and_first_twelve_keep_visibility_and_reclaimed_width(self):
        grid = self.make_grid(1200)
        self.resize_grid(grid, 683)
        for limit in (12, 15, 12):
            with self.subTest(limit=limit):
                grid.set_visible_limit(limit)
                self.settle(grid)
                self.assertEqual([not card.isHidden() for card in grid.widgets],
                                 [index < limit for index in range(15)])
                self.assertEqual(grid.grid.count(), limit)
                self.assert_row_fills_grid(grid, 2)

    def test_repeated_narrowing_and_widening_has_no_layout_history_effect(self):
        grid = self.make_grid(1200)
        for width, columns in ((683, 2), (500, 1), (1200, 3), (683, 2)):
            with self.subTest(width=width):
                self.resize_grid(grid, width)
                self.assert_row_fills_grid(grid, columns)

    def test_hidden_cards_can_be_restored_after_an_empty_narrow_grid(self):
        grid = self.make_grid(1200)
        grid.set_visible_limit(0)
        self.resize_grid(grid, 500)
        self.assertEqual(grid.grid.count(), 0)
        self.assertTrue(all(card.isHidden() for card in grid.widgets))
        grid.set_visible_limit(15)
        self.settle(grid)
        self.assertEqual(grid.grid.count(), 15)
        self.assert_row_fills_grid(grid, 1)


if __name__ == "__main__":
    unittest.main()
