"""Terminal live request -> Find -> cache miss before old owner cleanup.

Real worker QObject signals, inert thread mocks; never starts native threads.
"""
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
import traceback
from unittest.mock import MagicMock, patch

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, out = args.root.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / 'tests')]
report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
          'app_sha256': hashlib.sha256((root / 'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
          'cases': [], 'callback_errors': []}

with tempfile.TemporaryDirectory(prefix='golfhub-cache-live-handoff-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime,
                      TMP=runtime, XDG_CACHE_HOME=runtime)
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from app import qt_golfhub_app as ui
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])

    with ExitStack() as guards:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.getaddrinfo', 'webbrowser.open', 'app.qt_golfhub_app.fetch_site_result',
                       'app.qt_golfhub_app.fetch_shared_snapshot', 'app.course_results.get_weather_for_date',
                       'app.qt_golfhub_app.save_local_snapshot', 'app.qt_golfhub_app.BookingAssistDialog'):
            guards.enter_context(patch(target, side_effect=AssertionError('Offline controller probe')))
        guards.enter_context(patch.object(ui, 'load_local_snapshot', return_value=None))
        guards.enter_context(patch.object(ui, 'perth_today', return_value=QDate(2033, 1, 2)))
        guards.enter_context(patch.object(ui.ScanWorker, 'moveToThread'))
        guards.enter_context(patch.object(ui.CacheWorker, 'moveToThread'))
        guards.enter_context(patch.object(ui.ScanWorker, 'run', side_effect=AssertionError('No live execution')))
        guards.enter_context(patch.object(ui.CacheWorker, 'run', side_effect=AssertionError('No cache execution')))
        guards.enter_context(patch.object(ui.QMessageBox, 'critical'))
        guards.enter_context(patch('sys.excepthook', side_effect=lambda kind, value, _tb:
            report['callback_errors'].append({'type': kind.__name__, 'message': str(value)})))

        for terminal in ('failed', 'cancelled'):
            for retained in (False, True):
                record = {'terminal': terminal, 'retained_before_live': retained}
                report['cases'].append(record)
                threads, workers = [], []
                def thread_factory():
                    thread = MagicMock()
                    thread.isRunning.return_value = True
                    thread.wait.return_value = False
                    thread.quit.side_effect = lambda *_args: setattr(thread.isRunning, 'return_value', False)
                    threads.append(thread)
                    return thread
                with patch.object(ui, 'QThread', side_effect=thread_factory):
                    try:
                        with patch.object(ui.GolfHub, 'show_initial_cache'):
                            window = ui.GolfHub()
                        window._stop_deferred_timers()
                        window.resize(980, 640)
                        window.show()
                        window.set_all(False)
                        next(row for row in window.course_rows if row.site.name == 'Araluen').check.setChecked(True)
                        window.date.set_dates([QDate(2033, 1, 2)])
                        window.players.setCurrentText('4')
                        if retained:
                            window.context = window.params()
                            window.render_results([{'site_name': 'Araluen', 'url': 'https://example.invalid/old',
                                'hole_label': '18 holes', 'decorated_rows': [{'time': '9:00 am', 'minutes': 540, 'spots': 4}],
                                'weather': None, 'error': None}], 'Synthetic prior results')
                        QTest.mouseClick(window.live_button, Qt.LeftButton)
                        old_worker, old_thread = window.scan_worker, window.scan_thread
                        assert old_worker is not None and old_thread is not None
                        workers.append(old_worker)
                        if terminal == 'failed':
                            old_worker.failed.emit('Synthetic terminal live failure')
                        else:
                            QTest.mouseClick(window.stop_button, Qt.LeftButton)
                            assert old_worker.cancel_requested
                            old_worker.finished.emit([], True)
                        for _ in range(4): app.processEvents()
                        record['find_enabled_after_terminal'] = window.search_button.isEnabled()
                        record['old_live_owner_retained'] = window.scan_thread is old_thread
                        record['terminal_status'] = window.status.text()
                        assert record['find_enabled_after_terminal'] and record['old_live_owner_retained']

                        QTest.mouseClick(window.holes9, Qt.LeftButton)
                        window.date.set_dates([QDate(2033, 1, 5)])
                        window.players.setCurrentText('1')
                        window.time_preset.setCurrentText('Morning')
                        expected = window.params()
                        QTest.mouseClick(window.search_button, Qt.LeftButton)
                        cache_worker, cache_thread = window.cache_worker, window.cache_thread
                        assert cache_worker is not None and cache_thread is not None
                        workers.append(cache_worker)
                        assert window.context == expected
                        cache_worker.finished.emit({})
                        for _ in range(4): app.processEvents()
                        record['thread_instances_after_cache_miss'] = len(threads)
                        record['live_owner_after_cache_miss_is_old'] = window.scan_thread is old_thread
                        # Complete the new cache's controller cleanup first, then
                        # release the old live owner. No native thread is involved.
                        cache_thread.wait.return_value = True
                        window.cache_thread_done()
                        old_thread.wait.return_value = True
                        window.scan_thread_done()
                        for _ in range(8): app.processEvents()
                        record.update(
                            context={**{k: v for k, v in window.context.items() if k != 'sites'},
                                     'sites': [s.name for s in window.context['sites']]},
                            header=window.header_status.text(), status=window.status.text(),
                            labels=[label.text() for label in window.results_body.findChildren(QLabel)],
                            thread_instances_after_cleanup=len(threads),
                            scan_owner_present=window.scan_thread is not None,
                            cache_owner_present=window.cache_thread is not None,
                            progress_visible=window.progress.isVisible(),
                            find_enabled=window.search_button.isEnabled(), live_enabled=window.live_button.isEnabled(),
                            row_count=len(window.results_body.findChildren(ui.TeeTimeCard)))
                        if terminal == 'failed' and not retained:
                            window.grab().save(str(out / 'after-both-cleanups.png'))
                    except Exception:
                        record['fixture_failure'] = traceback.format_exc()
                    finally:
                        window.scan_thread = None
                        window.scan_worker = None
                        window.cache_thread = None
                        window.cache_worker = None
                        window._scan_cleanup_timer.stop()
                        window._cache_cleanup_timer.stop()
                        for worker in workers: worker.deleteLater()
                        cleanup_qt_widgets()
                print(json.dumps(record), flush=True)

report['scope'] = 'Actual Find/Refresh/Stop buttons and real worker QObject terminal signals; inert QThread mocks with explicitly deferred owner cleanup. No native thread, network/provider, persistence, booking/hold or notification execution. Synthetic ordering, not historical Windows shutdown diagnosis or production incidence.'
(out / 'probe.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'cases': len(report['cases']), 'fixture_failures': sum('fixture_failure' in c for c in report['cases']),
                  'callback_errors': report['callback_errors']}))
sys.exit(bool(report['callback_errors']) or any('fixture_failure' in c for c in report['cases']))
