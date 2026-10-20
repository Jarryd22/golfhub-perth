from contextlib import ExitStack
import argparse,json,os,sys,time,traceback
from pathlib import Path
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--mode',choices=['cache','scan'],required=True);p.add_argument('--output',required=True);args=p.parse_args()
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['LOCALAPPDATA']='/tmp/golfhub-thread-probe-runtime';os.environ['XDG_CACHE_HOME']='/tmp/golfhub-thread-probe-fontcache'
sys.path.insert(0,args.root)
from PySide6.QtCore import QTimer,QThread
from PySide6.QtWidgets import QApplication
from app.qt_golfhub_app import GolfHub,ResultCard,ScanWorker
from tests.qt_test_support import cleanup_qt_widgets
app=QApplication([]);report={'kind':'Real QApplication.exec event loop and real app workers, synthetic data, blocked sockets','mode':args.mode,'root':args.root,'checks':[],'callback_errors':[]};code=1
with ExitStack() as st:
 st.enter_context(patch('socket.create_connection',side_effect=AssertionError('blocked')));st.enter_context(patch('socket.socket.connect',side_effect=AssertionError('blocked')));st.enter_context(patch('webbrowser.open',side_effect=AssertionError('blocked')));st.enter_context(patch.object(GolfHub,'show_initial_cache'));st.enter_context(patch('app.qt_golfhub_app.load_local_snapshot',return_value=None));st.enter_context(patch('app.qt_golfhub_app.save_local_snapshot'))
 st.enter_context(patch('sys.excepthook',side_effect=lambda t,e,tb:report['callback_errors'].append(''.join(traceback.format_exception(t,e,tb)))))
 w=GolfHub();w._stop_deferred_timers();w.set_all(False);row=next(r for r in w.course_rows if r.site.provider=='miclub');row.check.setChecked(True);w.show()
 def result(site,date,holes):return {'site_name':site.name,'url':site.build_url(date,holes),'hole_label':f'{holes} holes','weather':None,'error':None,'decorated_rows':[{'time':'9:00 am','minutes':540,'spots':4,'source_url':site.build_url(date,holes)}]}
 st.enter_context(patch('app.qt_golfhub_app.fetch_shared_snapshot',side_effect=lambda date,holes:{'schema':1,'date':date,'holes':holes,'generated_at':'2026-10-20T00:00:00+00:00','results':[result(row.site,date,holes)]}))
 st.enter_context(patch.object(ScanWorker,'_fetch',side_effect=lambda site:result(site,w.selected_dates()[0],w.hole_type())))
 def finish(status):
  global code
  report['status']=status;code=0 if status=='passed' and not report['callback_errors'] else 1
  print(json.dumps(report),flush=True);Path(args.output).write_text(json.dumps(report,indent=2)+'\n');w.close();app.quit()
 count=0
 def poll():
  global count
  thread=getattr(w,args.mode+'_thread')
  if thread is not None:QTimer.singleShot(5,poll);return
  report['checks'].append({'iteration':count,'result_cards':len(w.findChildren(ResultCard)),'status':w.header_status.text(),'in_gui_thread':QThread.currentThread()==app.thread()})
  if len(w.findChildren(ResultCard))!=1:finish('failed');return
  if count==5:finish('passed')
  else:QTimer.singleShot(0,submit)
 def submit():
  global count
  count+=1
  if args.mode=='cache':w.search_cache()
  else:w.search_live()
  QTimer.singleShot(5,poll)
 QTimer.singleShot(0,submit);QTimer.singleShot(8000,lambda:finish('timeout'))
 app.exec()
 cleanup_qt_widgets()
sys.exit(code)
