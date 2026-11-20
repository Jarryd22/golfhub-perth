"""Actual QMessageBox inspection/dismissal; browser False/True are intercepted."""
import argparse
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import subprocess,sys,tempfile,traceback
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--expect-warning',action='store_true')
args=parser.parse_args()
root,out=args.root.resolve(),args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
report={'utc':datetime.now(timezone.utc).isoformat(),'source_root':str(root),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'expect_warning':args.expect_warning,'cases':[],'callback_errors':[]}
with tempfile.TemporaryDirectory(prefix='golfhub-browser-modal-') as temp:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=temp,TEMP=temp,TMP=temp,XDG_CACHE_HOME=temp)
    from PySide6.QtCore import QDate,QTimer,Qt,QRect,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QLabel,QMessageBox,QPushButton
    from app import qt_golfhub_app as ui
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    with ExitStack() as guards:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo',
                       'app.qt_golfhub_app.fetch_site_result','app.qt_golfhub_app.fetch_shared_snapshot',
                       'app.course_results.get_weather_for_date','app.qt_golfhub_app.BookingAssistDialog',
                       'app.qt_golfhub_app.save_local_snapshot','app.qt_golfhub_app.CacheWorker','app.qt_golfhub_app.ScanWorker'):
            guards.enter_context(patch(target,side_effect=AssertionError('Offline real-message-box probe')))
        browser=guards.enter_context(patch('app.qt_golfhub_app.webbrowser.open',return_value=False))
        guards.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        guards.enter_context(patch('sys.excepthook',side_effect=lambda kind,value,_tb:
            report['callback_errors'].append({'type':kind.__name__,'message':str(value)})))
        def events():
            for _ in range(4):app.processEvents()
        def rect(widget):
            r=widget.geometry()
            return {'x':r.x(),'y':r.y(),'width':r.width(),'height':r.height()}
        for width,height in ((1280,800),(980,640)):
            record={'viewport':[width,height],'assertions':[],'modals':[]}
            report['cases'].append(record)
            def expect(condition,name):
                record['assertions'].append({'name':name,'passed':bool(condition)})
                assert condition,name
            window=None
            try:
                with patch.object(ui.GolfHub,'show_initial_cache'):
                    window=ui.GolfHub()
                window._stop_deferred_timers()
                window.resize(width,height)
                window.show()
                window.set_all(False)
                next(r for r in window.course_rows if r.site.name=='Altone Park').check.setChecked(True)
                window.date.setDate(QDate(2033,1,3))
                window.context=window.params()
                results=window.add_direct_results([])
                window.render_results(results,'Synthetic configured direct link')
                events()
                card=window.results_body.findChild(ui.DirectCourseCard)
                action=next(b for b in card.findChildren(QPushButton) if b.text()=='VIEW COURSE')
                url=card.result['url']
                record['url']=url
                record['action_name']=action.accessibleName()
                window.results_scroll.ensureWidgetVisible(action)
                action.setFocus()
                events()
                original_results=window.last_results
                def inspect_and_dismiss(stage):
                    modal=QApplication.activeModalWidget()
                    data={'stage':stage,'found':isinstance(modal,QMessageBox)}
                    record['modals'].append(data)
                    if not isinstance(modal,QMessageBox):return
                    try:
                        data.update(title=modal.windowTitle(),text=modal.text(),geometry=rect(modal),
                            visible=modal.isVisible(),modal=modal.isModal(),
                            text_interaction_flags=int(modal.textInteractionFlags().value),
                            label_metrics=[{'name':l.objectName(),'text':l.text(),'geometry':rect(l),'word_wrap':l.wordWrap(),
                                'mouse_selectable':bool(l.textInteractionFlags() & Qt.TextSelectableByMouse),
                                'keyboard_selectable':bool(l.textInteractionFlags() & Qt.TextSelectableByKeyboard)}
                                for l in modal.findChildren(QLabel) if l.text()])
                        ok=modal.button(QMessageBox.Ok)
                        position=ok.mapTo(modal,QPoint(0,0))
                        ok_rect=QRect(position,ok.size())
                        data['ok_button_geometry_in_dialog']={'x':ok_rect.x(),'y':ok_rect.y(),'width':ok_rect.width(),'height':ok_rect.height()}
                        data['ok_inside_dialog']=modal.rect().contains(ok_rect)
                        modal.grab().save(str(out/f'{stage}-modal-{width}x{height}.png'))
                        ok.setFocus()
                        QTest.keyClick(ok,Qt.Key_Return)
                        data['dismissed_by']='Return on actual OK button (explicit focus anchor)'
                    except Exception:
                        data['inspection_failure']=traceback.format_exc()
                        modal.reject()
                browser.reset_mock(return_value=True)
                browser.return_value=False
                QTimer.singleShot(20,lambda:inspect_and_dismiss('failure'))
                QTest.keyClick(action,Qt.Key_Space)
                QTest.qWait(40)
                events()
                expect(browser.call_count==1 and browser.call_args.args==(url,),'Space dispatches the exact configured URL once')
                expect(len(record['modals'])==1,'scheduled failure observer ran once')
                failure=record['modals'][0]
                expect(failure['found']==args.expect_warning,'failure modal presence matches baseline or repaired contract')
                if args.expect_warning:
                    expect(failure.get('title')=='Could not open browser','real warning has expected title')
                    expect(failure.get('text')=='GolfHub could not open this link in your browser.\n\nOpen this address manually:\n'+url,'real warning includes recovery guidance and exact URL')
                    expect(failure.get('visible') and failure.get('modal'),'warning is actually visible and modal')
                    expect(failure.get('ok_inside_dialog') and not failure.get('inspection_failure'),'OK is inside dialog and modal inspection succeeds')
                expect(QApplication.activeModalWidget() is None,'no modal remains after failure stage')
                record['focus_returned_to_action']=QApplication.focusWidget() is action
                expect(record['focus_returned_to_action'],'focus returns to the course action')
                expect(window.last_results is original_results,'failure leaves result data unchanged')
                browser.return_value=True
                QTimer.singleShot(20,lambda:inspect_and_dismiss('retry'))
                QTest.mouseClick(action,Qt.LeftButton)
                QTest.qWait(40)
                events()
                expect(browser.call_count==2 and browser.call_args.args==(url,),'mouse retry dispatches the same URL once more')
                expect(len(record['modals'])==2 and not record['modals'][1]['found'],'True browser result has no warning')
                expect(window.last_results is original_results,'successful intercepted retry leaves results unchanged')
                window.grab().save(str(out/f'after-retry-{width}x{height}.png'))
                record['completed']=True
            except Exception:
                record['failure']=traceback.format_exc()
            finally:
                if window is not None:
                    window._stop_deferred_timers()
                    window.cache_thread=window.cache_worker=None
                    window.scan_thread=window.scan_worker=None
                cleanup_qt_widgets()
            print(json.dumps(record),flush=True)
report['summary']={'viewports':len(report['cases']),'completed':sum(c.get('completed',False) for c in report['cases']),
                  'recorded_assertions':sum(len(c['assertions']) for c in report['cases']),
                  'failed_assertions':sum(not a['passed'] for c in report['cases'] for a in c['assertions']),
                  'exceptions':sum('failure' in c for c in report['cases']),'callback_errors':len(report['callback_errors'])}
report['limits']='Actual course Space/mouse actions, realQMessageBox and queued inspector; OKReturn with explicitfocus anchor. BrowserFalse/True intercepted. No externalbrowser/network/provider,worker,persistence,booking/hold/notification/native device execution.'
(out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary']),flush=True)
sys.exit(bool(report['summary']['exceptions'] or report['summary']['callback_errors']))
