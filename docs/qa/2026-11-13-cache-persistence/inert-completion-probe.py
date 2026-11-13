"""Injected outer cache-executor failures; real QObject signals, inert thread/executor."""
import argparse,ast,hashlib,json,os,subprocess,sys,tempfile
from concurrent.futures import Future,as_completed as real_as_completed
from contextlib import ExitStack
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root,out=args.root.resolve(),args.output.resolve();out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-cache-completion-') as runtime:
 os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime,XDG_CACHE_HOME=runtime)
 from PySide6.QtCore import QDate,QObject,Signal
 from PySide6.QtWidgets import QApplication,QLabel
 from app import qt_golfhub_app as ui
 from app import shared_cache as cache
 from tests.qt_test_support import cleanup_qt_widgets
 app=QApplication.instance() or QApplication([])
 class InertThread(QObject):
  started=Signal();finished=Signal()
  def __init__(self):super().__init__();self.running=False;self.quit_calls=0
  def start(self):self.running=True
  def quit(self):self.running=False;self.quit_calls+=1
  def isRunning(self):return self.running
  def wait(self,*a):return not self.running
 dates=['2033-01-02','2033-01-03'];records=[]
 with ExitStack() as guards:
  for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.fetch_shared_snapshot','app.qt_golfhub_app.fetch_site_result','app.course_results.get_weather_for_date','app.qt_golfhub_app.save_local_snapshot','app.qt_golfhub_app.BookingAssistDialog'):
   guards.enter_context(patch(target,side_effect=AssertionError('Offline cache completion probe')))
  guards.enter_context(patch.object(ui,'load_local_snapshot',return_value=None))
  guards.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
  guards.enter_context(patch.object(ui.CacheWorker,'moveToThread'))
  scenarios=['constructor','context_enter','submission','iteration_before_first','iteration_after_one','normal_success','per_future_error','all_futures_error']
  for scenario in scenarios:
   callback_errors=[];finished=[];submitted=[];yielded=[]
   with ExitStack() as case:
    thread=InertThread();case.enter_context(patch.object(ui,'QThread',return_value=thread))
    case.enter_context(patch('sys.excepthook',side_effect=lambda kind,exc,tb:callback_errors.append({'type':kind.__name__,'message':str(exc)})))
    with patch.object(ui.GolfHub,'show_initial_cache'):window=ui.GolfHub()
    window._stop_deferred_timers();window.resize(980,640);window.show();window.set_all(False)
    row=next(r for r in window.course_rows if r.site.name=='Araluen');row.check.setChecked(True)
    window.date.set_dates([QDate.fromString(d,'yyyy-MM-dd') for d in dates])
    payloads={date:cache.make_snapshot(date,'18',[{'site_name':'Araluen','url':f'https://{row.site.domain}',
     'hole_label':'18 holes','error':None,'weather':None,'decorated_rows':[{'time':'9:00 am','minutes':540,'spots':4}]}]) for date in dates}
    class InertPool:
     def __enter__(self):
      if scenario=='context_enter':raise RuntimeError('Synthetic executor context-entry failure')
      return self
     def __exit__(self,*a):return False
     def submit(self,fn,date,holes):
      submitted.append(date)
      if scenario=='submission':raise RuntimeError("Synthetic submission failure: cannot start a new thread")
      future=Future();future.task_date=date
      if scenario=='all_futures_error' or (scenario=='per_future_error' and date==dates[0]):future.set_exception(RuntimeError('Synthetic individual fetch failure'))
      else:future.set_result(payloads[date])
      return future
    def pool_factory(*a,**kw):
     if scenario=='constructor':raise RuntimeError('Synthetic executor construction failure')
     return InertPool()
    def iteration(futures):
     if scenario=='iteration_before_first':raise RuntimeError('Synthetic completion-iteration failure')
     if scenario=='iteration_after_one':
      def partial():
       first=next(iter(futures));yielded.append(first.task_date);yield first
       raise RuntimeError('Synthetic completion-iteration failure after one result')
      return partial()
     return real_as_completed(futures)
    case.enter_context(patch.object(ui,'ThreadPoolExecutor',side_effect=pool_factory))
    case.enter_context(patch.object(ui,'as_completed',side_effect=iteration))
    window.search_cache();worker=window.cache_worker;worker.finished.connect(lambda value:finished.append(value))
    assert window.cache_thread is thread and window.scan_thread is None
    thread.started.emit()
    if thread.quit_calls:thread.finished.emit()
    for _ in range(5):app.processEvents()
    record={'scenario':scenario,'submitted_dates':submitted,'yielded_dates':yielded,'finished_signal_count':len(finished),
     'finished_payloads':[{date:None if payload is None else {'date':payload.get('date'),'result_count':len(payload.get('results',[]))} for date,payload in item.items()} for item in finished],
     'quit_signal_calls':thread.quit_calls,'callback_errors':callback_errors,'header':window.header_status.text(),'status':window.status.text(),
     'labels':[label.text() for label in window.results_body.findChildren(QLabel)],'progress_visible':window.progress.isVisible(),
     'cache_reference_retained':window.cache_thread is not None,'live_button_enabled':window.live_button.isEnabled(),'last_result_count':len(window.last_results)}
    records.append(record)
    if scenario in ('constructor','iteration_after_one','normal_success','all_futures_error'):window.grab().save(str(out/f'{scenario}.png'))
    # There is no native worker to cancel/join. Detach inert references before widget cleanup.
    window.cache_thread=None;window.cache_worker=None;worker.deleteLater();thread.deleteLater();cleanup_qt_widgets()
 source=(root/'app/qt_golfhub_app.py').read_text()
 def cache_run(text):
  tree=ast.parse(text);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CacheWorker')
  return ast.dump(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='run'),include_attributes=False)
 loose=Path('/workspace/golfhub-perth/app/qt_golfhub_app.py')
 report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
  'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'cases':records,
  'loose_cache_run_AST_identical':cache_run(source)==cache_run(loose.read_text()),
  'method':'Linux Qt source controllers and real QObject started/finished signals; inert QThread substitute and executor; prepared futures; every socket/provider/browser/save route blocked. Exceptions are deliberately injected boundary probes, not observed production incidents or native thread timing evidence.'}
 (out/'probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
