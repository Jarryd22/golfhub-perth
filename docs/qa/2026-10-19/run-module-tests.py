import json, os, pathlib, re, subprocess, sys
root=pathlib.Path('/workspace/golfhub-perth')
out=root/'docs/qa/2026-10-19'
env={**os.environ,'QT_QPA_PLATFORM':'offscreen','QTWEBENGINE_CHROMIUM_FLAGS':'--disable-gpu','LOCALAPPDATA':'/tmp/golfhub-broad-runtime','XDG_CACHE_HOME':'/tmp/golfhub-font-cache'}
summary=[]
for path in sorted((root/'tests').glob('test_*.py')):
    code='''import socket, sys, unittest
from unittest.mock import patch
sys.path.insert(0, '.')
def blocked(*args, **kwargs): raise AssertionError('QA networking blocked')
with patch('socket.create_connection', blocked), patch('socket.socket.connect', blocked):
    suite=unittest.defaultTestLoader.discover('tests', pattern=sys.argv[1])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print('QA_RESULT', __import__('json').dumps({'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}), flush=True)
    sys.exit(not result.wasSuccessful())
'''
    try:
        p=subprocess.run([sys.executable,'-c',code,path.name],cwd=root,env=env,capture_output=True,text=True,timeout=90)
        log=p.stdout+p.stderr
        result={'module':path.name,'exit_code':p.returncode}
        m=re.search(r'QA_RESULT (.+)',log)
        if m: result.update(json.loads(m[1]))
        else: result['status']='process did not complete unittest'
    except subprocess.TimeoutExpired as e:
        log=str(e.stdout)+str(e.stderr); result={'module':path.name,'status':'timeout'}
    (out/('test-'+path.stem.removeprefix('test_')+'.log')).write_text(log)
    summary.append(result)
    print(result,flush=True)
    (out/'test-summary-initial.json').write_text(json.dumps(summary,indent=2)+'\n')
