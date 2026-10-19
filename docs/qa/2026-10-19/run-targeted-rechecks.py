import json, os, pathlib, re, subprocess, sys
root=pathlib.Path('/workspace/golfhub-perth'); out=root/'docs/qa/2026-10-19'
env={**os.environ,'QT_QPA_PLATFORM':'offscreen','LOCALAPPDATA':'/tmp/golfhub-recheck-runtime','XDG_CACHE_HOME':'/tmp/golfhub-font-cache'}
checks=[('test_booking_ui_integration.py',None,root),('test_golfhub_v3.py',None,root),('test_booking_dialog.py','test_booking_dialog.ResultInterpreterTests',root),('test_golfhub_v3.py',None,pathlib.Path('/tmp/golfhub-qa-baseline-20261019')),('test_time_range_ui.py',None,pathlib.Path('/tmp/golfhub-qa-baseline-20261019'))]
results=[]
code='''import json, socket, sys, unittest
from unittest.mock import patch
sys.path[:0]=['.','tests']
def blocked(*args, **kwargs): raise AssertionError('QA networking blocked')
with patch('socket.create_connection', blocked), patch('socket.socket.connect', blocked):
    suite=unittest.defaultTestLoader.loadTestsFromName(sys.argv[2]) if len(sys.argv)>2 else unittest.defaultTestLoader.discover('tests', pattern=sys.argv[1])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    from tests.qt_test_support import cleanup_qt_widgets
    cleanup_qt_widgets()
    print('QA_RESULT',json.dumps({'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}),flush=True)
    sys.exit(not result.wasSuccessful())
'''
for module,klass,cwd in checks:
    cmd=[sys.executable,'-c',code,module]+([klass] if klass else [])
    p=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
    log=p.stdout+p.stderr; phase='baseline' if cwd!=root else 'after'
    name='test-recheck-'+phase+'-'+module.removesuffix('.py')
    (out/(name+'.log')).write_text(log)
    r={'module':module,'class':klass,'phase':phase,'exit_code':p.returncode,'external_fixture_cleanup':True}
    m=re.search(r'QA_RESULT (.+)',log)
    if m:r.update(json.loads(m[1]))
    results.append(r); print(r,flush=True)
(out/'test-rechecks.json').write_text(json.dumps(results,indent=2)+'\n')
