"""Owned startup timer controls with actual QApplication.exec and inert workers."""
import argparse
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import subprocess,sys,tempfile,traceback
from unittest.mock import MagicMock,patch

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--case',choices=['automatic_latest_controls','close_before_initial','close_between_callbacks'],required=True)
args=parser.parse_args()
root,out=args.root.resolve(),args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
report={'case':args.case,'utc':datetime.now(timezone.utc).isoformat(),
        'source_root':str(root),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'assertions':[],'callback_errors':[],'initial_callbacks':0}
with tempfile.TemporaryDirectory(prefix='golfhub-startup-controls-') as temp:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=temp,TEMP=temp,TMP=temp,XDG_CACHE_HOME=temp)
    from PySide6.QtCore import QDate,QTimer,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app import qt_golfhub_app as ui
    from app import shared_cache as cache
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    threads=[]
    def thread_factory():
        thread=MagicMock()
        thread.isRunning.return_value=True
        thread.wait.return_value=False
        threads.append(thread)
        return thread
    def expect(condition,name):
        report['assertions'].append({'name':name,'passed':bool(condition)})
        assert condition,name
    with ExitStack() as guards:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo',
                       'webbrowser.open','app.qt_golfhub_app.fetch_site_result','app.qt_golfhub_app.fetch_shared_snapshot',
                       'app.course_results.get_weather_for_date','app.qt_golfhub_app.BookingAssistDialog',
                       'app.qt_golfhub_app.save_local_snapshot'):
            guards.enter_context(patch(target,side_effect=AssertionError('Offline startup controls')))
        guards.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        guards.enter_context(patch.object(cache,'LOCAL_CACHE_DIR',Path(temp)/'cache'))
        guards.enter_context(patch.object(ui,'QThread',side_effect=thread_factory))
        for worker_class in (ui.CacheWorker,ui.ScanWorker):
            guards.enter_context(patch.object(worker_class,'moveToThread'))
            guards.enter_context(patch.object(worker_class,'run',side_effect=AssertionError('No workers')))
        guards.enter_context(patch('sys.excepthook',side_effect=lambda kind,value,_tb:
            report['callback_errors'].append({'type':kind.__name__,'message':str(value)})))
        payload=cache.make_snapshot('2033-01-03','18',[{'site_name':'Araluen','url':'https://example.invalid/saved',
            'hole_label':'18 holes','decorated_rows':[{'time':'9:00 am','minutes':540,'spots':4}],
            'error':None,'weather':None}])
        path=cache.local_snapshot_path('2033-01-03','18')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(payload))
        saved_bytes=path.read_bytes()
        window=ui.GolfHub()
        window.set_all(False)
        next(row for row in window.course_rows if row.site.name=='Araluen').check.setChecked(True)
        window.show()
        def initial_observer():
            try:
                report['initial_callbacks']+=1
                expect(window.header_status.text().startswith('SAVED CACHE /'),'owned initial callback displays isolated saved cache')
                expect(window._cache_search_timer.isActive() and window._cache_search_timer.interval()==100,'100ms automatic timer scheduled')
                report['initial_timer_remaining']=window._cache_search_timer.remainingTime()
                if args.case=='close_between_callbacks':
                    window.close()
                elif args.case=='automatic_latest_controls':
                    window.date.set_dates([QDate(2033,1,4)])
                    QTest.mouseClick(window.holes9,Qt.LeftButton)
                    window.players.setCurrentText('1')
            except Exception:
                report['failure']=traceback.format_exc()
        window._initial_cache_timer.timeout.connect(initial_observer)
        if args.case=='close_before_initial':
            window.close()
        def inspect_and_finish():
            try:
                expect(not report.get('failure'),'initial observer completed without failure')
                if args.case=='automatic_latest_controls':
                    expect(report['initial_callbacks']==1,'initial callback delivered once')
                    expect(len(threads)==1 and window.cache_worker is not None,'automatic cache search starts once')
                    threads[0].start.assert_called_once()
                    worker=window.cache_worker
                    report['automatic_request']={'dates':worker.date_strings,'holes':worker.hole_type,
                        'players':window.context['players'],'sites':[s.name for s in window.context['sites']]}
                    expect(report['automatic_request']=={'dates':['2033-01-04'],'holes':'9','players':1,'sites':['Araluen']},'automatic search uses latest controls when no manual search is submitted')
                    expect(window.scan_thread is None,'automatic check does not start live work')
                    expect(window._perth_date_timer.isActive(),'Perth rollover timer remains active')
                else:
                    expected_initial=0 if args.case=='close_before_initial' else 1
                    expect(report['initial_callbacks']==expected_initial,'close occurs at intended startup phase')
                    expect(not window.isVisible(),'window closes')
                    expect(not threads and window.cache_worker is None and window.scan_worker is None,'early close starts no worker')
                    expect(not window._initial_cache_timer.isActive() and not window._cache_search_timer.isActive(),'both startup timers inactive after close')
                    expect(not window._perth_date_timer.isActive(),'Perth timer stopped on close')
                expect(path.read_bytes()==saved_bytes,'isolated saved cache bytes unchanged')
                report['completed']=True
            except Exception:
                report['failure']=traceback.format_exc()
            finally:
                worker=window.cache_worker
                window.scan_thread=window.scan_worker=None
                window.cache_thread=window.cache_worker=None
                if worker is not None:worker.deleteLater()
                (out/'before-fixture-release.json').write_text(json.dumps(report,indent=2)+'\n')
                app.quit()
        # A real bounded event-loop interval; application startup intervals stay0/100ms.
        QTimer.singleShot(300,inspect_and_finish)
        app.exec()
        window._stop_deferred_timers()
        cleanup_qt_widgets()
report['summary']={'assertions':len(report['assertions']),'failed_assertions':sum(not a['passed'] for a in report['assertions']),
                   'callback_errors':len(report['callback_errors']),'completed':report.get('completed',False)}
report['limits']='ActualQApplication.exec and unchanged owned startup timers; inertQThreads and blocked worker bodies. Controls are synthetic. No providers/network/browser/persistence/booking/hold/notification or nativeWindows behavior.'
(out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(bool(report.get('failure') or report['callback_errors'] or not report.get('completed')))
