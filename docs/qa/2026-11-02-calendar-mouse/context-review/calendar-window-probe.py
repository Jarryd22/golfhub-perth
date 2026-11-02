"""Actual GolfHub popup mouse/keyboard comparison using synthetic Perth dates."""
from contextlib import ExitStack
import argparse
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
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
ROOT, OUT = args.root.resolve(), args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-calendar-window-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QTableView
    from app import qt_golfhub_app as ui
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    errors, cases = [], []
    def settle():
        for _ in range(8):
            app.processEvents()
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.getaddrinfo', 'webbrowser.open', 'app.qt_golfhub_app.CacheWorker',
                       'app.qt_golfhub_app.ScanWorker'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline source probe only')))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *args: errors.append(str(args[1]))))
        for month, blocked_day in ((3, 25), (11, 24)):
            start = QDate(2032, month, 1)
            with patch.object(ui, 'perth_today', return_value=start):
                for width, height in ((980, 640), (1280, 800)):
                    with patch.object(ui.GolfHub, 'show_initial_cache'):
                        window = ui.GolfHub()
                    window._stop_deferred_timers()
                    window.resize(width, height)
                    window.show()
                    window.date.setDate(start)
                    settle()
                    QTest.mouseClick(window.date, Qt.LeftButton)
                    settle()
                    popup = window.date.picker_popup()
                    view = popup.calendar.findChild(QTableView, 'qt_calendar_calendarview')
                    model = view.model()
                    clicks = []
                    for day in (22, blocked_day):
                        idx = next(model.index(r,c) for r in range(1, model.rowCount())
                                   for c in range(model.columnCount()) if str(model.index(r,c).data()) == str(day)
                                   and bool(model.index(r,c).flags() & Qt.ItemIsEnabled))
                        point = view.visualRect(idx).center()
                        before = [d.toString('yyyy-MM-dd') for d in popup.selected_dates()]
                        inferred = popup.calendar._date_at_view_position(point).toString('yyyy-MM-dd')
                        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=point)
                        settle()
                        clicks.append({'day': day, 'model_label': idx.data(), 'enabled': True,
                                       'row': idx.row(), 'column': idx.column(),
                                       'coordinates': [point.x(), point.y()], 'inferred': inferred,
                                       'before': before,
                                       'after': [d.toString('yyyy-MM-dd') for d in popup.selected_dates()],
                                       'selected': QDate(2032, month, day) in popup.selected_dates()})
                    name = f'window-{start.toString("yyyy-MM")}-{width}x{height}'
                    popup.grab().save(str(OUT / f'{name}-mouse.png'))
                    window.grab().save(str(OUT / f'{name}-app.png'))
                    target = QDate(2032, month, blocked_day)
                    popup.calendar.setSelectedDate(target)
                    view.setFocus()
                    QTest.keyClick(view, Qt.Key_Space)
                    settle()
                    keyboard_selected = target in popup.selected_dates()
                    QTest.mouseClick(popup.done_button, Qt.LeftButton)
                    settle()
                    cases.append({'window_size': [window.width(), window.height()],
                                  'month': start.toString('yyyy-MM'), 'clicks': clicks,
                                  'keyboard_selected_same_day': keyboard_selected,
                                  'applied_dates': window.selected_dates()})
                    cleanup_qt_widgets()
        result = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'source_sha256': hashlib.sha256((ROOT/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'scope': 'Linux Qt offscreen actual app-popup actions, fake Perth clock, isolated paths, blocked network/browser/workers',
                  'cases': cases, 'callback_errors': errors}
        (OUT/'calendar-window-probe.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
