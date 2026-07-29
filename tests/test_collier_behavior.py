import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app import golfhub_core
from app.golfhub_core import (
    COLLIER_EMPTY_BOOKING_NOTE,
    COLLIER_PUBLIC_CALENDAR_URL,
    CONFIG_FILE,
    DATA_DIR,
    fetch_site_result,
    load_sites,
)
from app.shared_cache import make_snapshot
from app.qt_golfhub_app import GolfHub, ResultCard


class CollierParkBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.site = next(
            site for site in load_sites(DATA_DIR / CONFIG_FILE)
            if site.name == 'Collier Park'
        )

    def test_config_uses_verified_collier_products(self):
        self.assertEqual(self.site.domain, 'bookings.collierparkgolf.com.au')
        self.assertEqual(
            self.site.holes['18'].resolve_fee_group_id('2026-07-23'),
            '1500257612',
        )
        self.assertEqual(
            self.site.holes['9'].resolve_fee_group_id('2026-07-23'),
            '1500323733',
        )

    def test_empty_date_stays_visible_and_opens_official_calendar(self):
        with (
            patch.object(golfhub_core, 'get_weather_for_date', return_value=None),
            patch.object(
                golfhub_core,
                'fetch_site_text',
                return_value='<html><body>No public times</body></html>',
            ),
        ):
            result = fetch_site_result(
                self.site, '2026-07-16', '18', None, None, None
            )

        self.assertIsNone(result['error'])
        self.assertEqual(result['decorated_rows'], [])
        self.assertIs(result['show_when_empty'], True)
        self.assertEqual(result['url'], COLLIER_PUBLIC_CALENDAR_URL)
        self.assertEqual(
            result['official_calendar_url'], COLLIER_PUBLIC_CALENDAR_URL
        )
        self.assertEqual(result['booking_note'], COLLIER_EMPTY_BOOKING_NOTE)
        self.assertIn('8 days in advance at 12:00 pm', result['booking_note'])

        cached = make_snapshot('2026-07-16', '18', [result])['results'][0]
        self.assertIs(cached['show_when_empty'], True)
        self.assertEqual(cached['url'], COLLIER_PUBLIC_CALENDAR_URL)
        self.assertEqual(cached['booking_note'], COLLIER_EMPTY_BOOKING_NOTE)

    def test_exact_rows_keep_exact_timesheet_url(self):
        html = '''
            <html><body>
            <div>07:00 am<br>Lake / Island<br>
            Available<br>Available<br>Available<br>Available</div>
            </body></html>
        '''
        with (
            patch.object(golfhub_core, 'get_weather_for_date', return_value=None),
            patch.object(golfhub_core, 'fetch_site_text', return_value=html),
        ):
            result = fetch_site_result(
                self.site, '2026-07-23', '18', None, None, None
            )

        self.assertIsNone(result['error'])
        self.assertEqual(len(result['decorated_rows']), 1)
        self.assertEqual(result['decorated_rows'][0]['time'], '07:00 am')
        self.assertEqual(result['decorated_rows'][0]['spots'], 4)
        self.assertIn('ViewPublicTimesheet.msp', result['url'])
        self.assertIn('feeGroupId=1500257612', result['url'])
        self.assertNotIn('show_when_empty', result)
        self.assertNotIn('booking_note', result)

    def test_old_cache_empty_result_renders_clear_calendar_action(self):
        with patch.object(GolfHub, 'show_initial_cache'):
            window = GolfHub()
        try:
            window.context = {
                'sites': [self.site],
                'date': '2026-07-16',
                'dates': ['2026-07-16'],
                'holes': '18',
                'players': None,
                'from': None,
                'to': None,
            }
            old_cache_result = {
                'site_name': 'Collier Park',
                'url': self.site.build_url('2026-07-16', '18'),
                'hole_label': '18 holes',
                'decorated_rows': [],
                'weather': None,
                'error': None,
            }
            window.render_results([old_cache_result], 'Shared cache')
            self.app.processEvents()

            cards = window.findChildren(ResultCard)
            self.assertEqual(len(cards), 1)
            labels = [label.text() for label in cards[0].findChildren(QLabel)]
            self.assertTrue(
                any('8 days in advance at 12:00 pm' in text for text in labels)
            )
            button = next(
                value
                for value in cards[0].findChildren(QPushButton)
                if value.text() == 'VIEW OFFICIAL CALENDAR'
            )
            with patch('app.qt_golfhub_app.webbrowser.open') as open_page:
                button.click()
            open_page.assert_called_once_with(COLLIER_PUBLIC_CALENDAR_URL)
        finally:
            window.cache_thread = None
            window.close()


if __name__ == '__main__':
    unittest.main()

