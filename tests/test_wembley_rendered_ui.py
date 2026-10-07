"""Rendered Wembley rows remain usable when only some products complete."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from app.qt_golfhub_app import ResultCard, TeeTimeCard


class WembleyRenderedUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def result(self, coverage):
        rows = [{
            "time": "05:48 am", "spots": 3, "minutes": 348, "course": "Old Course",
            "source_url": "https://www.wembleygolf.com.au/guests/bookings/ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2026-10-08&feeGroupId=102184",
        }]
        result = {
            "site_name": "Wembley", "hole_label": "18 holes", "decorated_rows": rows,
            "url": rows[0]["source_url"], "weather": None, "error": None,
            "wembley_collection": coverage,
        }
        if coverage == "partial":
            result["booking_note"] = "Only some Wembley course times could be read. Open the official calendar to check all current times."
        return result

    def test_partial_collection_displays_notice_and_visible_exact_row(self):
        result = self.result("partial")
        card = ResultCard(result, result["decorated_rows"])
        try:
            card.show()
            self.app.processEvents()
            notices = [label for label in card.findChildren(QLabel) if label.objectName() == "AvailabilityNotice"]
            self.assertEqual([label.text() for label in notices], [result["booking_note"]])
            self.assertTrue(notices[0].isVisible())
            times = card.findChildren(TeeTimeCard)
            self.assertEqual(len(times), 1)
            self.assertTrue(times[0].isVisible())
            labels = [label.text() for label in times[0].findChildren(QLabel)]
            self.assertIn("05:48 am", labels)
            self.assertIn("3 spots", labels)
            self.assertEqual(times[0].url, result["decorated_rows"][0]["source_url"])
        finally:
            card.close()

    def test_partial_notice_remains_when_filters_hide_all_rows(self):
        result = self.result("partial")
        card = ResultCard(result, [])
        try:
            card.show()
            self.app.processEvents()
            notices = [label for label in card.findChildren(QLabel) if label.objectName() == "AvailabilityNotice"]
            self.assertEqual([label.text() for label in notices], [result["booking_note"]])
            self.assertTrue(notices[0].isVisible())
            self.assertEqual(card.findChildren(TeeTimeCard), [])
            self.assertIn("No matching tee times in this search window.", [label.text() for label in card.findChildren(QLabel)])
        finally:
            card.close()

    def test_complete_collection_displays_exact_times_without_partial_notice(self):
        result = self.result("complete")
        card = ResultCard(result, result["decorated_rows"])
        try:
            card.show()
            self.app.processEvents()
            self.assertEqual(len(card.findChildren(TeeTimeCard)), 1)
            self.assertTrue(card.findChildren(TeeTimeCard)[0].isVisible())
            labels = card.findChildren(QLabel)
            self.assertIn("05:48 am", [label.text() for label in labels])
            self.assertIn("1 matching tee time - 18 holes", [label.text() for label in labels])
            self.assertFalse(any(label.objectName() == "AvailabilityNotice" for label in labels))
            self.assertFalse(any("quick check" in label.text() for label in labels))
        finally:
            card.close()


if __name__ == "__main__":
    unittest.main()
