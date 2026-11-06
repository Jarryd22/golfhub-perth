"""Bounded secondary-pointer checks on exact PR25. No external operations."""
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

ROOT=Path('/workspace/golfhub-20261105')
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
signal.alarm(30)
with tempfile.TemporaryDirectory(prefix='golfhub-secondary-input-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate, QPoint, Qt
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtWidgets import QApplication
    from app import qt_golfhub_app as ui
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    errors=[]
    def settle():
        for _ in range(8): app.processEvents()
    with ExitStack() as stack:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo',
                       'urllib.request.urlopen','webbrowser.open','app.qt_golfhub_app.CacheWorker',
                       'app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.BookingAssistDialog',
                       'app.qt_golfhub_app.fetch_site_result','app.golfhub_core.fetch_text',
                       'app.golfhub_core.get_weather_for_date'):
            stack.enter_context(patch(target,side_effect=AssertionError('Offline input probe')))
        stack.enter_context(patch('sys.excepthook',side_effect=lambda *a: errors.append(str(a[1]))))
        stack.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        checks=[]
        with patch.object(ui.GolfHub,'show_initial_cache'):
            window=ui.GolfHub()
        window._stop_deferred_timers()
        window.resize(980,640)
        window.show()
        settle()
        window.date.open_picker()
        settle()
        popup=window.date.picker_popup()
        view=popup.calendar._calendar_view
        original=popup.selected_dates()
        target=original[0].addDays(2)
        popup.calendar.setSelectedDate(target)
        settle()
        position=view.visualRect(view.currentIndex()).center()
        assert view.currentIndex().data()==target.day()
        for name,button in (('right',Qt.RightButton),('middle',Qt.MiddleButton),('left',Qt.LeftButton)):
            clicked=QSignalSpy(popup.calendar.clicked)
            before=popup.selected_dates()
            QTest.mouseClick(view.viewport(),button,pos=position)
            settle()
            after=popup.selected_dates()
            expected=sorted(original+[target]) if name=='left' else before
            checks.append({'scenario':f'{name} click on visible calendar date','pass':after==expected,
                           'date':target.toString('yyyy-MM-dd'),'clicked_signals':clicked.count(),
                           'before':[d.toString('yyyy-MM-dd') for d in before],
                           'after':[d.toString('yyyy-MM-dd') for d in after]})
        QTest.keyClick(view,Qt.Key_Escape)
        settle()
        window.toggle_courses()
        settle()
        row=next(row for row in window.course_rows if row.isVisible())
        for kind,widget,position in (('row',row,QPoint(row.width()-2,row.height()//2)),
                                     ('checkbox',row.check,row.check.rect().center())):
            for name,button in (('right',Qt.RightButton),('middle',Qt.MiddleButton),('left',Qt.LeftButton)):
                before=row.check.isChecked()
                toggled=QSignalSpy(row.toggled)
                QTest.mouseClick(widget,button,pos=position)
                settle()
                after=row.check.isChecked()
                expected=not before if name=='left' else before
                checks.append({'scenario':f'{name} click on course {kind}','pass':after==expected,
                               'course':row.site.name,'before':before,'after':after,'toggled_signals':toggled.count()})
        report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'source_sha256':hashlib.sha256((ROOT/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                'scope':'Linux Qt offscreen 980x640; real application popup/course widgets, synthetic input; sockets/DNS/provider/weather/browser/booking dialogs blocked; no worker, notification, native-device or screen-reader verification',
                'checks':checks,'callback_errors':errors}
        (OUT/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
        cleanup_qt_widgets()
        print(json.dumps({'checks':len(checks),'passed':sum(c['pass'] for c in checks),'callback_errors':errors}))
        assert not errors
signal.alarm(0)
