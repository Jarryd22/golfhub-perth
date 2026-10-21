import json, os, sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from app import qt_golfhub_app as ui
from tests.qt_test_support import cleanup_qt_widgets
app = QApplication([])
now = datetime(2032, 12, 31, 15, 59, 59, tzinfo=timezone.utc)
with patch.object(ui, 'datetime') as clock, patch.object(ui.GolfHub, 'show_initial_cache'), patch('socket.socket.connect', side_effect=AssertionError('Offline probe')), patch('webbrowser.open', side_effect=AssertionError('Offline probe')):
    clock.now.side_effect = lambda tz: now.astimezone(tz)
    window = ui.GolfHub()
    window._stop_deferred_timers()
    before = {'dates': window.selected_dates(), 'text': window.date.text(), 'minimum': window.date.minimumDate().toString('yyyy-MM-dd'), 'maximum': window.date.maximumDate().toString('yyyy-MM-dd')}
    window.date.setDate(QDate(2032, 12, 31))
    now += timedelta(seconds=1)
    window.date.open_picker()
    popup = window.date.picker_popup()
    after = {'today': ui.perth_today().toString('yyyy-MM-dd'), 'dates': window.selected_dates(), 'text': window.date.text(), 'minimum': window.date.minimumDate().toString('yyyy-MM-dd'), 'maximum': window.date.maximumDate().toString('yyyy-MM-dd'), 'popup_minimum': popup.calendar.minimumDate().toString('yyyy-MM-dd'), 'banner': popup.today_label.text()}
    with patch.object(window, '_start_cache_search') as launch:
        window.search_cache()
        after['new_search_dates'] = launch.call_args.args[0]['dates']
    print(json.dumps({'before':before,'after_midnight':after},indent=2))
    cleanup_qt_widgets()
