from datetime import datetime, timezone
import hashlib,json,os,platform,re,shutil,signal,subprocess,sys,time
from pathlib import Path
root=Path('/tmp/golfhub-crash-comparison-20261020')
python=Path('/tmp/golfhub-qa-venv/bin/python')
harness=root/'journey-smoke.py'
phase='strict-crash-comparison-20261020'
runtime=Path(f'/tmp/golfhub-smoke-{phase}-runtime')
fontcache=Path(f'/tmp/golfhub-smoke-{phase}-fontcache')
temp=root/'process-temp'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(where,*args):return subprocess.check_output(['git',*args],cwd=where,text=True).strip()
report={'started_utc':datetime.now(timezone.utc).isoformat(),'kind':'Identical committed asynchronous smoke harness; clean exact base/head worktrees; alternating bounded runs','harness_source_commit':'93d4763451358be608bff06fd0013936af36764c','harness_sha256':digest(harness),'python':str(python),'python_realpath':str(python.resolve()),'platform':platform.platform(),'timeout_seconds':25,'phase_identical':phase,'synchronous_cache':False,'retain_worker_wrappers':False,'max_runs_each':3,'worktrees':{},'runs':[]}
env={**os.environ,'QT_QPA_PLATFORM':'offscreen','PYTHONHASHSEED':'0','PYTHONUNBUFFERED':'1','TMP':str(temp),'TEMP':str(temp),'TMPDIR':str(temp)}
report['environment']={k:env.get(k) for k in ['QT_QPA_PLATFORM','QTWEBENGINE_CHROMIUM_FLAGS','QTWEBENGINE_DISABLE_SANDBOX','DISPLAY','WAYLAND_DISPLAY','PYTHONHASHSEED','PYTHONUNBUFFERED','TMP','TEMP','TMPDIR']}
report['runtime_versions']=subprocess.check_output([str(python),'-c','import sys,PySide6; from PySide6.QtCore import qVersion; print(sys.version); print("PySide6",PySide6.__version__,"Qt",qVersion())'],text=True).strip()
for name in ('base','head'):
  where=root/name
  status=git(where,'status','--porcelain')
  assert status=='',(name,status)
  report['worktrees'][name]={'path':str(where),'commit':git(where,'rev-parse','HEAD'),'status_before':status,'app_sha256':digest(where/'app/qt_golfhub_app.py'),'tests_sha256':{p.name:digest(p) for p in sorted((where/'tests').glob('*.py'))}}
def save(): (root/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
save()
for repetition in range(1,4):
  for name in ('base','head'):
    where=root/name
    assert git(where,'status','--porcelain')==''
    # All three paths are created only by this comparison; clear them so each run
    # gets equivalent cold application/font/temp state with identical env paths.
    for path in (runtime,fontcache,temp):
      if path.exists():shutil.rmtree(path)
      path.mkdir(parents=True)
    output=root/f'{name}-{repetition}'
    output.mkdir()
    command=[str(python),'-X','faulthandler',str(harness),'--root',str(where),'--output',str(output),'--phase',phase]
    before=digest(harness)
    record={'tree':name,'repetition':repetition,'command':command,'cwd':str(root),'started_utc':datetime.now(timezone.utc).isoformat(),'worktree_clean_before':True,'harness_sha256':before,'app_sha256':digest(where/'app/qt_golfhub_app.py')}
    started=time.monotonic()
    proc=subprocess.Popen(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:stdout,stderr=proc.communicate(timeout=25)
    except subprocess.TimeoutExpired:
      record['timeout']=True
      record['termination']='SIGABRT sent to owned test process group for faulthandler stack after 25-second limit'
      os.killpg(proc.pid,signal.SIGABRT)
      try:stdout,stderr=proc.communicate(timeout=5)
      except subprocess.TimeoutExpired:
        record['termination']+='; SIGKILL after 5-second cleanup limit'
        os.killpg(proc.pid,signal.SIGKILL)
        stdout,stderr=proc.communicate()
    record['elapsed_seconds']=round(time.monotonic()-started,3)
    record['returncode']=proc.returncode
    log=stdout+stderr
    (output/'process.log').write_text(log)
    record['log']=str(output/'process.log')
    record['harness_unchanged_after']=before==digest(harness)
    record['worktree_clean_after']=git(where,'status','--porcelain')==''
    report_path=output/f'journey-smoke-{phase}.json'
    if report_path.exists():
      smoke=json.loads(report_path.read_text());record['completed_report']=smoke['status'];record['checks']=len(smoke['checks']);record['callback_errors']=smoke['callback_errors']
    crash=log.find('Fatal Python error:')
    if crash!=-1:record['stack']=log[crash:]
    if proc.returncode == -signal.SIGSEGV and 'in cache_thread_done' in log:
      record['signature']='SIGSEGV; Python main thread in cache_thread_done; worker thread has no Python frame'
    elif proc.returncode==0:record['signature']='completed'
    elif record.get('timeout'):record['signature']='timeout; controlled diagnostic abort'
    else:record['signature']=f'other exit {proc.returncode}'
    report['runs'].append(record);save()
    print(json.dumps({k:record.get(k) for k in ('tree','repetition','returncode','elapsed_seconds','checks','signature','log')}),flush=True)
  base={r['signature'] for r in report['runs'] if r['tree']=='base' and r['returncode']==-signal.SIGSEGV}
  head={r['signature'] for r in report['runs'] if r['tree']=='head' and r['returncode']==-signal.SIGSEGV}
  if base&head:
    report['stop_reason']='Same spontaneous SIGSEGV/cache_thread_done signature reproduced on exact clean PR11 base and current head using identical harness/environment; paired comparison is conclusive for presence on baseline, not incidence or native-device impact.'
    break
else:report['stop_reason']='Three bounded alternating runs per tree exhausted; compare outcomes without inferring regression cause.'
report['finished_utc']=datetime.now(timezone.utc).isoformat();save();print(report['stop_reason'],flush=True)
