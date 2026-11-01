"""Core-to-widget handling of message-less provider exceptions, fully offline."""
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
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path('/workspace/golfhub-20261031'))
parser.add_argument('--output', type=Path, default=Path(__file__).parent)
args = parser.parse_args()
root, output = args.root.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-empty-error-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel
    from app import golfhub_core as core
    from app.qt_golfhub_app import GolfHub, ResultCard, ScanWorker
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    callbacks = []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'webbrowser.open'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline probe')))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today', return_value=QDate(2033, 1, 2)))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *a: callbacks.append(str(a[1]))))
        stack.enter_context(patch.object(core, 'get_weather_for_date', return_value=None))
        with patch.object(GolfHub, 'show_initial_cache'):
            window = GolfHub()
        window._stop_deferred_timers()
        window.resize(1280, 800)
        window.show()
        sites = {site.name: site for site in window.sites}
        cases = []
        def capture(kind, site, result, exception):
            window.context = {'date': '2033-01-02', 'dates': ['2033-01-02'], 'sites': [site],
                              'holes': '18', 'players': None, 'from': None, 'to': None}
            window.render_results([result], 'Synthetic provider response')
            for _ in range(3):
                app.processEvents()
            cases.append({'case': kind, 'site': site.name, 'raised': exception,
                          'result_error': result.get('error'),
                          'error_truthy': bool(result.get('error')),
                          'rows': result.get('decorated_rows'),
                          'headline': window.results_body.findChild(QLabel, 'SummaryValue').text(),
                          'status': window.status.text(),
                          'rendered_course_cards': len(window.results_body.findChildren(ResultCard)),
                          'labels': [label.text() for label in window.results_body.findChildren(QLabel)]})
            if kind.endswith('no-message-timeout'):
                window.grab().save(str(output / f'{kind}.png'))
        for site_name, fetcher in [('Araluen', 'fetch_site_text'), ('Wembley', 'fetch_text')]:
            site = sites[site_name]
            for name, failure in [('no-message-timeout', TimeoutError()), ('named-timeout', TimeoutError('Synthetic timeout'))]:
                with patch.object(core, fetcher, side_effect=failure):
                    result = core.fetch_site_result(site, '2033-01-02', '18', None, None, None)
                capture(f'{site_name.lower()}-{name}', site, result, repr(failure))
        with patch.object(core, 'fetch_site_text', return_value='<html><body>No tee times</body></html>'), \
                patch.object(core, 'save_debug_html'):
            result = core.fetch_site_result(sites['Araluen'], '2033-01-02', '18', None, None, None)
        capture('araluen-successful-empty', sites['Araluen'], result, None)
        worker = ScanWorker([sites['Araluen']], '2033-01-02', '18', None, None, None)
        finished = []
        worker.finished.connect(lambda results, cancelled: finished.append((results, cancelled)))
        with patch.object(worker, '_fetch', side_effect=TimeoutError()):
            worker.run()
        capture('worker-no-message-timeout', sites['Araluen'], finished[0][0][0], 'TimeoutError()')
        worker.deleteLater()
        report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  'source_hashes': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                    for name in ('app/golfhub_core.py', 'app/qt_golfhub_app.py')},
                  'kind': 'Linux offscreen; actual core parser error paths and synchronous ScanWorker.run with mocked provider fetch; sockets/browser blocked; no Qt worker launch',
                  'cases': cases, 'callback_errors': callbacks}
        (output / 'empty-error-probe.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        cleanup_qt_widgets()
