from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

root=Path('/workspace/golfhub-20261027')
out=Path('/tmp/golfhub-oct28-gap-evidence'); out.mkdir(exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-oct28-gaps-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
    from PySide6.QtWidgets import QApplication,QLabel
    from app.qt_golfhub_app import GolfHub,ResultCard,TeeTimeCard
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    errors=[]
    with ExitStack() as stack:
        for target in ('socket.create_connection','socket.socket.connect','webbrowser.open'):
            stack.enter_context(patch(target,side_effect=AssertionError('Offline read-only probe')))
        stack.enter_context(patch.object(GolfHub,'show_initial_cache'))
        stack.enter_context(patch('sys.excepthook',side_effect=lambda *a:errors.append(str(a[1]))))
        w=GolfHub();w._stop_deferred_timers();w.resize(1280,800);w.show();app.processEvents()
        araluen=next(s for s in w.sites if s.name=='Araluen')
        wembley=next(s for s in w.sites if s.name=='Wembley')
        collier=next(s for s in w.sites if s.name=='Collier Park')
        dates=['2030-01-02','2030-01-03']
        def context(sites):
            return dict(sites=sites,date=dates[0],dates=dates,holes='18',players=None,**{'from':None,'to':None})
        def result(site,rows=(),**extra):
            return dict(site_name=site.name,url='https://example.invalid/booking',hole_label='18 holes',decorated_rows=list(rows),weather=None,error=None,**extra)
        row={'time':'9:00 am','minutes':540,'spots':4}
        evidence={}
        for calendar in ('available','unreleased','full'):
            w.context=context([araluen,wembley])
            w.render_results([result(araluen,[row]),result(wembley,calendar_availability=calendar)],'Synthetic cache')
            app.processEvents()
            evidence['one-row-plus-calendar-'+calendar]={
                'status':w.status.text(),'summary':w.findChild(QLabel,'SummaryValue').text(),
                'tee_time_cards':len(w.findChildren(TeeTimeCard)),
                'courses_with_time_cards':sorted(set(c.result['site_name'] for c in w.findChildren(ResultCard) if c.findChildren(TeeTimeCard))),
            }
            if calendar=='full':w.grab().save(str(out/'one-time-plus-full-calendar.png'))
        w.context=context([araluen])
        error_result=result(araluen);error_result['error']='Offline synthetic failure'
        w.render_results([error_result],'Synthetic cache')
        evidence['single-error']={'status':w.status.text(),'summary':w.findChild(QLabel,'SummaryValue').text(),
                                 'labels':[l.text() for l in w.results_body.findChildren(QLabel)]}
        w.render_multi_results([{'date':d,'available':True,'results':[error_result],'source':'Synthetic loaded cache'} for d in dates],'2 of 2 dates loaded')
        evidence['multi-error']={'status':w.status.text(),'summary':w.findChild(QLabel,'SummaryValue').text(),
                                'day_titles':[s.toggle.text() for s in w.day_sections],
                                'day_built':[s._built for s in w.day_sections]}
        w.context=context([collier]); cr=result(collier);cr['error']='Offline synthetic failure'
        w.render_results([cr],'Synthetic cache')
        evidence['collier-error']={'labels':[l.text() for l in w.results_body.findChildren(QLabel)]}
        evidence['callback_errors']=errors
        evidence['kind']='Exact PR16 source, Linux offscreen, synthetic render only, socket/browser blocked, no workers/provider calls'
        (out/'probe.json').write_text(json.dumps(evidence,indent=2)+'\n')
        print(json.dumps(evidence,indent=2))
        cleanup_qt_widgets()
        assert not errors
