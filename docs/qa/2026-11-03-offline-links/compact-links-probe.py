"""Compact offscreen recovery-card reachability and keyboard handoff diagnostic."""
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
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, output = args.root.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-compact-links-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate, QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from app import shared_cache
    from app.qt_golfhub_app import DirectCourseCard, GolfHub
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    callbacks = []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.getaddrinfo', 'app.qt_golfhub_app.CacheWorker', 'app.qt_golfhub_app.ScanWorker'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline compact probe')))
        weather = stack.enter_context(patch('app.course_results.get_weather_for_date', side_effect=AssertionError('No weather')))
        browser = stack.enter_context(patch('app.qt_golfhub_app.webbrowser.open', return_value=True))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today', return_value=QDate(2033, 1, 2)))
        stack.enter_context(patch.object(shared_cache, 'LOCAL_CACHE_DIR', Path(runtime) / 'cache'))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *a: callbacks.append(str(a[1]))))
        with patch.object(GolfHub, 'show_initial_cache'):
            window = GolfHub()
        window._stop_deferred_timers()
        window.resize(980, 640)
        window.show()
        names = {'Araluen', 'Altone Park', 'Boddington Golf Club'}
        window.set_all(False)
        for row in window.course_rows:
            row.check.setChecked(row.site.name in names)
        window.date.set_dates([QDate(2033, 1, 2), QDate(2033, 1, 4), QDate(2033, 1, 7)])
        window.players.setCurrentText('4')
        window.time_preset.setCurrentText('Afternoon')
        window.context = window.params()
        window._active_cache_context = window._snapshot_search_context(window.context)
        with patch.object(window, 'search_live', side_effect=AssertionError('No multi-date live fallback')):
            window.cache_finished({})
        for _ in range(3):
            app.processEvents()
        cards = window.results_body.findChildren(DirectCourseCard)
        assert [c.result['site_name'] for c in cards] == ['Altone Park', 'Boddington Golf Club']
        window.grab().save(str(output / 'offline-links-980x640-top.png'))
        buttons = [card.findChild(QPushButton) for card in cards]
        window.search_button.setFocus()
        app.processEvents()
        focus_path = []
        reached = []
        for _ in range(30):
            focused = app.focusWidget()
            assert focused is not None
            QTest.keyClick(focused, Qt.Key_Tab)
            app.processEvents()
            focused = app.focusWidget()
            focus_path.append({'type': type(focused).__name__, 'name': focused.accessibleName(),
                               'object_name': focused.objectName()})
            if focused in buttons and focused not in reached:
                reached.append(focused)
                QTest.keyClick(focused, Qt.Key_Space)
            if len(reached) == len(buttons):
                break
        assert reached == buttons, 'Both official links must be reachable by Tab from Find Tee Times'
        assert [call.args[0] for call in browser.call_args_list] == [c.result['url'] for c in cards]
        visibility = []
        viewport = window.results_scroll.viewport()
        for card, button in zip(cards, buttons):
            window.results_scroll.ensureWidgetVisible(card)
            for _ in range(3):
                app.processEvents()
            position = button.mapTo(viewport, QPoint(0, 0))
            visible = (position.x() >= 0 and position.y() >= 0
                       and position.x() + button.width() <= viewport.width()
                       and position.y() + button.height() <= viewport.height())
            assert visible and button.isVisible()
            visibility.append({'course': card.result['site_name'], 'fully_inside_viewport': visible,
                               'button_accessible_name': button.accessibleName(),
                               'button_rect': [position.x(), position.y(), button.width(), button.height()]})
        window.grab().save(str(output / 'offline-links-980x640-scrolled.png'))
        weather.assert_not_called()
        assert not callbacks
        assert window.cache_thread is None and window.scan_thread is None
        report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  'app_sha256': hashlib.sha256((root / 'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'kind': 'Separate Linux offscreen diagnostic; actual Tab/Space from Find Tee Times and scroll reachability; real empty temporary local cache; sockets/weather/workers blocked, browser intercepted',
                  'logical_window': [window.width(), window.height()],
                  'status': window.status.text(), 'header': window.header_status.text(),
                  'focus_path': focus_path, 'links': visibility,
                  'intercepted_urls': [call.args[0] for call in browser.call_args_list],
                  'callback_errors': callbacks}
        (output / 'compact-links-probe.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        cleanup_qt_widgets()
