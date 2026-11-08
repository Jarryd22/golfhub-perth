"""Actual course-panel input with intercepted search submission; no workers."""
import argparse
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root,out=args.root.resolve(),args.output.resolve();out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-panel-counts-') as runtime:
 os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime,XDG_CACHE_HOME=runtime)
 from PySide6.QtCore import QDate,Qt
 from PySide6.QtGui import QAccessible
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QPushButton,QScrollArea
 from app import qt_golfhub_app as ui
 from tests.qt_test_support import cleanup_qt_widgets
 app=QApplication.instance() or QApplication([])
 with ExitStack() as stack:
  for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.CacheWorker','app.qt_golfhub_app.fetch_site_result','app.course_results.get_weather_for_date','app.qt_golfhub_app.save_local_snapshot','app.qt_golfhub_app.BookingAssistDialog'):
   stack.enter_context(patch(target,side_effect=AssertionError('Offline count probe')))
  stack.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
  errors=[];stack.enter_context(patch('sys.excepthook',side_effect=lambda *a:errors.append(str(a[1]))))
  information=stack.enter_context(patch.object(ui.QMessageBox,'information'))
  with patch.object(ui.GolfHub,'show_initial_cache'):window=ui.GolfHub()
  window._stop_deferred_timers();window.resize(980,640);window.show();window.activateWindow()
  launch=stack.enter_context(patch.object(window,'_start_cache_search'))
  window.date.set_dates([QDate(2033,1,2)])
  records=[];submissions=[];checks=[]
  def settle():
   for _ in range(5):app.processEvents()
  def selected():return [s.name for s in window.selected_sites()]
  def checked():return [r.site.name for r in window.course_rows if r.check.isChecked()]
  def record(name):
   settle();count=len(selected());interface=QAccessible.queryAccessibleInterface(window.course_button)
   item={'name':name,'round':window.hole_type(),'selected':selected(),'checked':checked(),'selected_count':count,
    'button':window.course_button.text(),'button_accessible_name':interface.text(QAccessible.Name),
    'panel_visible':window.course_panel.isVisible(),'count_label':window.selected_count.text(),'count_label_visible':window.selected_count.isVisible(),
    'query':window.course_search.text(),'visible_courses':[r.site.name for r in window.course_rows if r.isVisible()],
    'pending_count_visible':window.selected_count.isVisible() or window.course_button.text()==f'COURSES  {count} OF {len(window.sites)}'}
   records.append(item);return item
  def toggle(mode):
   before=checked();query=window.course_search.text();visible=window.course_panel.isVisible()
   if mode=='mouse':QTest.mouseClick(window.course_button,Qt.LeftButton)
   else:
    window.course_button.setFocus();settle();assert app.focusWidget() is window.course_button
    QTest.keyClick(app.focusWidget(),Qt.Key_Space)
   settle();assert window.course_panel.isVisible()!=visible;assert checked()==before;assert window.course_search.text()==query
  def submit(name,expected):
   launch.reset_mock();information.reset_mock();QTest.mouseClick(window.search_button,Qt.LeftButton);settle()
   if expected:
    launch.assert_called_once();payload=launch.call_args.args[0]
    assert sorted(s.name for s in payload['sites'])==sorted(expected)
    assert payload['holes']==window.hole_type() and payload['date']=='2033-01-02'
    information.assert_not_called()
    submissions.append({'name':name,'submitted':sorted(s.name for s in payload['sites']),'round':payload['holes'],'date':payload['date'],'no_selection_message':None})
   else:
    launch.assert_not_called();information.assert_called_once()
    submissions.append({'name':name,'submitted':[],'round':window.hole_type(),'date':None,'no_selection_message':information.call_args.args[2]})
  def button(text):return next(b for b in window.course_panel.findChildren(QPushButton) if b.text()==text)
  def query(value):
   window.course_search.setFocus();QTest.keyClick(window.course_search,Qt.Key_A,Qt.ControlModifier);QTest.keyClick(window.course_search,Qt.Key_Backspace)
   QTest.keyClicks(window.course_search,value);settle();assert window.course_search.text()==value
  def checkbox(name):
   row=next(r for r in window.course_rows if r.site.name==name);assert row.isVisible()
   window.course_panel.findChild(QScrollArea).ensureWidgetVisible(row.check);settle();QTest.mouseClick(row.check,Qt.LeftButton);settle()
  settle();many=selected();assert len(many)>1;record('initial_many_closed')
  toggle('mouse');record('many_open_mouse');toggle('space');record('many_closed_space');submit('many',many)
  checks.append('mouse open and Space close preserve many selected courses and submitted sites')
  toggle('space');QTest.mouseClick(button('Clear'),Qt.LeftButton);settle();assert not selected();record('zero_open')
  toggle('mouse');record('zero_closed_mouse');window.grab().save(str(out/'zero-closed.png'));submit('zero',[])
  checks.append('clear and mouse close preserve zero selection; Find gives existing choose-course guidance without launching')
  toggle('mouse');checkbox('Araluen');assert selected()==['Araluen'];record('one_open')
  toggle('space');record('one_closed_space');window.grab().save(str(out/'one-closed.png'));submit('one',['Araluen'])
  checks.append('actual checkbox and Space close preserve one selected course and submitted site')
  toggle('space');checkbox('Altone Park');query('Araluen');assert sorted(selected())==['Altone Park','Araluen']
  assert [r.site.name for r in window.course_rows if r.isVisible()]==['Araluen'];record('hidden_selection_open')
  toggle('mouse');record('hidden_selection_closed_mouse');submit('name_filter_hides_selected_course',['Altone Park','Araluen'])
  checks.append('name-filter-hidden selected course remains selected and submitted after mouse close')
  toggle('mouse');query('no matching course');assert not any(r.isVisible() for r in window.course_rows)
  toggle('space');record('no_matching_names_closed_space');submit('no_matching_names',['Altone Park','Araluen'])
  checks.append('zero visible name matches do not erase selected course count or submission')
  toggle('mouse');QTest.mouseClick(button('Clear'),Qt.LeftButton);query('Araluen');QTest.mouseClick(button('Select visible'),Qt.LeftButton)
  query('Chequers');QTest.mouseClick(button('Select visible'),Qt.LeftButton);settle();assert sorted(selected())==['Araluen','Chequers']
  QTest.mouseClick(window.holes9,Qt.LeftButton);query('Embleton');QTest.mouseClick(button('Select visible'),Qt.LeftButton);settle()
  assert sorted(selected())==['Araluen','Embleton'];assert sorted(checked())==['Araluen','Chequers','Embleton']
  toggle('space');record('nine_holes_closed_space');submit('nine_holes',['Araluen','Embleton'])
  QTest.mouseClick(window.holes18,Qt.LeftButton);settle();record('closed_round_changed_to_eighteen');submit('eighteen_holes',['Araluen','Chequers'])
  toggle('mouse');record('eighteen_reopened');toggle('space');record('eighteen_reclosed_space')
  assert sorted(checked())==['Araluen','Chequers','Embleton']
  checks.append('actual Select visible and 18→9→18 input preserves checked choices and submits only round-eligible courses')
  assert window.scan_thread is None and window.cache_thread is None;assert not errors
  result={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
   'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'records':records,'submissions':submissions,'compatibility_checks_passed':checks,'callback_errors':errors,
   'limits':'Linux Qt offscreen real mouse/Space/checkbox/query/round input; source search_cache params with _start_cache_search intercepted; socket/DNS/provider/weather/browser/persistence/worker/booking blocked; no native device, screen-reader, live query or booking test'}
  (out/'probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));cleanup_qt_widgets()
