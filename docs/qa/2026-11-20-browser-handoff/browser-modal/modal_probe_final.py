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
parser.add_argument('--route',choices=['direct','long_booking'],default='direct')
args=parser.parse_args()
root,out=args.root.resolve(),args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
report={'utc':datetime.now(timezone.utc).isoformat(),'source_root':str(root),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'expect_warning':args.expect_warning,'route':args.route,'cases':[],'callback_errors':[]}
with tempfile.TemporaryDirectory(prefix='golfhub-browser-modal-') as temp:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=temp,TEMP=temp,TMP=temp,XDG_CACHE_HOME=temp)
    from PySide6.QtCore import QDate,QTimer,Qt,QRect,QPoint
    from PySide6.QtGui import QPalette
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
                selected_name='Altone Park' if args.route=='direct' else 'Araluen'
                next(r for r in window.course_rows if r.site.name==selected_name).check.setChecked(True)
                window.date.setDate(QDate(2033,1,3))
                window.context=window.params()
                if args.route=='direct':
                    results=window.add_direct_results([])
                else:
                    long_url='https://araluenestategolfcourse.miclub.com.au/guests/bookings/ViewPublicTimesheet.msp?bookingResourceId=3000000&selectedDate=2033-01-03&feeGroupId=102807'
                    results=[{'site_name':'Araluen','url':long_url,'hole_label':'18 holes','decorated_rows':[{'time':'9:00 am','minutes':540,'spots':4,'source_url':long_url}],'error':None,'weather':None}]
                window.render_results(results,'Synthetic configured direct link')
                events()
                card=window.results_body.findChild(ui.DirectCourseCard if args.route=='direct' else ui.TeeTimeCard)
                action=next(b for b in card.findChildren(QPushButton) if b.text()==('VIEW COURSE' if args.route=='direct' else 'BOOK'))
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
                            text_format=int(modal.textFormat().value),
                            fits_parent_viewport=modal.width()<=window.width() and modal.height()<=window.height(),
                            label_metrics=[{'name':l.objectName(),'text':l.text(),'geometry':rect(l),'word_wrap':l.wordWrap(),
                                'mouse_selectable':bool(l.textInteractionFlags() & Qt.TextSelectableByMouse),
                                'keyboard_selectable':bool(l.textInteractionFlags() & Qt.TextSelectableByKeyboard)}
                                for l in modal.findChildren(QLabel) if l.text()])
                        ok=modal.button(QMessageBox.Ok)
                        position=ok.mapTo(modal,QPoint(0,0))
                        ok_rect=QRect(position,ok.size())
                        data['ok_button_geometry_in_dialog']={'x':ok_rect.x(),'y':ok_rect.y(),'width':ok_rect.width(),'height':ok_rect.height()}
                        data['ok_inside_dialog']=modal.rect().contains(ok_rect)
                        image=ok.grab().toImage()
                        data['ok_palette_button_text']=ok.palette().color(QPalette.Active,QPalette.ButtonText).name()
                        data['ok_rendered_background_samples']=[image.pixelColor(x,y).name() for x,y in [(8,image.height()//2),(image.width()//2,5)]]
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
                    expect(failure.get('text_format')==int(Qt.PlainText.value),'message uses plain text for exact URL')
                    expect(failure.get('text_interaction_flags')==int((Qt.TextSelectableByMouse|Qt.TextSelectableByKeyboard).value) and all(label['mouse_selectable'] and label['keyboard_selectable'] for label in failure['label_metrics']),'shown body retains mouse and keyboard selection flags')
                    expect(failure.get('ok_palette_button_text')=='#090909' and failure.get('ok_rendered_background_samples')==['#f59e0b','#f59e0b'],'shown OK has existing dark-text and gold-background palette')
                    expect(failure.get('fits_parent_viewport'),'message fits parent viewport at this size')
                expect(QApplication.activeModalWidget() is None,'no modal remains after failure stage')
                record['focus_returned_to_action']=QApplication.focusWidget() is action
                record['active_window_after_dismissal']=type(QApplication.activeWindow()).__name__ if QApplication.activeWindow() else None
                if not record['focus_returned_to_action']:
                    window.activateWindow()
                    events()
                    record['explicit_window_activation_used']=True
                else:
                    record['explicit_window_activation_used']=False
                record['focus_after_activation']=QApplication.focusWidget() is action
                expect(record['focus_after_activation'],'explicit window activation restores the course action in offscreen fixture')
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
report['source_sha256_after']=hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest()
report['source_unchanged_during_probe']=report['source_sha256_after']==report['app_sha256']
report['limits']='Actual course/BOOK Space/mouse actions, realQMessageBox and queued inspector; OKReturn with explicitfocus anchor; explicitwindowreactivation after demonstratedplainQt focusloss. BrowserFalse/True intercepted. No externalbrowser/network/provider,worker,persistence,booking/hold/notification/native device execution.'
(out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary']),flush=True)
sys.exit(bool(report['summary']['exceptions'] or report['summary']['callback_errors'] or not report['source_unchanged_during_probe']))
