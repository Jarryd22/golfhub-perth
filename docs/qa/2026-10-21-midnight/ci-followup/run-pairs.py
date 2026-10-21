import argparse, hashlib, json, os, subprocess, tempfile, time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--python',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
base=Path('/workspace/golfhub-midnight-baseline-20261021');head=Path('/workspace/golfhub-midnight-20261021');test=head/'tests/test_thread_lifecycle.py';out=args.output;out.mkdir(parents=True,exist_ok=True)
assert (base/'tests/test_thread_lifecycle.py').read_bytes()==test.read_bytes()
report={'plan':'10 paired rounds, alternating order; stop after fourth timeout; unchanged cache_close scenario, 30s limit, fresh isolated dirs, retain all outcomes; no retries','python':args.python,'harness_sha256':hashlib.sha256(test.read_bytes()).hexdigest(),'roots':{},'runs':[]}
for label,root in [('base',base),('head',head)]:
 report['roots'][label]={'root':str(root),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'source_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest()}
report['environment']=subprocess.check_output([args.python,'-c','import sys,PySide6;from PySide6.QtCore import qVersion;print(sys.version);print(PySide6.__version__,qVersion())'],text=True)
(out/'results.json').write_text(json.dumps(report,indent=2))
timeouts=0
for pair in range(1,11):
 order=[('base',base),('head',head)] if pair%2 else [('head',head),('base',base)]
 for label,root in order:
  with tempfile.TemporaryDirectory(prefix='golfhub-ci-close-') as runtime:
   env=dict(os.environ,QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,XDG_CACHE_HOME=runtime,TMP=runtime,TEMP=runtime,PYTHONUNBUFFERED='1')
   command=[args.python,'-X','faulthandler',str(test),'--scenario','cache_close','--root',str(root)]
   entry={'pair':pair,'label':label,'command':command};start=time.monotonic()
   try:
    r=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=30);entry['exit_code']=r.returncode;log=r.stdout+r.stderr
    results=[l for l in r.stdout.splitlines() if l.startswith('LIFECYCLE_RESULT ')]
    entry['pass']=r.returncode==0 and len(results)==1
    if len(results)==1:entry['result']=json.loads(results[0].split(' ',1)[1])
   except subprocess.TimeoutExpired as e:
    timeouts+=1;entry.update(timeout=True,passed=False)
    log=(e.stdout.decode(errors='replace') if isinstance(e.stdout,bytes) else e.stdout or '')+(e.stderr.decode(errors='replace') if isinstance(e.stderr,bytes) else e.stderr or '')
   entry['seconds']=round(time.monotonic()-start,3);entry['log']=f'{pair:02d}-{label}.log';(out/entry['log']).write_text(log)
   report['runs'].append(entry);(out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(entry),flush=True)
  if timeouts>3:break
 if timeouts>3:
  report['stop_reason']='Predeclared four-timeout cap reached';break
report['counts']={label:{'runs':len([r for r in report['runs'] if r['label']==label]),'passed':len([r for r in report['runs'] if r['label']==label and r.get('pass')]),'timeouts':len([r for r in report['runs'] if r['label']==label and r.get('timeout')])} for label in ['base','head']}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['counts']),flush=True)
