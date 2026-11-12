import argparse, hashlib, json, os, pathlib, re, subprocess, sys, tempfile
from datetime import datetime, timezone
p=argparse.ArgumentParser(); p.add_argument('--root',type=pathlib.Path,required=True); p.add_argument('--test',type=pathlib.Path,required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
a.output.parent.mkdir(parents=True,exist_ok=True)
code='''import importlib.util,json,sys,unittest
sys.path[:0]=[sys.argv[1],sys.argv[1]+'/tests']
spec=importlib.util.spec_from_file_location('cache_completion_regression',sys.argv[2]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from unittest.mock import patch
def blocked(*a,**kw): raise AssertionError('Offline regression')
with patch('socket.create_connection',blocked), patch('socket.socket.connect',blocked), patch('webbrowser.open',blocked):
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
from tests.qt_test_support import cleanup_qt_widgets
cleanup_qt_widgets()
print('QA_RESULT',json.dumps({'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped)}),flush=True)
sys.exit(not r.wasSuccessful())
'''
with tempfile.TemporaryDirectory(prefix='golfhub-cache-completion-regression-') as runtime:
 env=dict(os.environ,QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
 r=subprocess.run([sys.executable,'-X','faulthandler','-c',code,str(a.root.resolve()),str(a.test.resolve())],cwd=a.root,env=env,capture_output=True,text=True,timeout=60)
log=r.stdout+r.stderr;a.output.with_suffix('.log').write_text(log)
match=re.search(r'QA_RESULT (.+)',log)
report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.root,text=True).strip(),'app_sha256':hashlib.sha256((a.root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(a.test.read_bytes()).hexdigest(),'exit_code':r.returncode,'result':json.loads(match[1]) if match else None}
a.output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));print(log[-6000:]);sys.exit(r.returncode)
