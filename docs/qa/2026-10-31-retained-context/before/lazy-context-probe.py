"""Read-only synthetic lazy-date context repro with worker/browser/socket blocking."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

root = Path('/workspace/golfhub-20261030')
output = Path(__file__).parent
sys.path[:0] = [str(root), str(root / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-lazy-context-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel
    from app.qt_golfhub_app import GolfHub, TeeTimeCard
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    callbacks = []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'webbrowser.open',
                       'app.qt_golfhub_app.BookingAssistDialog'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline probe')))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today', return_value=QDate(2033, 1, 2)))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *a: callbacks.append(str(a[1]))))
        with patch.object(GolfHub, 'show_initial_cache'):
            window = GolfHub()
        window._stop_deferred_timers()
        window.resize(1280, 800)
        window.show()
        window.set_all(False)
        next(r for r in window.course_rows if r.site.name == 'Araluen').check.setChecked(True)
        dates = [QDate(2033, 1, 2), QDate(2033, 1, 3)]
        window.date.set_dates(dates)
        window.players.setCurrentText('1')
        window.time_preset.setCurrentText('Any time')
        window.context = window.params()
        def result(date):
            url = ('https://araluenestategolfcourse.miclub.com.au/guests/bookings/'
                   f'ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate={date}&feeGroupId=102807')
            return {'site_name': 'Araluen', 'url': url, 'hole_label': '18 holes', 'error': None,
                    'decorated_rows': [{'time': '9:00 am', 'minutes': 540, 'spots': 2, 'source_url': url}]}
        days = [{'date': d.toString('yyyy-MM-dd'), 'results': [result(d.toString('yyyy-MM-dd'))],
                 'source': 'Synthetic saved snapshot'} for d in dates]
        window.render_multi_results(days, 'Synthetic saved two-date search')
        window.day_sections[0].set_expanded(False)
        section = window.day_sections[1]
        before = {'summary': window.findChild(QLabel, 'SummaryValue').text(),
                  'heading': section.toggle.text(), 'built': section._built,
                  'context': {key: window.context[key] for key in ('date', 'dates', 'players', 'from', 'to')}}
        window.date.setDate(QDate(2033, 1, 5))
        window.players.setCurrentText('4')
        window.time_preset.setCurrentText('Afternoon')
        fake_thread = MagicMock()
        fake_thread.isRunning.return_value = False
        fake_thread.wait.return_value = True
        with patch('app.qt_golfhub_app.QThread', return_value=fake_thread), \
                patch('app.qt_golfhub_app.ScanWorker'):
            window.search_live()
        section.set_expanded(True)
        app.processEvents()
        after = {'summary': window.findChild(QLabel, 'SummaryValue').text(),
                 'heading': section.toggle.text(), 'built': section._built,
                 'labels': [label.text() for label in section.findChildren(QLabel)],
                 'tee_time_cards': len(section.findChildren(TeeTimeCard)),
                 'context': {key: window.context[key] for key in ('date', 'dates', 'players', 'from', 'to')}}
        window.grab().save(str(output / 'retained-lazy-context.png'))
        window.scan_thread = None
        window.scan_worker = None
        report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  'app_sha256': hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'kind': 'Linux offscreen; synthetic cached multi-date rows; fake non-running worker; sockets/browser/booking dialogs blocked',
                  'before': before, 'after': after, 'callback_errors': callbacks}
        (output / 'lazy-context-probe.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        cleanup_qt_widgets()
