"""Configured direct-course recovery links across missing multi-date caches."""
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
parser.add_argument('--root', type=Path, default=Path('/workspace/golfhub-20261101'))
parser.add_argument('--output', type=Path, default=Path(__file__).parent)
args = parser.parse_args()
root, output = args.root.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-offline-links-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from app import shared_cache
    from app.qt_golfhub_app import DirectCourseCard, GolfHub
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    callbacks = []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.getaddrinfo', 'app.course_results.get_weather_for_date',
                       'app.qt_golfhub_app.CacheWorker', 'app.qt_golfhub_app.ScanWorker'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline probe')))
        browser = stack.enter_context(patch('app.qt_golfhub_app.webbrowser.open', return_value=True))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today', return_value=QDate(2033, 1, 2)))
        stack.enter_context(patch.object(shared_cache, 'LOCAL_CACHE_DIR', Path(runtime) / 'cache'))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *a: callbacks.append(str(a[1]))))
        with patch.object(GolfHub, 'show_initial_cache'):
            window = GolfHub()
        window._stop_deferred_timers()
        window.resize(1280, 800)
        window.show()
        direct = [site for site in window.sites if site.provider == 'direct' and '18' in site.holes][:2]
        live = next(site for site in window.sites if site.name == 'Araluen')
        dates = ['2033-01-02', '2033-01-04', '2033-01-07']
        cases = []
        def select(sites, selected_dates):
            window.set_all(False)
            names = {site.name for site in sites}
            for row in window.course_rows:
                row.check.setChecked(row.site.name in names)
            window.date.set_dates([QDate.fromString(date, 'yyyy-MM-dd') for date in selected_dates])
            window.context = window.params()
            window._active_cache_context = window._snapshot_search_context(window.context)
        empty = shared_cache.make_snapshot(dates[0], '18', [])
        for name, selected, snapshots in (
            ('direct-only-all-missing', direct[:1], {}),
            ('mixed-all-missing', [live, *direct], {}),
            ('integrated-only-all-missing', [live], {}),
            ('direct-only-one-loaded', direct[:1], {dates[0]: empty}),
            ('mixed-one-loaded', [live, *direct], {dates[0]: empty}),
        ):
            select(selected, dates)
            browser.reset_mock()
            with patch.object(window, 'search_live', side_effect=AssertionError('No multi-day live fallback')):
                window.cache_finished(snapshots)
            for _ in range(3):
                app.processEvents()
            cards = window.results_body.findChildren(DirectCourseCard)
            for card in cards:
                card.findChild(QPushButton).click()
            cases.append({'case': name, 'selected': [site.name for site in selected],
                          'expected_static_urls': [f'https://{site.domain}' for site in selected if site.provider == 'direct'],
                          'local_cache_files': [str(p.relative_to(Path(runtime))) for p in Path(runtime).rglob('*.json')],
                          'direct_cards': [{'name': c.result['site_name'], 'url': c.result['url']} for c in cards],
                          'intercepted_urls': [call.args[0] for call in browser.call_args_list],
                          'header': window.header_status.text(), 'status': window.status.text(),
                          'labels': [label.text() for label in window.results_body.findChildren(QLabel)]})
            if name in ('direct-only-all-missing', 'direct-only-one-loaded'):
                window.grab().save(str(output / f'{name}.png'))
                if cards:
                    window.results_scroll.ensureWidgetVisible(cards[0])
                    for _ in range(3):
                        app.processEvents()
                    window.grab().save(str(output / f'{name}-scrolled.png'))
        report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  'app_sha256': hashlib.sha256((root / 'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'kind': 'Linux offscreen; configured selected courses; actual cache_finished with synthetic shared map and real empty temporary local cache; socket/weather/worker access blocked and browser URLs intercepted',
                  'cases': cases, 'callback_errors': callbacks}
        (output / 'offline-links-probe.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        cleanup_qt_widgets()
