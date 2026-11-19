"""Actual owned startup timers with inert workers; no native QThread execution."""
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

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--case',choices=['changed_controls','unchanged_controls'],required=True)
args=parser.parse_args()
root,out=args.root.resolve(),args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
report={'utc':datetime.now(timezone.utc).isoformat(),'case':args.case,
        'root':str(root),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'callback_errors':[],'stages':[]}
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-firstlaunch-') as temp:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=temp,TEMP=temp,TMP=temp,XDG_CACHE_HOME=temp)
    from PySide6.QtCore import QDate,QTimer,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QLabel,QPushButton
    from app import qt_golfhub_app as ui
    from app import shared_cache as cache
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    threads,workers=[],[]
    def thread_factory():
        thread=MagicMock()
        thread.isRunning.return_value=True
        thread.wait.return_value=False
        thread.quit.side_effect=lambda *_args:setattr(thread.isRunning,'return_value',False)
        threads.append(thread)
        return thread
    def serial(context):
        return {**{k:v for k,v in context.items() if k!='sites'},'sites':[s.name for s in context.get('sites',[])]}
    def result(date,holes,clock='9:00 am',minutes=540):
        return {'site_name':'Araluen','url':f'https://example.invalid/{date}/{holes}',
                'hole_label':f'{holes} holes','decorated_rows':[{'time':clock,'minutes':minutes,'spots':4}],
                'weather':None,'error':None}
    with ExitStack() as guards:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo',
                       'webbrowser.open','app.qt_golfhub_app.fetch_site_result','app.qt_golfhub_app.fetch_shared_snapshot',
                       'app.course_results.get_weather_for_date','app.qt_golfhub_app.BookingAssistDialog'):
            guards.enter_context(patch(target,side_effect=AssertionError('Offline startup diagnostic')))
        guards.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        guards.enter_context(patch.object(cache,'LOCAL_CACHE_DIR',Path(temp)/'cache'))
        guards.enter_context(patch.object(ui,'QThread',side_effect=thread_factory))
        for worker_class in (ui.ScanWorker,ui.CacheWorker):
            guards.enter_context(patch.object(worker_class,'moveToThread'))
            guards.enter_context(patch.object(worker_class,'run',side_effect=AssertionError('Worker bodies blocked')))
        saved=guards.enter_context(patch.object(ui,'save_local_snapshot'))
        guards.enter_context(patch.object(ui.QMessageBox,'critical'))
        guards.enter_context(patch('sys.excepthook',side_effect=lambda kind,value,_tb:
            report['callback_errors'].append({'type':kind.__name__,'message':str(value)})))
        initial_date='2033-01-03'
        initial_payload=cache.make_snapshot(initial_date,'18',[result(initial_date,'18','12:00 pm',720)])
        path=cache.local_snapshot_path(initial_date,'18')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(initial_payload))
        initial_bytes=path.read_bytes()
        window=ui.GolfHub()
        window.resize(1280,800)
        window.set_all(False)
        next(row for row in window.course_rows if row.site.name=='Araluen').check.setChecked(True)
        window.players.setCurrentText('4')
        window.show()
        timed_out=QTimer()
        timed_out.setSingleShot(True)
        def fail_timeout():
            report['fixture_failure']='Diagnostic did not finish within3s'
            app.quit()
        timed_out.timeout.connect(fail_timeout)
        timed_out.start(3000)

        def after_automatic_timer():
            try:
                report['stages'].append({'phase':'after_automatic_timer','context':serial(window.context),
                    'cache_owner':window.cache_thread is not None,'live_owner':window.scan_thread is not None,
                    'header':window.header_status.text(),'thread_count':len(threads),
                    'auto_timer_active':window._cache_search_timer.isActive()})
                assert window.scan_worker is live_worker
                cache_worker=window.cache_worker
                if cache_worker is not None:
                    workers.append(cache_worker)
                    report['automatic_cache_request']={'dates':cache_worker.date_strings,'holes':cache_worker.hole_type}
                    active=window.context
                    cache_worker.finished.emit({active['date']:cache.make_snapshot(active['date'],active['holes'],[result(active['date'],active['holes'],'10:00 am',600)])})
                live_worker.finished.emit([result(initial_date,'18')],False)
                report['saved_payloads']=[{'date':call.args[0]['date'],'holes':call.args[0]['holes'],
                    'results':call.args[0]['results']} for call in saved.call_args_list]
                report['rendered']={'context':serial(window.context),'header':window.header_status.text(),
                    'status':window.status.text(),'labels':[l.text() for l in window.results_body.findChildren(QLabel)],
                    'book_names':[b.accessibleName() for b in window.results_body.findChildren(QPushButton) if b.text()=='BOOK']}
                report['live_payload_saved_with_submitted_date_round']=bool(saved.call_count==1 and
                    saved.call_args.args[0]['date']==initial_date and saved.call_args.args[0]['holes']=='18')
                report['initial_saved_bytes_unchanged']=path.read_bytes()==initial_bytes
                report['completed']=True
                window.grab().save(str(out/'after-live-completion.png'))
            except Exception:
                report['fixture_failure']=traceback.format_exc()
            finally:
                timed_out.stop()
                app.quit()

        def after_initial_timer():
            global live_worker
            try:
                report['stages'].append({'phase':'after_initial_saved_render','context':serial(window.context),
                    'header':window.header_status.text(),'auto_timer_active':window._cache_search_timer.isActive(),
                    'auto_timer_interval':window._cache_search_timer.interval(),
                    'auto_timer_remaining':window._cache_search_timer.remainingTime(),
                    'rows':[c.row for c in window.results_body.findChildren(ui.TeeTimeCard)]})
                assert window._cache_search_timer.isActive() and window._cache_search_timer.interval()==100
                assert window.live_button.isEnabled()
                QTest.mouseClick(window.live_button,Qt.LeftButton)
                live_worker=window.scan_worker
                workers.append(live_worker)
                assert live_worker is not None and len(threads)==1
                window.scan_thread.start.assert_called_once()
                report['live_submitted']=serial(window.context)
                if args.case=='changed_controls':
                    window.date.set_dates([QDate(2033,1,4)])
                    QTest.mouseClick(window.holes9,Qt.LeftButton)
                    window.players.setCurrentText('1')
                report['stages'].append({'phase':'after_explicit_live','context':serial(window.context),
                    'pending_controls':serial(window.params()),'auto_timer_active':window._cache_search_timer.isActive(),
                    'auto_timer_remaining':window._cache_search_timer.remainingTime()})
                QTimer.singleShot(250,after_automatic_timer)
            except Exception:
                report['fixture_failure']=traceback.format_exc()
                timed_out.stop()
                app.quit()
        window._initial_cache_timer.timeout.connect(after_initial_timer)
        app.exec()
        window._stop_deferred_timers()
        window._cache_cleanup_timer.stop()
        window._scan_cleanup_timer.stop()
        window.scan_thread=window.scan_worker=None
        window.cache_thread=window.cache_worker=None
        for worker in workers:
            if worker is not None:worker.deleteLater()
        cleanup_qt_widgets()
report['limits']='Real QApplication.exec and unchanged owned0ms/100ms startup timers; injected user action just after initial-render timeout. Native QThreads and all worker bodies inert. No provider/network/browser/bookings/holds/notification; save intercepted and only isolated synthetic file read. Controlled ordering does not establish natural incidence or historical Windows timeout cause.'
(out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(bool(report.get('fixture_failure') or report['callback_errors'] or not report.get('completed')))
