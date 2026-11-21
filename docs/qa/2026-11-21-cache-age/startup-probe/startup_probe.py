"""Actual deferred startup from isolated JSON; no network, workers or persistence."""
import argparse, hashlib, json, os, sys, tempfile, traceback
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args(); root=args.root.resolve(); out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(root))
from PySide6.QtCore import QDate,QTimer
from PySide6.QtWidgets import QApplication,QLabel
from app import shared_cache as cache
from app import qt_golfhub_app as ui
from tests.qt_test_support import cleanup_qt_widgets
class Clock(datetime):
    @classmethod
    def now(cls,tz=None):return datetime(2033,1,2,tzinfo=timezone.utc)
def blocked(*args,**kwargs):raise AssertionError('Offline cache-age probe')
app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False)
cases=[('valid','2033-01-01T23:55:00Z'),('absent',None),('invalid_string','not a timestamp'),('integer',123),('boolean',True),('array',['2033-01-01']),('object',{'timestamp':'2033-01-01'})]
report={'source_root':str(root),'qt_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'cache_sha256':hashlib.sha256((root/'app/shared_cache.py').read_bytes()).hexdigest(),'cases':[]}
from contextlib import ExitStack
for name,stamp in cases:
    case={'name':name,'generated_at':stamp,'callbacks':[]}
    with tempfile.TemporaryDirectory(prefix='golfhub-age-') as tmp, ExitStack() as stack:
        stack.enter_context(patch.object(cache,'LOCAL_CACHE_DIR',Path(tmp)/'cache'))
        stack.enter_context(patch.object(cache,'datetime',Clock))
        stack.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.CacheWorker','app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.fetch_site_result','app.course_results.get_weather_for_date'):
            stack.enter_context(patch(target,side_effect=blocked))
        stack.enter_context(patch.object(sys,'excepthook',side_effect=lambda typ,exc,tb:case['callbacks'].append({'type':typ.__name__,'message':str(exc)})))
        payload={'schema':1,'date':'2033-01-03','holes':'18','generated_at':stamp,'results':[{'site_name':'Araluen','url':'https://example.invalid/booking','hole_label':'18 holes','decorated_rows':[{'time':'9:00 am','minutes':540,'spots':4}],'weather':None,'error':None}]}
        path=cache.local_snapshot_path(payload['date'],payload['holes']);path.parent.mkdir(parents=True);path.write_text(json.dumps(payload));original=path.read_bytes()
        case['accepted_by_loader']=cache.load_local_snapshot(payload['date'],payload['holes'])==payload
        window=ui.GolfHub();schedule=stack.enter_context(patch.object(window._cache_search_timer,'start'));window.show()
        QTimer.singleShot(200,app.quit);app.exec()
        case.update(shared_schedule=[list(call.args) for call in schedule.call_args_list],headline=[label.text() for label in window.findChildren(QLabel) if label.objectName()=='SummaryValue'],header=window.header_status.text(),bytes_unchanged=path.read_bytes()==original,worker_owners_absent=window.cache_thread is None and window.scan_thread is None)
        case['recovery_pass']=not case['callbacks'] and case['shared_schedule']==[[100]] and case['headline']==['1 matching time'] and case['bytes_unchanged'] and case['worker_owners_absent']
        if name in ('valid','integer'):window.grab().save(str(out/(name+'.png')))
        window.close();cleanup_qt_widgets()
    report['cases'].append(case)
report['counts']={'cases':len(cases),'recovery_pass':sum(c['recovery_pass'] for c in report['cases']),'recovery_fail':sum(not c['recovery_pass'] for c in report['cases'])}
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if all(c['recovery_pass'] for c in report['cases']) else 1)
