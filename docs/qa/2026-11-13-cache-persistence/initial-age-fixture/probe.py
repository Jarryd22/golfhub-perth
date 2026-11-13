"""Synthetic shared-download/save-error/UI probe; no actual network or workers."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import urllib.error

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, out = args.root.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / 'tests')]

with tempfile.TemporaryDirectory(prefix='golfhub-save-error-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime,
                      TEMP=runtime, TMP=runtime, XDG_CACHE_HOME=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel
    from app import qt_golfhub_app as ui
    from app import shared_cache as cache
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    records = []
    callback_errors = []
    scenarios = [
        ('write_error_old_single', 'write_text', True, False, 'valid'),
        ('mkdir_error_empty_single', 'mkdir', False, False, 'valid'),
        ('replace_error_old_multi', 'replace', True, True, 'valid'),
        ('write_error_empty_multi', 'write_text', False, True, 'valid'),
        ('valid_save_single', None, False, False, 'valid'),
        ('valid_save_multi', None, False, True, 'valid'),
        ('invalid_payload_old_single', None, True, False, 'invalid'),
        ('transport_error_old_single', None, True, False, 'offline'),
        ('transport_error_empty_multi', None, False, True, 'offline'),
    ]
    with ExitStack() as guards:
        for target in ('socket.create_connection', 'socket.socket.connect',
                       'socket.socket.connect_ex', 'socket.getaddrinfo', 'webbrowser.open',
                       'app.qt_golfhub_app.CacheWorker', 'app.qt_golfhub_app.ScanWorker',
                       'app.qt_golfhub_app.fetch_site_result', 'app.course_results.get_weather_for_date',
                       'app.qt_golfhub_app.BookingAssistDialog'):
            guards.enter_context(patch(target, side_effect=AssertionError('Offline persistence probe')))
        guards.enter_context(patch.object(ui, 'perth_today', return_value=QDate(2033, 1, 2)))
        guards.enter_context(patch('sys.excepthook', side_effect=lambda kind, value, _tb:
            callback_errors.append({'type': kind.__name__, 'message': str(value)})))
        guards.enter_context(patch.object(cache, '_cache_base_url', return_value='https://example.invalid/cache'))
        for name, failure, saved, multi, transport in scenarios:
            with ExitStack() as fixture:
                cache_dir = Path(runtime) / name / 'cache'
                fixture.enter_context(patch.object(cache, 'LOCAL_CACHE_DIR', cache_dir))
                with patch.object(ui.GolfHub, 'show_initial_cache'):
                    window = ui.GolfHub()
                window._stop_deferred_timers()
                window.resize(980, 640)
                window.show()
                site = next(s for s in window.sites if s.name == 'Araluen')
                dates = ['2033-01-02', '2033-01-03'] if multi else ['2033-01-02']
                submitted = {'sites': [site], 'dates': dates, 'date': dates[0],
                             'holes': '18', 'players': 4, 'from': None, 'to': None}
                window.set_all(False)
                next(r for r in window.course_rows if r.site.name == site.name).check.setChecked(True)
                window.date.set_dates([QDate.fromString(d, 'yyyy-MM-dd') for d in dates])
                window.players.setCurrentText('4')
                window.context = window._snapshot_search_context(submitted)
                window._active_cache_context = window._snapshot_search_context(submitted)
                window.render_empty('Checking the shared cache...')
                window.header_status.setText('CHECKING SHARED CACHE')
                window.status.setText('Checking shared cache...')

                def payload(date, old=False):
                    url = f'https://{site.domain}/guests/bookings/ViewPublicTimesheet.msp?selectedDate={date}'
                    rows = [{'time': '8:00 am' if old else '10:00 am',
                             'minutes': 480 if old else 600, 'spots': 4, 'source_url': url},
                            {'time': '9:00 am', 'minutes': 540, 'spots': 2, 'source_url': url}]
                    value = cache.make_snapshot(date, '18', [{'site_name': site.name, 'url': url,
                        'hole_label': '18 holes', 'decorated_rows': rows, 'weather': None, 'error': None}])
                    if old:
                        value['generated_at'] = '2032-12-31T00:00:00Z'
                    return value

                # A real old cache exists only for the first selected date.
                if saved:
                    cache.save_local_snapshot(payload(dates[0], old=True))
                paths = {date: cache.local_snapshot_path(date, '18') for date in dates}
                before_bytes = {date: path.read_bytes() if path.exists() else None for date, path in paths.items()}
                downloads, injected = [], []
                downloaded = {date: payload(date) for date in dates}
                if transport == 'invalid':
                    downloaded[dates[0]]['results'] = [None]
                def response(request, timeout):
                    date = request.full_url.rsplit('/', 2)[-2]
                    downloads.append({'url': request.full_url, 'timeout': timeout})
                    if transport == 'offline':
                        raise urllib.error.URLError('Synthetic offline transport failure')
                    return io.BytesIO(json.dumps(downloaded[date]).encode('utf-8'))
                fixture.enter_context(patch.object(cache.urllib.request, 'urlopen', side_effect=response))
                if failure:
                    original = getattr(Path, failure)
                    targets = set(path.parent if failure == 'mkdir' else path.with_suffix('.tmp')
                                  for path in paths.values())
                    def failed_io(path, *a, **kw):
                        if path in targets:
                            injected.append({'operation': failure, 'path': str(path.relative_to(cache_dir))})
                            raise OSError('Synthetic local cache ' + failure + ' failure')
                        return original(path, *a, **kw)
                    fixture.enter_context(patch.object(Path, failure, new=failed_io))
                live = fixture.enter_context(patch.object(window, 'search_live'))
                snapshots = {date: cache.fetch_shared_snapshot(date, '18') for date in dates}
                window.cache_finished(snapshots)
                for _ in range(8):
                    app.processEvents()
                after_bytes = {date: path.read_bytes() if path.exists() else None for date, path in paths.items()}
                def summarise_context(value):
                    return {**{key: val for key, val in value.items() if key != 'sites'},
                            'sites': [s.name for s in value['sites']]}
                record = {'scenario': name, 'injected_io_errors': injected, 'download_calls': downloads,
                    'downloaded_valid_payloads': transport == 'valid',
                    'fetch_returned_dates': [date for date, value in snapshots.items() if value is not None],
                    'returned_exact_downloads': {date: value == downloaded[date] for date, value in snapshots.items() if value is not None},
                    'submitted_context': summarise_context(submitted),
                    'render_context': summarise_context(window.context),
                    'live_fallback_contexts': [summarise_context(call.args[0]) for call in live.call_args_list],
                    'header': window.header_status.text(), 'status': window.status.text(),
                    'labels': [label.text() for label in window.results_body.findChildren(QLabel)],
                    'rendered_rows': [dict(card.row) for card in window.results_body.findChildren(ui.TeeTimeCard)],
                    'day_count': len(window.day_sections),
                    'local_cache': {date: {'existed_before': before_bytes[date] is not None,
                        'exists_after': after_bytes[date] is not None,
                        'bytes_unchanged': before_bytes[date] == after_bytes[date],
                        'stored_matches_download': after_bytes[date] is not None and json.loads(after_bytes[date]) == downloaded[date],
                        'temporary_file_exists': paths[date].with_suffix('.tmp').exists()} for date in dates}}
                records.append(record)
                if name in ('write_error_old_single', 'mkdir_error_empty_single',
                            'replace_error_old_multi', 'write_error_empty_multi', 'valid_save_single'):
                    window.grab().save(str(out / f'{name}.png'))
                cleanup_qt_widgets()
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'source_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ('app/shared_cache.py', 'app/qt_golfhub_app.py')},
        'cases': records, 'callback_errors': callback_errors,
        'scope': 'Actual shared-cache fetch/validation/save functions, mocked BytesIO downloads and URLError, real isolated cache files, targeted Path I/O OSError injection, actual UI completion/rendering; no workers, sockets, provider calls, browser navigation, holds, notifications or filesystem permission changes.',
        'limits': 'Injected storage/transport failures are not production incidents. Single-date live fallback is intercepted; its in-progress UI is therefore not executed. No native Windows/Android, device/screen-reader, real filesystem exhaustion or notification test.'}
    (out / 'probe.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
