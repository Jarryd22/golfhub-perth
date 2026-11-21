"""Follow partial-cache guidance through live Stop and corrected cached retry."""
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
args=parser.parse_args()
root,out=args.root.resolve(),args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
sources=('app/qt_golfhub_app.py','app/shared_cache.py')
hashes=lambda:{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources}
report={'utc':datetime.now(timezone.utc).isoformat(),'source_root':str(root),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'source_sha256':hashes(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'assertions':[],'stages':[],'callback_errors':[]}
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-recovery-chain-') as temp:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=temp,TEMP=temp,TMP=temp,XDG_CACHE_HOME=temp)
    from PySide6.QtCore import QDate,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QLabel,QPushButton
    from app import qt_golfhub_app as ui
    from app import shared_cache as cache
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    def events():
        for _ in range(4):app.processEvents()
    def expect(condition,name):
        report['assertions'].append({'name':name,'passed':bool(condition)})
        assert condition,name
    def serial(context):
        return {**{k:v for k,v in context.items() if k!='sites'},'sites':[s.name for s in context.get('sites',[])]}
    def labels(widget):return [label.text() for label in widget.findChildren(QLabel)]
    def row(minutes,spots):
        h,m=divmod(minutes,60)
        return {'time':f'{h%12 or 12}:{m:02d} '+('am' if h<12 else 'pm'),'minutes':minutes,'spots':spots}
    def result(date,holes,rows=(),error=None):
        return {'site_name':'Araluen','url':f'https://example.invalid/{date}/{holes}',
                'hole_label':f'{holes} holes','decorated_rows':list(rows),'weather':None,'error':error}
    threads,workers=[],[]
    def thread_factory():
        thread=MagicMock()
        thread.isRunning.return_value=True
        thread.wait.return_value=True
        thread.quit.side_effect=lambda *_args:setattr(thread.isRunning,'return_value',False)
        threads.append(thread)
        return thread
    with ExitStack() as guards:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo',
                       'webbrowser.open','app.qt_golfhub_app.fetch_site_result','app.qt_golfhub_app.fetch_shared_snapshot',
                       'app.course_results.get_weather_for_date','app.qt_golfhub_app.BookingAssistDialog'):
            guards.enter_context(patch(target,side_effect=AssertionError('Offline recovery chain')))
        guards.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        guards.enter_context(patch.object(cache,'LOCAL_CACHE_DIR',Path(temp)/'cache'))
        guards.enter_context(patch.object(ui,'QThread',side_effect=thread_factory))
        for cls in (ui.ScanWorker,ui.CacheWorker):
            guards.enter_context(patch.object(cls,'moveToThread'))
            guards.enter_context(patch.object(cls,'run',side_effect=AssertionError('No worker body execution')))
        save=guards.enter_context(patch.object(ui,'save_local_snapshot'))
        guards.enter_context(patch('sys.excepthook',side_effect=lambda kind,value,_tb:
            report['callback_errors'].append({'type':kind.__name__,'message':str(value)})))
        originals={}
        for date,payload in [
            ('2033-01-02',cache.make_snapshot('2033-01-02','18',[result('2033-01-02','18',[row(540,2)])])),
            ('2033-01-03',cache.make_snapshot('2033-01-03','18',[result('2033-01-03','18',error='Synthetic provider timeout')]))]:
            path=cache.local_snapshot_path(date,'18')
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(payload))
            originals[path]=path.read_bytes()
        window=None
        try:
            with patch.object(ui.GolfHub,'show_initial_cache'):
                window=ui.GolfHub()
            window._stop_deferred_timers()
            window.resize(980,640)
            window.show()
            window.set_all(False)
            for course in window.course_rows:
                if course.site.name in ('Araluen','Altone Park'):course.check.setChecked(True)
            window.date.set_dates([QDate(2033,1,d) for d in (2,3,4)])
            window.players.setCurrentText('1')
            initial_context=window.params()
            booking=guards.enter_context(patch.object(window,'open_tee_time'))
            QTest.mouseClick(window.search_button,Qt.LeftButton)
            first_cache=window.cache_worker
            workers.append(first_cache)
            expect(first_cache is not None and len(threads)==1,'initial three-date Find starts one inert cache worker')
            first_cache.finished.emit({})
            window.cache_thread_done()
            events()
            expect(window.cache_thread is None,'initial cache ownership explicitly released before next action')
            expect(window.header_status.text()=='SHARED CACHE / 2 OF 3 DAYS','saved fallback reports two loaded days')
            summary=window.results_body.findChild(QLabel,'SummaryValue').text()
            expect(summary=='1 matching time across 2 loaded days','partial totals describe loaded days only')
            sections=list(window.day_sections)
            expect(len(sections)==3,'all three requested date sections remain present')
            expect('Availability incomplete' in sections[1].toggle.text(),'loaded provider error stays distinct from empty results')
            expect('Availability not checked' in sections[2].toggle.text(),'missing date stays unchecked')
            expect(len(window.results_body.findChildren(ui.DirectCourseCard))==1,'configured direct course link remains once for the range')
            missing=sections[2]
            window.results_scroll.ensureWidgetVisible(missing.toggle)
            missing.toggle.setFocus()
            QTest.keyClick(missing.toggle,Qt.Key_Space)
            events()
            note=next(label for label in missing.body.findChildren(QLabel) if 'select this date alone and use Refresh Live' in label.text())
            expect(note.isVisible(),'keyboard opens actionable missing-date guidance')
            window.results_scroll.ensureWidgetVisible(note)
            events()
            window.grab().save(str(out/'partial-missing-guidance.png'))
            old_results=window.last_results
            old_card=sections[0].findChild(ui.TeeTimeCard)
            report['stages'].append({'name':'partial cache','context':serial(window.context),
                'header':window.header_status.text(),'summary':summary,'section_titles':[s.toggle.text() for s in sections],
                'guidance':note.text()})

            window.date.setFocus()
            QTest.keyClick(window.date,Qt.Key_Space)
            events()
            picker=window.date.picker_popup()
            view=picker.calendar._calendar_view
            expect(picker.selected_dates()==[QDate(2033,1,d) for d in (2,3,4)],'calendar starts with displayed three-date selection')
            QTest.keyClick(view,Qt.Key_Return)
            QTest.keyClick(view,Qt.Key_Right)
            QTest.keyClick(view,Qt.Key_Return)
            expect(picker.selected_dates()==[QDate(2033,1,4)],'keyboard removes first two dates and retains missing date')
            picker.done_button.setFocus()
            QTest.keyClick(picker.done_button,Qt.Key_Space)
            events()
            expect(window.selected_dates()==['2033-01-04'],'Apply commits the missing date alone')
            expect(window.live_button.isEnabled(),'single-date recovery enables Refresh Live')
            QTest.mouseClick(window.live_button,Qt.LeftButton)
            live=window.scan_worker
            workers.append(live)
            expect(live is not None and len(threads)==2,'actual Refresh Live starts one inert request')
            expect(live.date_str=='2033-01-04' and live.hole_type=='18' and live.players==1,'live request uses narrowed submitted date and filters')
            expect(window.day_sections==sections and window.last_results is old_results,'live request retains the earlier partial view')
            QTest.mouseClick(window.stop_button,Qt.LeftButton)
            expect(live.cancel_requested,'actual Stop requests cancellation')
            partial=result('2033-01-04','18',[row(990,4)])
            live.finished.emit([partial],True)
            events()
            expect(save.call_count==0,'cancelled partial result is not saved')
            expect(all(path.read_bytes()==data for path,data in originals.items()),'cancel leaves both original saved files byte-identical')
            expect(window.header_status.text()=='REFRESH STOPPED / PREVIOUS RESULTS KEPT','cancel truthfully reports retained results')
            expect(window.day_sections==sections and window.last_results is old_results,'cancel keeps the original partial sections and result list')
            expect('Availability not checked' in missing.toggle.text() and note.text() in labels(missing),'cancel preserves unknown-date guidance')
            expect(sections[0].findChild(ui.TeeTimeCard) is old_card,'cancel preserves original matching card identity')
            old_book=next(b for b in old_card.findChildren(QPushButton) if b.text()=='BOOK')
            window.results_scroll.ensureWidgetVisible(old_book)
            old_book.setFocus()
            QTest.keyClick(old_book,Qt.Key_Space)
            expect(booking.call_count==1 and booking.call_args.kwargs['context']==initial_context,'retained BOOK keeps original submitted range/group/round context')
            expect(booking.call_args.args[1]['minutes']==540 and booking.call_args.args[1]['spots']==2,'retained BOOK dispatches original row rather than cancelled partial row')
            window.scan_thread_done()
            events()
            expect(window.scan_thread is None and window.live_button.isEnabled(),'retry availability returns after explicit inert cleanup')
            report['stages'].append({'name':'after Stop','active_context':serial(window.context),
                'display_context':serial(booking.call_args.kwargs['context']),
                'header':window.header_status.text(),'status':window.status.text(),'saved_calls':save.call_count})

            QTest.mouseClick(window.course_button,Qt.LeftButton)
            window.course_search.setFocus()
            QTest.keyClicks(window.course_search,'Araluen')
            events()
            clear=next(b for b in window.course_panel.findChildren(QPushButton) if b.text()=='Clear')
            select=next(b for b in window.course_panel.findChildren(QPushButton) if b.text()=='Select visible')
            QTest.mouseClick(clear,Qt.LeftButton)
            QTest.mouseClick(select,Qt.LeftButton)
            expect([s.name for s in window.selected_sites()]==['Araluen'],'actual name filter and bulk buttons select only intended course')
            QTest.mouseClick(window.course_button,Qt.LeftButton)
            QTest.mouseClick(window.holes9,Qt.LeftButton)
            window.players.setCurrentText('4')
            window.time_preset.setCurrentText('Afternoon')
            new_context=window.params()
            expect(new_context['date']=='2033-01-04' and new_context['holes']=='9' and new_context['players']==4 and (new_context['from'],new_context['to'])==(900,1110),'corrected request has intended date/round/group/preset')
            QTest.mouseClick(window.search_button,Qt.LeftButton)
            retry=window.cache_worker
            workers.append(retry)
            expect(retry is not None and len(threads)==3,'corrected Find starts one new cache request')
            expect(retry.date_strings==['2033-01-04'] and retry.hole_type=='9','retry worker receives corrected date and round')
            expect(not window.day_sections and not window.last_results,'new uncached request clears previous display metadata')
            fresh=result('2033-01-04','9',[row(540,4),row(900,2),row(930,4),row(960,4)])
            retry.finished.emit({'2033-01-04':cache.make_snapshot('2033-01-04','9',[fresh])})
            window.cache_thread_done()
            events()
            cards=window.results_body.findChildren(ui.TeeTimeCard)
            expect([(c.row['minutes'],c.row['spots']) for c in cards]==[(930,4),(960,4)],'successful cache retry applies corrected group and time filters')
            expect(window.results_body.findChild(QLabel,'SummaryValue').text()=='2 matching times','retry summary agrees with two rendered exact times')
            expect(window.status.text()=='2 matching tee times across 1 course','retry status describes current results')
            expect(window.header_status.text().startswith('SHARED CACHE /'),'retry replaces cancellation header with shared-cache provenance')
            expect(not window.day_sections and not window.results_body.findChildren(ui.DaySection),'single-date success removes old date sections')
            expect(not window.results_body.findChildren(ui.DirectCourseCard),'unselected static course card is removed')
            expect(not any('Availability could not be checked' in text or 'Live times were unavailable' in text for text in labels(window.results_body)),'old missing/provider-error notes do not leak into successful replacement')
            expect(window.context==new_context,'final active context matches corrected submission')
            book=next(b for b in cards[0].findChildren(QPushButton) if b.text()=='BOOK')
            window.results_scroll.ensureWidgetVisible(book)
            book.setFocus()
            QTest.keyClick(book,Qt.Key_Space)
            expect(booking.call_count==2 and booking.call_args.kwargs['context']==new_context,'replacement BOOK uses corrected submitted context')
            expect(booking.call_args.args[1]['minutes']==930,'replacement BOOK dispatches expected filtered row')
            expect(save.call_count==0 and all(path.read_bytes()==data for path,data in originals.items()),'cached completion performs no UI persistence and leaves original bytes unchanged')
            expect(window.cache_thread is None and window.scan_thread is None,'chain ends without worker ownership')
            report['stages'].append({'name':'successful corrected retry','context':serial(window.context),
                'header':window.header_status.text(),'status':window.status.text(),
                'rows':[c.row for c in cards],'booking_callbacks':booking.call_count,'constructed_threads':len(threads)})
            window.grab().save(str(out/'successful-corrected-retry.png'))
            report['completed']=True
        except Exception:
            report['failure']=traceback.format_exc()
        finally:
            if window is not None:
                window._stop_deferred_timers()
                window._cache_cleanup_timer.stop()
                window._scan_cleanup_timer.stop()
                window.cache_thread=window.cache_worker=None
                window.scan_thread=window.scan_worker=None
            for worker in workers:
                if worker is not None:worker.deleteLater()
            cleanup_qt_widgets()
report['source_sha256_after']=hashes()
report['source_unchanged_during_probe']=report['source_sha256_after']==report['source_sha256']
report['summary']={'completed':report.get('completed',False),'recorded_assertions':len(report['assertions']),
                  'failed_assertions':sum(not a['passed'] for a in report['assertions']),
                  'exceptions':int('failure' in report),'callback_errors':len(report['callback_errors'])}
report['limits']='One controlled input chain at980x640. Real Qt mouse/keyboard and workerQObject signals; inertQThread mocks and explicitly simulated completion. Synthetic isolated savedfiles, intercepted persistence/BOOK, blocked network/provider/browser/holds/delivery. No nativeWindows/Android orrealworker timing.'
(out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(bool(report['summary']['exceptions'] or report['summary']['callback_errors'] or not report['source_unchanged_during_probe']))
