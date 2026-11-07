from pathlib import Path
import os,tempfile,sys,json,subprocess,hashlib
from contextlib import ExitStack
from unittest.mock import patch
from datetime import datetime,timezone
root=Path('/workspace/golfhub-20261106');out=Path('/workspace/scratch/golfhub-20261107-course-panel')
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-course-panel-') as runtime:
 os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime,XDG_CACHE_HOME=runtime)
 from PySide6.QtWidgets import QApplication,QLabel
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app import qt_golfhub_app as ui
 from tests.qt_test_support import cleanup_qt_widgets
 app=QApplication.instance() or QApplication([])
 with ExitStack() as stack:
  for target in ['socket.create_connection','socket.socket.connect','socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.CacheWorker','app.qt_golfhub_app.save_local_snapshot']:
   stack.enter_context(patch(target,side_effect=AssertionError('Offline course-panel probe')))
  errors=[];stack.enter_context(patch('sys.excepthook',side_effect=lambda *a:errors.append(str(a[1]))))
  with patch.object(ui.GolfHub,'show_initial_cache'):w=ui.GolfHub()
  w._stop_deferred_timers();w.resize(980,640);w.show();app.processEvents();records=[]
  def record(name):
   app.processEvents();records.append({'name':name,'selected':[s.name for s in w.selected_sites()],'button':w.course_button.text(),'button_accessible_name':w.course_button.accessibleName(),'panel_visible':w.course_panel.isVisible(),'count_text':w.selected_count.text(),'count_visible':w.selected_count.isVisible()})
  record('initial_closed');QTest.mouseClick(w.course_button,Qt.LeftButton);record('opened')
  w.set_all(False);next(r for r in w.course_rows if r.site.name=='Araluen').check.setChecked(True);record('one_selected')
  QTest.mouseClick(w.course_button,Qt.LeftButton);record('closed_one_selected');w.grab().save(str(out/'closed-one-selected.png'))
  QTest.mouseClick(w.course_button,Qt.LeftButton);w.set_all(False);QTest.mouseClick(w.course_button,Qt.LeftButton);record('closed_none_selected')
  (out/'probe.json').write_text(json.dumps({'timestamp_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'cases':records,'callback_errors':errors,'scope':'Linux offscreen actual source widgets; no native/device/provider behavior'},indent=2)+'\n');print(json.dumps(records));cleanup_qt_widgets();assert not errors
