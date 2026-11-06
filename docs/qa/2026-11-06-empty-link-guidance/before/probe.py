"""Configured integrated-course filter exclusion and conditional link guidance."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('/workspace/golfhub-20261105'));parser.add_argument('--output',type=Path,default=Path('/workspace/scratch/golfhub-20261106-empty-links'))
args=parser.parse_args();root,out=args.root.resolve(),args.output.resolve();out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-empty-links-') as runtime:
 os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
 from PySide6.QtCore import QDate
 from PySide6.QtWidgets import QApplication,QLabel,QPushButton
 from app import qt_golfhub_app as ui
 from app import shared_cache as cache
 from tests.qt_test_support import cleanup_qt_widgets
 app=QApplication.instance() or QApplication([])
 with ExitStack() as stack:
  for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.CacheWorker','app.course_results.get_weather_for_date','app.qt_golfhub_app.save_local_snapshot'):
   stack.enter_context(patch(target,side_effect=AssertionError('Offline configured render probe')))
  stack.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
  errors=[];stack.enter_context(patch('sys.excepthook',side_effect=lambda *a:errors.append(str(a[1]))))
  with patch.object(ui.GolfHub,'show_initial_cache'):window=ui.GolfHub()
  window._stop_deferred_timers();window.resize(980,640);window.show()
  sites={site.name:site for site in window.sites};date='2033-01-02';records=[]
  cases=[('integrated_group_exclusion',['Araluen'],'4',True),('mixed_group_exclusion',['Araluen','Altone Park'],'4',True),('integrated_checked_empty',['Araluen'],'Any',False),('integrated_positive',['Araluen'],'1',True)]
  for name,names,players,has_row in cases:
   window.set_all(False)
   for row in window.course_rows:row.check.setChecked(row.site.name in names)
   window.date.set_dates([QDate(2033,1,2)]);window.players.setCurrentText(players)
   window.context=window.params();window._active_cache_context=window._snapshot_search_context(window.context)
   result={'site_name':'Araluen','url':f'https://{sites["Araluen"].domain}/guests/bookings/ViewPublicTimesheet.msp?selectedDate={date}',
    'hole_label':'18 holes','error':None,'weather':None,'decorated_rows':[{'time':'9:00 am','minutes':540,'spots':2}] if has_row else []}
   window.cache_finished({date:cache.make_snapshot(date,'18',[result])})
   for _ in range(3):app.processEvents()
   records.append({'name':name,'selected':names,'players':players,'source_rows':len(result['decorated_rows']),
    'filtered_rows':len(window.filtered_rows(result['decorated_rows'])),'labels':[l.text() for l in window.results_body.findChildren(QLabel)],
    'result_cards':len(window.results_body.findChildren(ui.ResultCard)),
    'direct_cards':len(window.results_body.findChildren(ui.DirectCourseCard)),
    'action_buttons':[{'text':b.text(),'accessible':b.accessibleName()} for b in window.results_body.findChildren(QPushButton)]})
   window.grab().save(str(out/f'{name}.png'))
  report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
   'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'cases':records,'callbacks':errors,
   'method':'Configured Araluen/Altone; synthetic successful cached rows through actual cache_finished/render_snapshot; real control params and player filtering; socket/DNS/worker/provider/weather/browser/save blocked; Linux offscreen only'}
  (out/'probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));cleanup_qt_widgets()
