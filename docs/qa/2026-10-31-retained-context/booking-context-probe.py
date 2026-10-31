"""Synthetic retained-result handoff probe; no provider, browser or worker execution."""
import argparse
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

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = args.root.resolve()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-booking-context-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from app.qt_golfhub_app import GolfHub, TeeTimeCard
    from app.booking_assist import build_booking_assist_plan
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    callbacks = []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'webbrowser.open'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline probe')))
        stack.enter_context(patch('app.qt_golfhub_app.BookingAssistDialog', side_effect=AssertionError('No holds')))
        stack.enter_context(patch('app.qt_golfhub_app.QMessageBox.critical'))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today', return_value=QDate(2033, 1, 2)))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *args: callbacks.append(str(args[1]))))
        with patch.object(GolfHub, 'show_initial_cache'):
            window = GolfHub()
        window._stop_deferred_timers()
        window.resize(1280, 800)
        window.show()
        window.set_all(False)
        next(r for r in window.course_rows if r.site.name == 'Araluen').check.setChecked(True)
        window.date.setDate(QDate(2033, 1, 2))
        window.players.setCurrentText('1')
        window.context = window.params()
        url = ('https://araluenestategolfcourse.miclub.com.au/guests/bookings/'
               'ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2033-01-02&feeGroupId=102807')
        row = {'time': '9:00 am', 'minutes': 540, 'spots': 4, 'source_url': url}
        result = {'site_name': 'Araluen', 'url': url, 'hole_label': '18 holes',
                  'decorated_rows': [row], 'weather': None, 'error': None}
        window.render_results([result], 'Synthetic saved snapshot for 2 January')
        original_context = dict(window.context)
        evidence = []
        def capture(stage):
            card = window.results_body.findChild(TeeTimeCard)
            button = next(b for b in card.findChildren(QPushButton) if b.text() == 'BOOK')
            with patch('app.qt_golfhub_app.build_booking_assist_plan', wraps=build_booking_assist_plan) as builder, \
                    patch.object(window, '_booking_choice', return_value='cancel'):
                button.click()
            app.processEvents()
            evidence.append({'stage': stage, 'button_accessible_name': button.accessibleName(),
                             'button_enabled': button.isEnabled(), 'row_url': card.url,
                             'displayed_summary': window.findChild(QLabel, 'SummaryValue').text(),
                             'status': window.status.text(), 'context_date': window.context['date'],
                             'context_players': window.context['players'],
                             'plan_players': builder.call_args.kwargs['players'],
                             'plan_url': builder.call_args.kwargs['source_url']})
        capture('initial saved result')
        window.date.setDate(QDate(2033, 1, 5))
        window.players.setCurrentText('4')
        capture('pending controls not submitted')
        fake_thread = MagicMock()
        fake_thread.isRunning.return_value = False
        fake_thread.wait.return_value = True
        with patch('app.qt_golfhub_app.QThread', return_value=fake_thread), \
                patch('app.qt_golfhub_app.ScanWorker') as worker:
            window.search_live()
            capture('new live search pending; old result retained')
            window.scan_failed('Synthetic offline failure')
            capture('new live search failed; old result retained')
            window.scan_finished([], True)
            capture('new live search cancelled; old result retained')
        window.grab().save(str(output / 'retained-booking-context.png'))
        window.scan_thread = None
        window.scan_worker = None
        report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  'app_sha256': hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'kind': 'Linux offscreen; synthetic results; fake non-running worker; actual BOOK click; pure plan intercepted/cancelled; sockets/browser/dialog blocked',
                  'initial_search': {'date': original_context['date'], 'players': original_context['players']},
                  'observations': evidence, 'callback_errors': callbacks}
        (output / 'booking-context-probe.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        cleanup_qt_widgets()
