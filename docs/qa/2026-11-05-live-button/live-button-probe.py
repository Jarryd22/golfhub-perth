"""Synthetic single-date worker completion after editing pending dates."""
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
from unittest.mock import MagicMock, patch
parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,default=Path('/workspace/golfhub-20261104'))
parser.add_argument('--output',type=Path,default=Path('/workspace/scratch/golfhub-20261105-live-mode'))
args=parser.parse_args()
root,output=args.root.resolve(),args.output.resolve()
output.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-live-mode-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication
    from app import qt_golfhub_app as ui
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    records=[]
    with ExitStack() as stack:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex',
                       'socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.fetch_site_result',
                       'app.course_results.get_weather_for_date','app.qt_golfhub_app.BookingAssistDialog'):
            stack.enter_context(patch(target,side_effect=AssertionError('Offline probe')))
        stack.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        stack.enter_context(patch.object(ui.ScanWorker,'moveToThread'))
        stack.enter_context(patch.object(ui,'save_local_snapshot'))
        stack.enter_context(patch.object(ui.QMessageBox,'critical'))
        for outcome, mode in ((outcome,mode) for outcome in ('success','failure','cancelled') for mode in ('pending_multi','back_to_single')):
            errors=[]
            with ExitStack() as case:
                case.enter_context(patch('sys.excepthook',side_effect=lambda *a:errors.append(str(a[1]))))
                thread=MagicMock();thread.isRunning.return_value=True;thread.wait.return_value=True
                case.enter_context(patch.object(ui,'QThread',return_value=thread))
                with patch.object(ui.GolfHub,'show_initial_cache'):
                    window=ui.GolfHub()
                window._stop_deferred_timers();window.resize(1280,800);window.show()
                window.set_all(False)
                next(r for r in window.course_rows if r.site.name=='Araluen').check.setChecked(True)
                window.date.set_dates([QDate(2033,1,2)])
                window.search_live();worker=window.scan_worker
                window.date.set_dates([QDate(2033,1,3),QDate(2033,1,4)])
                if mode=='back_to_single':window.date.set_dates([QDate(2033,1,3)])
                pending={'dates':window.selected_dates(),'live_enabled':window.live_button.isEnabled(),
                         'tooltip':window.live_button.toolTip(),'helper':window.search_helper.text()}
                if outcome=='failure':worker.failed.emit('RuntimeError: Synthetic worker failure')
                else:worker.finished.emit([],outcome=='cancelled')
                terminal={'live_enabled':window.live_button.isEnabled(),'scan_thread_retained':window.scan_thread is thread}
                status_before=window.status.text();window.live_button.click()
                terminal.update(click_status_changed=window.status.text()!=status_before,worker_unchanged=window.scan_worker is worker)
                thread.isRunning.return_value=False;thread.wait.return_value=False
                window.scan_thread_done()
                if mode=='back_to_single':window.date.set_dates([QDate(2033,1,4)])
                held={'live_enabled':window.live_button.isEnabled(),'scan_thread_retained':window.scan_thread is thread,
                      'thread_is_running':thread.isRunning(),'wait_zero':thread.wait(0)}
                thread.wait.return_value=True
                window.scan_thread_done()
                for _ in range(3):app.processEvents()
                completed={'live_enabled':window.live_button.isEnabled(),'tooltip':window.live_button.toolTip(),
                           'helper':window.search_helper.text(),'status':window.status.text(),
                           'scan_thread_is_none':window.scan_thread is None,'active_context_dates':window.context['dates']}
                window.grab().save(str(output/f'{outcome}-{mode}.png'))
                window.live_button.click()
                clicked={'status':window.status.text(),'new_worker_started':window.scan_thread is not None}
                records.append({'outcome':outcome,'mode':mode,'pending':pending,'terminal_before_cleanup':terminal,'held_cleanup_after_date_change':held,'completed':completed,'clicked':clicked,'callback_errors':errors})
                if window.scan_worker is not None and window.scan_worker is not worker:window.scan_worker.deleteLater()
                window.scan_thread=None;window.scan_worker=None
                worker.deleteLater();cleanup_qt_widgets()
        report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                'method':'Real source controls and signal callbacks; synthetic worker completion; inert native thread; sockets/browser/provider/weather/save/holds blocked or intercepted; Linux offscreen only',
                'cases':records}
        (output/'probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
