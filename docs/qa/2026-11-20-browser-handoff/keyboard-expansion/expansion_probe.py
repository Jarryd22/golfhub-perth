"""Actual Space/Tab/ShiftTab over lazy result sections; booking intercepted."""
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
args=parser.parse_args()
root,out=args.root.resolve(),args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
report={'utc':datetime.now(timezone.utc).isoformat(),'source_root':str(root),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'cases':[],'callback_errors':[]}
with tempfile.TemporaryDirectory(prefix='golfhub-expansion-') as temp:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=temp,TEMP=temp,TMP=temp,XDG_CACHE_HOME=temp)
    from PySide6.QtCore import QDate,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QPushButton
    from app import qt_golfhub_app as ui
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    with ExitStack() as guards:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo',
                       'webbrowser.open','app.qt_golfhub_app.fetch_site_result','app.qt_golfhub_app.fetch_shared_snapshot',
                       'app.course_results.get_weather_for_date','app.qt_golfhub_app.BookingAssistDialog',
                       'app.qt_golfhub_app.save_local_snapshot','app.qt_golfhub_app.CacheWorker','app.qt_golfhub_app.ScanWorker'):
            guards.enter_context(patch(target,side_effect=AssertionError('Offline expansion probe')))
        guards.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        guards.enter_context(patch('sys.excepthook',side_effect=lambda kind,value,_tb:
            report['callback_errors'].append({'type':kind.__name__,'message':str(value)})))
        def events():
            for _ in range(4):app.processEvents()
        def serial(context):
            return {**{k:v for k,v in context.items() if k!='sites'},'sites':[s.name for s in context.get('sites',[])]}
        def key(widget,keycode,modifier=Qt.NoModifier):
            QTest.keyClick(widget,keycode,modifier)
            events()
        def button(card):
            return next(b for b in card.findChildren(QPushButton) if b.text()=='BOOK')
        def identity(widget):
            return {'class':type(widget).__name__,'text':widget.text() if hasattr(widget,'text') else '',
                    'accessible_name':widget.accessibleName(),'visible':widget.isVisible()}
        def result(date,n):
            rows=[]
            for i in range(n):
                minute=420+i*15
                hour,minutes=divmod(minute,60)
                rows.append({'time':f'{hour%12 or 12}:{minutes:02d} '+('am' if hour<12 else 'pm'),
                             'minutes':minute,'spots':4,'source_url':f'https://example.invalid/{date}/{i}'})
            return {'site_name':'Araluen','url':f'https://example.invalid/{date}','hole_label':'18 holes',
                    'decorated_rows':rows,'weather':None,'error':None}
        for width,height in ((980,640),(1280,800)):
            record={'viewport':[width,height],'assertions':[],'focus_traces':[]}
            report['cases'].append(record)
            def expect(condition,name):
                record['assertions'].append({'name':name,'passed':bool(condition)})
                assert condition,name
            def tab_until(target,limit=80):
                trace=[]
                for _ in range(limit):
                    focused=QApplication.focusWidget()
                    assert focused is not None,'tab traversal lost focus'
                    key(focused,Qt.Key_Tab)
                    focused=QApplication.focusWidget()
                    assert focused is not None,'tab traversal lost focus after Tab'
                    trace.append(identity(focused))
                    if focused is target:break
                record['focus_traces'].append(trace)
                expect(QApplication.focusWidget() is target,'target reached using bounded Tab sequence')
                expect(all(x['visible'] for x in trace),'Tab focus never lands on a hidden widget')
                return trace
            window=None
            try:
                with patch.object(ui.GolfHub,'show_initial_cache'):
                    window=ui.GolfHub()
                window._stop_deferred_timers()
                window.resize(width,height)
                window.show()
                window.set_all(False)
                next(r for r in window.course_rows if r.site.name=='Araluen').check.setChecked(True)
                window.date.set_dates([QDate(2033,1,2),QDate(2033,1,3)])
                window.players.setCurrentText('4')
                window.context=window.params()
                submitted=dict(window.context)
                results=[result('2033-01-02',15),result('2033-01-03',14)]
                with patch.object(window,'open_tee_time') as booking:
                    window.render_multi_results([
                        {'date':'2033-01-02','source':'Synthetic shared cache','results':[results[0]]},
                        {'date':'2033-01-03','source':'Synthetic shared cache','results':[results[1]]}],
                        '2 of 2 dates loaded')
                    events()
                    first,second=window.day_sections
                    expect(first.toggle.isChecked() and first.body.isVisible(),'first matching day starts open')
                    expect(not second.toggle.isChecked() and not second.findChildren(ui.ResultCard),'second day has no eager course cards')
                    first_card=first.findChild(ui.ResultCard)
                    first_rows=first_card.tee_grid.widgets
                    expect(len(first_rows)==15 and sum(not x.isHidden() for x in first_rows)==12,'first course initially exposes twelve of fifteen rows')
                    first.toggle.setFocus()
                    trace=tab_until(first_card.more_button)
                    book_trace=[x for x in trace if x['text']=='BOOK']
                    expect(len(book_trace)==12,'collapsed course exposes exactly twelve BOOK stops')
                    expect(all('2 January 2033' in x['accessible_name'] for x in book_trace),'visible BOOK focus identifies displayed first date')
                    key(first_card.more_button,Qt.Key_Space)
                    expect(first_card.expanded and sum(not x.isHidden() for x in first_rows)==15,'Space expands all fifteen rows')
                    expect(first_card.more_button.text()=='SHOW FIRST 12','expanded action offers first twelve')
                    expect('Araluen' in first_card.more_button.accessibleName() and '2 January 2033' in first_card.more_button.accessibleName(),'expanded action retains course/date accessibility context')
                    key(first_card.more_button,Qt.Key_Tab,Qt.ShiftModifier)
                    expect(QApplication.focusWidget() is button(first_rows[-1]),'ShiftTab reaches the newly revealed last BOOK')
                    key(QApplication.focusWidget(),Qt.Key_Space)
                    expect(booking.call_count==1 and booking.call_args.args==(results[0],results[0]['decorated_rows'][-1]),'keyboard last-row BOOK dispatches exact displayed row')
                    expect(booking.call_args.kwargs['context']==submitted,'first BOOK uses submitted context')
                    key(QApplication.focusWidget(),Qt.Key_Tab)
                    expect(QApplication.focusWidget() is first_card.more_button,'Tab returns from last BOOK to collapse action')
                    key(first_card.more_button,Qt.Key_Space)
                    expect(not first_card.expanded and sum(not x.isHidden() for x in first_rows)==12,'Space collapses back to first twelve')
                    expect(QApplication.focusWidget() is first_card.more_button,'collapse retains focus on activating action')
                    key(first_card.more_button,Qt.Key_Tab,Qt.ShiftModifier)
                    expect(QApplication.focusWidget() is button(first_rows[11]),'collapsed ShiftTab skips hidden rows thirteen through fifteen')
                    first.toggle.setFocus()
                    key(first.toggle,Qt.Key_Space)
                    expect(not first.body.isVisible(),'Space collapses the whole first date')
                    trace=tab_until(second.toggle)
                    expect(not any(x['text']=='BOOK' for x in trace),'collapsed date contributes no BOOK focus stops')
                    key(second.toggle,Qt.Key_Space)
                    second_card=second.findChild(ui.ResultCard)
                    expect(second.body.isVisible() and second_card is not None,'Space builds and opens lazy second date')
                    second_rows=second_card.tee_grid.widgets
                    identities=[id(x) for x in second_rows]
                    expect(len(second_rows)==14 and sum(not x.isHidden() for x in second_rows)==12,'lazy course initially exposes twelve of fourteen')
                    trace=tab_until(second_card.more_button)
                    expect(len([x for x in trace if x['text']=='BOOK'])==12,'new lazy course is keyboard reachable through twelve BOOK stops')
                    key(second_card.more_button,Qt.Key_Space)
                    expect(sum(not x.isHidden() for x in second_rows)==14,'lazy SHOW ALL exposes fourteen rows')
                    # Pending controls change without changing the submitted result context.
                    window.date.set_dates([QDate(2033,1,5)])
                    window.holes9.setChecked(True)
                    window.players.setCurrentText('1')
                    window.time_preset.setCurrentText('Afternoon')
                    key(second_card.more_button,Qt.Key_Tab,Qt.ShiftModifier)
                    expect(QApplication.focusWidget() is button(second_rows[-1]),'expanded lazy last BOOK reachable by ShiftTab')
                    key(QApplication.focusWidget(),Qt.Key_Space)
                    expect(booking.call_count==2 and booking.call_args.args==(results[1],results[1]['decorated_rows'][-1]),'lazy keyboard BOOK dispatches its exact final row once')
                    expect(booking.call_args.kwargs['context']==submitted,'lazy keyboard BOOK preserves submitted group/date/round after pending edits')
                    expect('3 January 2033' in QApplication.focusWidget().accessibleName(),'lazy BOOK accessible name retains its displayed date')
                    second.toggle.setFocus()
                    for cycle in range(3):
                        key(second.toggle,Qt.Key_Space)
                        expect(not second.body.isVisible(),f'cycle{cycle+1}: keyboard closes lazy date')
                        key(second.toggle,Qt.Key_Space)
                        expect(second.body.isVisible(),f'cycle{cycle+1}: keyboard reopens lazy date')
                        expect(len(second.findChildren(ui.ResultCard))==1 and [id(x) for x in second_card.tee_grid.widgets]==identities,
                               f'cycle{cycle+1}: reopening reuses single course and original rows')
                    expect(second_card.expanded and sum(not x.isHidden() for x in second_rows)==14,'date collapse/reopen preserves local SHOW ALL state')
                    key(second.toggle,Qt.Key_Tab)
                    expect(QApplication.focusWidget().text()=='OPEN BOOKING PAGE','reopened date begins with its official-page action')
                    second_card.more_button.setFocus()
                    window.results_scroll.ensureWidgetVisible(second_card.more_button)
                    events()
                    window.grab().save(str(out/f'expanded-{width}x{height}.png'))
                    record['submitted']=serial(submitted)
                    record['pending']=serial(window.params())
                    record['row_counts']={'first_total':len(first_rows),'second_total':len(second_rows),
                        'first_hidden_date':not first.body.isVisible(),'second_visible_rows':sum(x.isVisible() for x in second_rows)}
                    record['booking_callback_count']=booking.call_count
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
report['limits']='Real Qt keyboard events after explicitly anchored focus; synthetic two-date results. No screen reader/native device, network/provider/weather/browser, booking plan/hold/delivery, realworker or persistence execution. BOOK intercepted before handler implementation. Counts are diagnostic assertions, not new unittest methods.'
(out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary']),flush=True)
sys.exit(bool(report['summary']['exceptions'] or report['summary']['callback_errors']))
