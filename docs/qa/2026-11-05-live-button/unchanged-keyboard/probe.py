"""Bounded offline keyboard focus/reachability observations on exact PR24."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT=Path('/workspace/golfhub-20261104')
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
signal.alarm(30)
with tempfile.TemporaryDirectory(prefix='golfhub-keyboard-nov5-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.qt_golfhub_app import GolfHub
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    errors=[]
    with ExitStack() as stack:
        for target in ('socket.create_connection','socket.socket.connect','socket.getaddrinfo',
                       'urllib.request.urlopen','webbrowser.open','app.qt_golfhub_app.CacheWorker',
                       'app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.BookingAssistDialog',
                       'app.qt_golfhub_app.fetch_site_result','app.golfhub_core.fetch_text',
                       'app.golfhub_core.get_weather_for_date'):
            stack.enter_context(patch(target,side_effect=AssertionError('Offline keyboard probe')))
        stack.enter_context(patch('sys.excepthook',side_effect=lambda *a: errors.append(str(a[1]))))
        with patch.object(GolfHub,'show_initial_cache'):
            window=GolfHub()
        window._stop_deferred_timers()
        window.resize(980,640)
        window.show()
        def settle():
            for _ in range(8): app.processEvents()
        def focus_name():
            widget=app.focusWidget()
            if widget is None: return None
            for name in ('date','time_preset','time_from','time_to','players','course_button','search_button','live_button','results_scroll','holes18','holes9'):
                if widget is getattr(window,name): return name
            return type(widget).__name__+':'+widget.objectName()
        settle()
        checks=[]
        for action in ('cancel','apply'):
            before=window.date.selected_qdates()
            window.date.setFocus()
            QTest.keyClick(window.date,Qt.Key_Space)
            settle()
            popup=window.date.picker_popup()
            table=popup.calendar._calendar_view
            QTest.keyClick(table,Qt.Key_Right)
            QTest.keyClick(table,Qt.Key_Space)
            pending=popup.selected_dates()
            if action=='cancel':
                QTest.keyClick(table,Qt.Key_Escape)
            else:
                for _ in range(12):
                    if popup.done_button.hasFocus(): break
                    QTest.keyClick(app.focusWidget(),Qt.Key_Tab)
                assert popup.done_button.hasFocus()
                QTest.keyClick(popup.done_button,Qt.Key_Space)
            settle()
            expected=before if action=='cancel' else pending
            checks.append({'scenario':f'popup {action} restores date-button focus and expected selection',
                           'focus':focus_name(),'pass':focus_name()=='date' and window.date.picker_popup() is None and window.date.selected_qdates()==expected,
                           'selected':[x.toString('yyyy-MM-dd') for x in window.date.selected_qdates()]})
        window.time_preset.setFocus()
        QTest.keyClick(window.time_preset,Qt.Key_End)
        settle()
        path=[]
        for _ in range(14):
            QTest.keyClick(app.focusWidget(),Qt.Key_Tab)
            path.append(focus_name())
            if app.focusWidget() is window.time_preset: break
        checks.append({'scenario':'custom range controls reachable in normal Tab cycle',
                       'preset':window.time_preset.currentText(),'focus_path':path,
                       'pass':window.time_preset.currentText()=='Custom range' and all(name in path for name in ('time_from','time_to'))})
        window.time_preset.setFocus()
        QTest.keyClick(window.time_preset,Qt.Key_Home)
        settle()
        path=[]
        for _ in range(14):
            QTest.keyClick(app.focusWidget(),Qt.Key_Tab)
            path.append(focus_name())
            if app.focusWidget() is window.time_preset: break
        checks.append({'scenario':'hidden custom controls excluded from Tab cycle',
                       'preset':window.time_preset.currentText(),'focus_path':path,
                       'pass':window.time_preset.currentText()=='Any time' and not any(name in path for name in ('time_from','time_to'))})
        report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'source_sha256':hashlib.sha256((ROOT/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                'scope':'Linux Qt offscreen 980x640; bounded synthetic keyboard input; sockets/DNS/provider/weather/browser/booking dialogs blocked; no native-screen-reader or device claims',
                'checks':checks,'callback_errors':errors}
        (OUT/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
        cleanup_qt_widgets()
        print(json.dumps({'checks':len(checks),'passed':sum(c['pass'] for c in checks),'callback_errors':errors}))
        assert not errors
        assert all(c['pass'] for c in checks)
signal.alarm(0)
