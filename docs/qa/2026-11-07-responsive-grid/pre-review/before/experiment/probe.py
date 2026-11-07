"""Bounded result/show-all/booking and resize-history source-widget diagnostic."""
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
root=Path('/workspace/golfhub-20261106');out=Path('/workspace/scratch/golfhub-20261107-results/experiment')
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-nov07-results-') as runtime:
 os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
 from PySide6.QtCore import QDate,Qt,QPoint,QRect
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QPushButton
 from app import qt_golfhub_app as ui
 from tests.qt_test_support import cleanup_qt_widgets
 app=QApplication.instance() or QApplication([]);errors=[]
 with ExitStack() as stack:
  for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo','app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.CacheWorker','app.qt_golfhub_app.fetch_site_result','app.course_results.get_weather_for_date','app.qt_golfhub_app.save_local_snapshot','app.qt_golfhub_app.BookingAssistDialog'):
   stack.enter_context(patch(target,side_effect=AssertionError('Offline diagnostic')))
  browser=stack.enter_context(patch('webbrowser.open',return_value=True))
  stack.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
  stack.enter_context(patch('sys.excepthook',side_effect=lambda *a:errors.append(str(a[1]))))
  def settle():
   for _ in range(8):app.processEvents()
  def make(width,open_panel=False):
   with patch.object(ui.GolfHub,'show_initial_cache'):window=ui.GolfHub()
   window._stop_deferred_timers();window.resize(width,800);window.show();settle()
   if open_panel:window.course_button.click();settle()
   window.set_all(False)
   next(r for r in window.course_rows if r.site.name=='Araluen').check.setChecked(True)
   site=next(s for s in window.sites if s.name=='Araluen')
   window.date.set_dates([QDate(2033,1,2)]);window.players.setCurrentText('Any');window.context=window.params()
   url=f'https://{site.domain}/guests/bookings/ViewPublicTimesheet.msp?selectedDate=2033-01-02'
   rows=[{'time':f'{(540+10*i)//60%12 or 12}:{(540+10*i)%60:02d} am','minutes':540+10*i,'spots':4,'source_url':url+f'&syntheticRow={i}'} for i in range(15)]
   result={'site_name':site.name,'url':url,'hole_label':'18 holes','decorated_rows':rows,'error':None,'weather':None}
   window.render_results([result],'Synthetic saved results');settle()
   return window,window.results_body.findChild(ui.ResultCard),rows
  def state(window,card):
   grid=card.tee_grid;layout=grid.grid
   items=[]
   for i in range(layout.count()):
    widget=layout.itemAt(i).widget();r,c,rs,cs=layout.getItemPosition(i)
    items.append({'row':r,'column':c,'rect':[widget.x(),widget.y(),widget.width(),widget.height()]})
   active_columns=max((item['column'] for item in items),default=-1)+1
   return {'window':[window.width(),window.height()],'panel_visible':window.course_panel.isVisible(),'grid':[grid.width(),grid.height()],
    'visible_rows':sum(not w.isHidden() for w in grid.widgets),'active_columns':active_columns,'layout_columns':layout.columnCount(),
    'stretches':[layout.columnStretch(c) for c in range(layout.columnCount())],
    'column_widths':[layout.cellRect(0,c).width() for c in range(layout.columnCount())],
    'first_row':[i for i in items if i['row']==0],'toggle_text':card.more_button.text(),'toggle_accessible':card.more_button.accessibleName()}
  window,card,rows=make(1500)
  checks=[];states={'initial_wide':state(window,card)}
  assert states['initial_wide']['visible_rows']==12
  checks.append('initial shows first12')
  window.results_scroll.ensureWidgetVisible(card.more_button);settle();QTest.mouseClick(card.more_button,Qt.LeftButton);settle()
  states['expanded_wide']=state(window,card);assert states['expanded_wide']['visible_rows']==15
  checks.append('actual show-all click exposes all15')
  book=next(b for b in card.tee_grid.widgets[14].findChildren(QPushButton) if b.text()=='BOOK')
  window.results_scroll.ensureWidgetVisible(book);settle();QTest.mouseClick(book,Qt.LeftButton);settle()
  browser.assert_called_once_with(rows[14]['source_url']);checks.append('15th-row BOOK preserves row URL with browser intercepted')
  window.results_scroll.ensureWidgetVisible(card.more_button);settle();QTest.mouseClick(card.more_button,Qt.LeftButton);settle()
  assert state(window,card)['visible_rows']==12;checks.append('collapse restores first12')
  window.resize(1100,800);window.course_button.click();settle()
  states['wide_then_narrow']=state(window,card)
  window.results_scroll.verticalScrollBar().setValue(0);settle();window.grab().save(str(out/'wide-then-narrow.png'))
  # Probe-only mutation: reset obsolete stretch; application source remains untouched.
  active=states['wide_then_narrow']['active_columns']
  for column in range(card.tee_grid.grid.columnCount()):card.tee_grid.grid.setColumnStretch(column,1 if column<active else 0)
  card.tee_grid.grid.activate();settle()
  states['probe_only_obsolete_stretch_reset']=state(window,card)
  window.grab().save(str(out/'probe-only-reset.png'))
  fresh,fresh_card,_=make(1100,open_panel=True)
  states['fresh_narrow']=state(fresh,fresh_card)
  fresh.grab().save(str(out/'fresh-narrow.png'))
  record={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
   'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'experiment':'Only in-memory QGridLayout.columnStretch values changed after baseline observation; no application source edit or fixed-source claim','checks_passed':checks,'states':states,'callbacks':errors,
   'limits':'Synthetic configured Araluen data, Linux offscreen; no native workers/providers/persistence/browser navigation/holds. Resize geometry is layout observation, not native-device clipping evidence.'}
  (out/'probe.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2));cleanup_qt_widgets()
