"""Malformed cache recovery probe with real isolated files and no network."""
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
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
a=parser.parse_args(); root=a.root.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-cache-shape-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime,XDG_CACHE_HOME=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication,QLabel
    from app import shared_cache as cache
    from app.qt_golfhub_app import GolfHub
    from tests.qt_test_support import cleanup_qt_widgets
    app=QApplication.instance() or QApplication([])
    with ExitStack() as stack:
        for target in ('socket.create_connection','socket.socket.connect','webbrowser.open'):
            stack.enter_context(patch(target,side_effect=AssertionError('Offline QA')))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today',return_value=QDate(2033,1,2)))
        stack.enter_context(patch.object(cache,'LOCAL_CACHE_DIR',Path(runtime)/'cache'))
        stack.enter_context(patch.object(GolfHub,'show_initial_cache'))
        window=GolfHub(); window._stop_deferred_timers()
    # Constructor timer was stopped before removing its method patch.
    with ExitStack() as stack:
        for target in ('socket.create_connection','socket.socket.connect','webbrowser.open'):
            stack.enter_context(patch(target,side_effect=AssertionError('Offline QA')))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today',return_value=QDate(2033,1,2)))
        stack.enter_context(patch.object(cache,'LOCAL_CACHE_DIR',Path(runtime)/'cache'))
        window.date.setDate(QDate(2033,1,2)); window.set_all(False)
        site=next(s for s in window.sites if s.name=='Araluen')
        next(r for r in window.course_rows if r.site.name==site.name).check.setChecked(True)
        good=cache.make_snapshot('2033-01-02','18',[{'site_name':site.name,'url':'https://example.invalid/booking','hole_label':'18 holes','decorated_rows':[],'weather':None,'error':None}])
        cases={'null-result':[None], 'string-result':['bad record'], 'null-row':[dict(good['results'][0],decorated_rows=[None])], 'object-rows':[dict(good['results'][0],decorated_rows={'minutes':540})]}
        evidence=[]
        for name,results in cases.items():
            bad={**good,'results':results}
            path=cache.local_snapshot_path('2033-01-02','18'); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(bad))
            loaded=cache.load_local_snapshot('2033-01-02','18')
            error=None
            with patch.object(window._cache_search_timer,'start') as schedule:
                try: window.show_initial_cache()
                except Exception as exc: error=f'{type(exc).__name__}: {exc}'
            startup={'loaded_invalid_payload':loaded is not None,'exception':error,'scheduled_ms':[c.args[0] for c in schedule.call_args_list]}
            cache.save_local_snapshot(good)
            old_bytes=path.read_bytes()
            response=__import__('io').BytesIO(json.dumps(bad).encode())
            with patch.object(cache,'_cache_base_url',return_value='https://example.invalid/cache'), patch.object(cache.urllib.request,'urlopen',return_value=response):
                fetched=cache.fetch_shared_snapshot('2033-01-02','18')
            evidence.append({'case':name,'startup':startup,'download':{'accepted_invalid_payload':fetched is not None,'valid_saved_bytes_preserved':path.read_bytes()==old_bytes}})
        report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'source_hashes':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in ('app/shared_cache.py','app/qt_golfhub_app.py')},'kind':'Linux offscreen startup methods with isolated real cache files; mocked HTTP bytes and intercepted recovery timer; no network or worker launch','cases':evidence}
        (out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        cleanup_qt_widgets()
