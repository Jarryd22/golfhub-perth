"""Bounded injected cache failures using a real Qt worker thread and inert executor.

This probes completion delivery, retry and queued-search handoff only. It does not
reproduce or diagnose historical Windows close timing. Providers never run.
"""
import argparse
from concurrent.futures import Future
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, out = args.root.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / 'tests')]

with tempfile.TemporaryDirectory(prefix='golfhub-cache-signal-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime,
                      TEMP=runtime, TMP=runtime, XDG_CACHE_HOME=runtime)
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtWidgets import QApplication, QLabel
    from shiboken6 import isValid
    from app import qt_golfhub_app as ui
    from app import shared_cache as cache
    from tests.qt_test_support import cleanup_qt_widgets

    app = QApplication.instance() or QApplication([])
    cases = []

    def pump_until(predicate, seconds=3):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return True
            time.sleep(0.002)
        app.processEvents()
        return bool(predicate())

    with ExitStack() as guards:
        for target in ('socket.create_connection', 'socket.socket.connect',
                       'socket.socket.connect_ex', 'socket.getaddrinfo', 'webbrowser.open',
                       'app.qt_golfhub_app.fetch_shared_snapshot', 'app.qt_golfhub_app.fetch_site_result',
                       'app.course_results.get_weather_for_date', 'app.qt_golfhub_app.save_local_snapshot',
                       'app.qt_golfhub_app.BookingAssistDialog'):
            guards.enter_context(patch(target, side_effect=AssertionError('Offline Qt completion probe')))
        guards.enter_context(patch.object(ui, 'load_local_snapshot', return_value=None))
        guards.enter_context(patch.object(ui, 'perth_today', return_value=QDate(2033, 1, 2)))

        for scenario in ('setup_failure_and_retry', 'partial_iteration', 'queued_newest_after_failure'):
            entered, release, observed = threading.Event(), threading.Event(), threading.Event()
            exceptions, emissions, submitted, executor_calls, thread_ends = [], [], [], [], []
            windows = []
            case = {'scenario': scenario}
            with ExitStack() as fixture:
                def exception_hook(kind, value, _traceback):
                    exceptions.append({'type': kind.__name__, 'message': str(value)})
                    observed.set()
                fixture.enter_context(patch('sys.excepthook', side_effect=exception_hook))
                with patch.object(ui.GolfHub, 'show_initial_cache'):
                    window = ui.GolfHub()
                windows.append(window)
                window._stop_deferred_timers()
                window.resize(980, 640)
                window.show()
                site = next(s for s in window.sites if s.name == 'Araluen')

                def context(offset=0, players=None):
                    dates = [QDate(2033, 1, 2).addDays(offset + i).toString('yyyy-MM-dd') for i in (0, 1)]
                    return {'sites': [site], 'date': dates[0], 'dates': dates, 'holes': '18',
                            'players': players, 'from': None, 'to': None}

                def payload(date):
                    rows = [{'time': '9:00 am', 'minutes': 540, 'spots': 2},
                            {'time': '10:00 am', 'minutes': 600, 'spots': 4}]
                    return cache.make_snapshot(date, '18', [{'site_name': site.name,
                        'url': f'https://{site.domain}', 'hole_label': '18 holes',
                        'error': None, 'weather': None, 'decorated_rows': rows}])

                class Pool:
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        return False
                    def submit(self, _fn, date, holes):
                        submitted.append({'date': date, 'holes': holes})
                        future = Future()
                        future.task_date = date
                        future.set_result(payload(date))
                        return future

                def pool_factory(*a, **kw):
                    executor_calls.append({'max_workers': kw.get('max_workers')})
                    if len(executor_calls) == 1:
                        entered.set()
                        if not release.wait(5):
                            raise AssertionError('Fixture release gate expired')
                        if scenario != 'partial_iteration':
                            raise RuntimeError('Synthetic cache executor setup failure')
                    return Pool()

                def completion_iterator(jobs):
                    for index, future in enumerate(jobs):
                        yield future
                        if scenario == 'partial_iteration' and index == 0:
                            raise RuntimeError('Synthetic iteration failure after one collected result')

                fixture.enter_context(patch.object(ui, 'ThreadPoolExecutor', side_effect=pool_factory))
                fixture.enter_context(patch.object(ui, 'as_completed', side_effect=completion_iterator))
                original_start = window._start_cache_search
                native_start = ui.QThread.start

                def start(ctx):
                    # Attach observers before allowing this actual QThread to run.
                    with patch.object(ui.QThread, 'start'):
                        original_start(ctx)
                    worker, thread = window.cache_worker, window.cache_thread
                    def emitted(value):
                        emissions.append({d: None if p is None else len(p['results']) for d, p in value.items()})
                        observed.set()
                    worker.finished.connect(emitted, Qt.DirectConnection)
                    thread.finished.connect(lambda: thread_ends.append(True), Qt.DirectConnection)
                    native_start(thread)
                fixture.enter_context(patch.object(window, '_start_cache_search', side_effect=start))

                def state():
                    return {'header': window.header_status.text(), 'status': window.status.text(),
                        'labels': [label.text() for label in window.results_body.findChildren(QLabel)],
                        'cache_reference_retained': window.cache_thread is not None,
                        'progress_visible': window.progress.isVisible(),
                        'search_button_text': window.search_button.text(),
                        'context_dates': list(window.context['dates']),
                        'context_players': window.context['players'],
                        'pending_dates': None if window._pending_cache_context is None else list(window._pending_cache_context['dates']),
                        'rendered_spots': [card.row['spots'] for card in window.results_body.findChildren(ui.TeeTimeCard)]}

                try:
                    original, discarded, newest = context(), context(2, 1), context(4, 4)
                    window._start_cache_search(original)
                    assert pump_until(entered.is_set), 'Executor fixture did not start'
                    if scenario == 'queued_newest_after_failure':
                        for ctx in (discarded, newest):
                            with patch.object(window, 'params', return_value=ctx):
                                window.search_cache()
                        case['queued_before_release'] = state()
                    release.set()
                    assert pump_until(observed.is_set), 'Neither completion nor escaped exception observed'
                    # The missing-completion baseline gets a bounded observation window.
                    completed = pump_until(lambda: window.cache_thread is None, 0.5 if exceptions else 3)
                    case['completed_without_intervention'] = completed
                    case['after_first_boundary'] = state()
                    window.grab().save(str(out / f'{scenario}.png'))
                    if scenario == 'setup_failure_and_retry' and completed:
                        window._start_cache_search(newest)
                        assert pump_until(lambda: window.cache_thread is None), 'Retry did not complete'
                        case['retry'] = state()
                    case['emissions'] = list(emissions)
                    case['finished_signal_count'] = len(emissions)
                    case['native_thread_finished_count'] = len(thread_ends)
                    case['executor_invocations'] = len(executor_calls)
                    case['submitted'] = list(submitted)
                    case['callback_errors'] = list(exceptions)
                finally:
                    release.set()
                    # Failed baseline slots leave an idle event-loop thread. Stop it
                    # explicitly only after the exception was observed; clear pending
                    # work so fixture cleanup cannot start another search.
                    window._pending_cache_context = None
                    thread = window.cache_thread
                    case['explicit_fixture_cleanup_required'] = thread is not None
                    if thread is not None and isValid(thread):
                        thread.quit()
                        assert thread.wait(2000), 'Fixture cleanup could not join idle worker thread'
                        assert pump_until(lambda: window.cache_thread is None), 'Fixture references not cleared'
                    assert window.scan_thread is None
                    cleanup_qt_widgets()
                cases.append(case)

    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'app_sha256': hashlib.sha256((root / 'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
        'cases': cases,
        'method': 'Real Linux QThread + existing window worker signal connections; inert executor and completed futures; no provider, socket, browser, cache save, or live worker execution.',
        'limits': 'Injected boundary failures, not production incidents. Bounded signal/recovery test; no Windows/Android device, native-close diagnosis, live booking or notification verification.'}
    (out / 'probe.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
