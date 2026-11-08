"""Offline input and accessibility regressions for course selection."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.qt_golfhub_app import GolfHub
from tests.qt_test_support import cleanup_qt_widgets


class CourseControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.callback_errors = []
        self.addCleanup(patch.stopall)
        patch("socket.create_connection", side_effect=AssertionError("Offline test")).start()
        patch("socket.socket.connect", side_effect=AssertionError("Offline test")).start()
        patch("sys.excepthook", side_effect=lambda *args: self.callback_errors.append(str(args[1]))).start()
        with patch.object(GolfHub, "show_initial_cache"):
            self.window = GolfHub()
        self.window._stop_deferred_timers()
        self.window.show()
        self.window.toggle_courses()
        self.app.processEvents()
        self.row = next(r for r in self.window.course_rows if not r.isHidden())

    def tearDown(self):
        cleanup_qt_widgets()
        self.assertEqual(self.callback_errors, [], "Qt signal callbacks must not raise")

    def assert_count_matches_selection(self):
        count = len(self.window.selected_sites())
        self.assertEqual(self.window.selected_count.text(), f"{count} selected")
        self.assertEqual(self.window.course_button.text(), f"COURSES  {count} OF {len(self.window.sites)}")

    def test_checkbox_click_updates_count_once_and_keyboard_restores_it(self):
        initial = len(self.window.selected_sites())
        signals = QSignalSpy(self.row.toggled)
        QTest.mouseClick(self.row.check, Qt.LeftButton)
        self.assertFalse(self.row.check.isChecked())
        self.assertEqual(len(self.window.selected_sites()), initial - 1)
        self.assert_count_matches_selection()
        self.assertEqual(signals.count(), 1)
        self.row.check.setFocus()
        self.assertTrue(self.row.check.hasFocus())
        QTest.keyClick(self.row.check, Qt.Key_Space)
        self.assertTrue(self.row.check.isChecked())
        self.assert_count_matches_selection()
        self.assertEqual(signals.count(), 2)

    def test_course_row_click_updates_count_once(self):
        signals = QSignalSpy(self.row.toggled)
        QTest.mouseClick(self.row, Qt.LeftButton, pos=QPoint(self.row.width() - 2, self.row.height() // 2))
        self.assertFalse(self.row.check.isChecked())
        self.assert_count_matches_selection()
        self.assertEqual(signals.count(), 1)

    def test_clear_select_visible_and_round_changes_preserve_correct_selection(self):
        clear = next(b for b in self.window.course_panel.findChildren(QPushButton) if b.text() == "Clear")
        select = next(b for b in self.window.course_panel.findChildren(QPushButton) if b.text() == "Select visible")
        QTest.mouseClick(clear, Qt.LeftButton)
        self.assertEqual(self.window.selected_sites(), [])
        self.assert_count_matches_selection()
        query = "park"
        self.window.course_search.setText(query.upper())
        for round_button, holes in ((self.window.holes18, "18"), (self.window.holes9, "9"), (self.window.holes18, "18")):
            QTest.mouseClick(round_button, Qt.LeftButton)
            QTest.mouseClick(select, Qt.LeftButton)
            expected = {s.name for s in self.window.sites if holes in s.holes and query in s.name.lower()}
            self.assertEqual({s.name for s in self.window.selected_sites()}, expected)
            self.assert_count_matches_selection()
        self.window.course_search.clear()
        self.assert_count_matches_selection()

    def test_hidden_selected_courses_remain_counted_during_name_search(self):
        self.window.course_search.setText(self.row.site.name)
        self.assertTrue(any(r.isHidden() and r.check.isChecked() for r in self.window.course_rows))
        QTest.mouseClick(self.row.check, Qt.LeftButton)
        self.assert_count_matches_selection()

    def test_mouse_close_and_reopen_preserve_count_for_all_one_and_zero_courses(self):
        for selection in ("all", "one", "none"):
            with self.subTest(selection=selection):
                if not self.window.course_panel.isVisible():
                    QTest.mouseClick(self.window.course_button, Qt.LeftButton)
                self.window.set_all(selection == "all")
                if selection == "one":
                    self.row.check.setChecked(True)
                checked = [row.check.isChecked() for row in self.window.course_rows]
                signals = QSignalSpy(self.row.toggled)
                QTest.mouseClick(self.window.course_button, Qt.LeftButton)
                self.assertFalse(self.window.course_panel.isVisible())
                self.assertTrue(self.window.course_button.isVisible())
                self.assert_count_matches_selection()
                self.assertEqual([row.check.isChecked() for row in self.window.course_rows], checked)
                self.assertEqual(signals.count(), 0)
                QTest.mouseClick(self.window.course_button, Qt.LeftButton)
                self.assertTrue(self.window.course_panel.isVisible())
                self.assertTrue(self.window.selected_count.isVisible())
                self.assertEqual(self.window.course_button.text(), "HIDE COURSES")

    def test_keyboard_close_exposes_total_selection_including_name_filtered_courses(self):
        self.window.course_search.setText(self.row.site.name)
        self.assertTrue(any(row.isHidden() and row.check.isChecked() for row in self.window.course_rows))
        selected = [site.name for site in self.window.selected_sites()]
        self.window.course_button.setFocus()
        self.assertTrue(self.window.course_button.hasFocus())
        QTest.keyClick(self.window.course_button, Qt.Key_Space)
        self.assertFalse(self.window.course_panel.isVisible())
        self.assert_count_matches_selection()
        interface = QAccessible.queryAccessibleInterface(self.window.course_button)
        self.assertEqual(interface.text(QAccessible.Name), self.window.course_button.text())
        self.assertEqual([site.name for site in self.window.selected_sites()], selected)
        QTest.keyClick(self.window.course_button, Qt.Key_Space)
        self.assertTrue(self.window.course_panel.isVisible())
        self.assertEqual(self.window.course_button.text(), "HIDE COURSES")

    def test_collapsed_count_follows_round_eligibility_without_changing_checkboxes(self):
        checked = [row.check.isChecked() for row in self.window.course_rows]
        QTest.mouseClick(self.window.course_button, Qt.LeftButton)
        self.assert_count_matches_selection()
        for button, holes in ((self.window.holes9, "9"), (self.window.holes18, "18")):
            with self.subTest(holes=holes):
                QTest.mouseClick(button, Qt.LeftButton)
                self.assertFalse(self.window.course_panel.isVisible())
                self.assert_count_matches_selection()
                self.assertEqual({site.name for site in self.window.selected_sites()},
                                 {site.name for site in self.window.sites if holes in site.holes})
                self.assertEqual([row.check.isChecked() for row in self.window.course_rows], checked)

    def test_collapsed_count_agrees_with_submitted_sites_and_empty_selection_guard(self):
        for names in ({"Araluen", "Altone Park"}, set()):
            with self.subTest(names=sorted(names)):
                if not self.window.course_panel.isVisible():
                    QTest.mouseClick(self.window.course_button, Qt.LeftButton)
                self.window.set_all(False)
                for row in self.window.course_rows:
                    row.check.setChecked(row.site.name in names)
                self.window.course_search.setText("Araluen")
                QTest.mouseClick(self.window.course_button, Qt.LeftButton)
                self.assertFalse(self.window.course_panel.isVisible())
                self.assert_count_matches_selection()
                with (
                    patch.object(self.window, "_start_cache_search") as start,
                    patch("app.qt_golfhub_app.QMessageBox.information") as message,
                ):
                    QTest.mouseClick(self.window.search_button, Qt.LeftButton)
                if names:
                    message.assert_not_called()
                    start.assert_called_once()
                    self.assertEqual({site.name for site in start.call_args.args[0]["sites"]}, names)
                else:
                    start.assert_not_called()
                    message.assert_called_once()
                self.assertEqual({site.name for site in self.window.selected_sites()}, names)

    def test_filter_names_and_label_buddies_are_exposed(self):
        for control, field, name in (
            (self.window.players, self.window.players_field, "Players"),
            (self.window.time_preset, self.window.time_field, "Time"),
        ):
            with self.subTest(name=name):
                interface = QAccessible.queryAccessibleInterface(control)
                self.assertEqual(control.accessibleName(), name)
                label = field.findChild(QLabel)
                self.assertIs(label.buddy(), control)
                # On Unix Qt exposes the selected value as Name; assistive
                # technology discovers this control's label through relations.
                labels = interface.relations(QAccessible.RelationFlag.Label)
                self.assertTrue(any(related.object() is label for related, _ in labels))
        # Existing precise names must survive the generic field association.
        self.assertEqual(self.window.time_from.accessibleName(), "Start time")
        self.assertEqual(self.window.time_to.accessibleName(), "End time")

    def test_each_course_checkbox_exposes_course_name_and_checked_state(self):
        for row in self.window.course_rows:
            with self.subTest(course=row.site.name):
                interface = QAccessible.queryAccessibleInterface(row.check)
                self.assertEqual(interface.text(QAccessible.Name), row.site.name)
                self.assertTrue(interface.state().checked)
                label = next(label for label in row.findChildren(QLabel) if label.objectName() == "CourseName")
                self.assertIs(label.buddy(), row.check)
                # A buddy makes & a mnemonic marker; preserve literal course
                # names such as Serpentine & Districts in visible labels too.
                self.assertEqual(QAccessible.queryAccessibleInterface(label).text(QAccessible.Name), row.site.name)
        self.row.check.setChecked(False)
        self.assertFalse(QAccessible.queryAccessibleInterface(self.row.check).state().checked)

    def test_course_search_keeps_its_accessible_name_after_typing(self):
        for query in ("", "PARK"):
            self.window.course_search.setText(query)
            self.assertEqual(QAccessible.queryAccessibleInterface(self.window.course_search).text(QAccessible.Name), "Search courses")

    def test_course_search_hint_matches_name_only_matching(self):
        self.assertEqual(self.window.course_search.placeholderText(), "Search course names")
        self.window.course_search.setText("  PARK  ")
        expected = {s.name for s in self.window.sites if "18" in s.holes and "park" in s.name.lower()}
        self.assertEqual({r.site.name for r in self.window.course_rows if not r.isHidden()}, expected)


if __name__ == "__main__":
    unittest.main()
