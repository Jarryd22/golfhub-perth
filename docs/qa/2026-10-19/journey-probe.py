from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
import argparse, collections, hashlib, json, os, platform, sys, traceback
p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--phase',required=True); p.add_argument('--output',required=True); a=p.parse_args()
root=Path(a.root); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ['LOCALAPPDATA']=f'/tmp/golfhub-journey-{a.phase}-runtime'; os.environ['XDG_CACHE_HOME']=f'/tmp/golfhub-journey-{a.phase}-fontcache'
sys.path.insert(0,str(root))
import PySide6
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication,QLabel,QPushButton
from PySide6.QtTest import QTest
from app.qt_golfhub_app import GolfHub,ResultCard,WeatherBadge,APP_VERSION
from app.course_results import direct_result
app=QApplication([])
errors=[]
def hook(kind,value,tb): errors.append(''.join(traceback.format_exception(kind,value,tb)))
def names(w):
  i=QAccessible.queryAccessibleInterface(w)
  return {'property':w.accessibleName(),'interface_name':i.text(QAccessible.Name),'interface_value':i.text(QAccessible.Value)}
report={'source_app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),'phase':a.phase,'kind':'Linux real Qt offscreen source-widget interaction with synthetic data and blocked sockets','python':platform.python_version(),'platform':platform.platform(),'pyside':PySide6.__version__,'app_version':APP_VERSION,'timestamp_utc':datetime.now(timezone.utc).isoformat()}
with ExitStack() as st:
 st.enter_context(patch('sys.excepthook',hook)); st.enter_context(patch('socket.create_connection',side_effect=AssertionError('QA sockets blocked'))); st.enter_context(patch('socket.socket.connect',side_effect=AssertionError('QA sockets blocked')))
 browser=st.enter_context(patch('app.qt_golfhub_app.webbrowser.open'))
 st.enter_context(patch.object(GolfHub,'show_initial_cache')); st.enter_context(patch('app.qt_golfhub_app.save_local_snapshot')); st.enter_context(patch('app.qt_golfhub_app.fetch_shared_snapshot',return_value=None)); st.enter_context(patch('app.qt_golfhub_app.load_local_snapshot',return_value=None))
 w=GolfHub(); w._stop_deferred_timers(); w.resize(1280,800); w.show(); w.toggle_courses(); app.processEvents()
 row=next(r for r in w.course_rows if not r.isHidden())
 initial={'selected':len(w.selected_sites()),'label':w.selected_count.text()}
 QTest.mouseClick(row.check,Qt.LeftButton); app.processEvents()
 clicked={'selected':len(w.selected_sites()),'label':w.selected_count.text(),'checkbox_course':row.site.name,'checked':row.check.isChecked(),'callback_errors':len(errors)}
 assert w.grab().save(str(out/f'journey-selection-{a.phase}.png'))
 report['selection']={'initial':initial,'after_checkbox_click':clicked,'count_agrees':w.selected_count.text()==f'{len(w.selected_sites())} selected'}
 report['names']={k:names(v) for k,v in [('players',w.players),('time_preset',w.time_preset),('start_time',w.time_from),('end_time',w.time_to),('course_search',w.course_search),('course_checkbox',row.check)]}
 report['search_placeholder']=w.course_search.placeholderText()
 QTest.keyClick(row.check,Qt.Key_Space); app.processEvents()
 report['selection']['after_space']={'selected':len(w.selected_sites()),'label':w.selected_count.text(),'checked':row.check.isChecked()}
 # Course-name filtering is case insensitive; coverage includes exactly all configured eligible courses.
 w.course_search.setText(row.site.name.upper()); app.processEvents()
 report['case_insensitive_name_search']=[r.site.name for r in w.course_rows if not r.isHidden()]
 assert report['case_insensitive_name_search']==[row.site.name]
 w.course_search.clear(); w.set_all(True); app.processEvents()
 dates=[w.date.minimumDate().toString('yyyy-MM-dd'),w.date.minimumDate().addDays(1).toString('yyyy-MM-dd')]
 coverage={'configured':len(w.sites),'providers':dict(collections.Counter(s.provider for s in w.sites)),'dates':dates,'rounds':{},'intercepted_course_card_clicks':0,'url_checks':[]}
 for hole,button in [('18',w.holes18),('9',w.holes9),('18',w.holes18)]:
  QTest.mouseClick(button,Qt.LeftButton); app.processEvents()
  eligible=[s for s in w.sites if hole in s.holes]
  actual=[r.site.name for r in w.course_rows if not r.isHidden()]
  assert actual==[s.name for s in eligible]
  coverage['rounds'][hole]={'eligible':actual,'selected':len(w.selected_sites())}
 for hole in ('18','9'):
  for day in dates:
   for site in [s for s in w.sites if hole in s.holes]:
    if site.provider=='direct': result=direct_result(site,day,hole)
    else: result={'site_name':site.name,'url':site.build_url(day,hole),'hole_label':f'{hole} holes','weather':None,'decorated_rows':[]}
    url=result['url']; parsed=urlsplit(url); assert parsed.scheme=='https' and parsed.netloc and not parsed.username
    if site.provider=='miclub': assert parse_qs(parsed.query)['selectedDate']==[day]
    elif site.provider=='quick18': assert parse_qs(parsed.query)['teedate']==[day.replace('-','')]
    card=ResultCard(result,[]); card.show(); app.processEvents(); btn=card.findChild(QPushButton)
    expected=card.open_target or url
    browser.reset_mock(); QTest.mouseClick(btn,Qt.LeftButton); app.processEvents(); browser.assert_called_once_with(expected)
    coverage['intercepted_course_card_clicks']+=1
    coverage['url_checks'].append({'course':site.name,'date':day,'holes':hole,'provider':site.provider,'url':url,'intercepted_url':expected})
    card.close(); card.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
 report['coverage']=coverage
 # A newly published record can still contain a stale course; do not infer observation age from publication.
 w.date.set_dates([w.date.minimumDate()]); w.set_all(False); r=next(r for r in w.course_rows if r.site.provider=='miclub'); r.check.setChecked(True); w.course_panel.hide(); w.context=w.params()
 now=datetime.now(timezone.utc); old=(now-timedelta(hours=2)).isoformat(); site=r.site; url=site.build_url(dates[0],'18')
 result={'site_name':site.name,'url':url,'hole_label':'18 holes','error':None,'stale':True,'stale_since':old,'last_success_at':old,'weather_generated_at':old,'weather':{'label':'Clear','tmin':12,'tmax':24,'rain_chance':10,'wind':15},'decorated_rows':[{'time':'10:00 am','minutes':600,'spots':4,'source_url':url}]}
 w.render_snapshot({'schema':1,'date':dates[0],'holes':'18','generated_at':now.isoformat(),'results':[result]},'Shared cache'); app.processEvents()
 card=w.findChild(ResultCard); labels=[x.text() for x in card.findChildren(QLabel)]
 report['freshness_fixture']={'publication_age_seconds':0,'course_and_weather_fixture_age_seconds':7200,'header':w.header_status.text(),'card_labels':labels,'stale_marker_visible':any('stale' in x.lower() for x in labels),'known_backlog_finding':True}
 if a.phase=='after': assert w.grab().save(str(out/'journey-stale-publication.png'))
 # Renderer evidence is synthetic; source-data quality sampled separately.
 report['weather_rendering']={}
 for label,value in [('unavailable',None),('valid_zero_rain',{'label':'Clear','tmin':12,'tmax':24,'rain_chance':0,'wind':15}),('zero_sentinel',{'label':'Clear','tmin':0,'tmax':0,'rain_chance':0,'wind':0}),('partial',{'label':'Clear','rain_chance':0})]:
  b=WeatherBadge(value); report['weather_rendering'][label]=[q.text() for q in b.findChildren(QLabel)]; b.deleteLater()
 report['callback_errors']={'count':len(errors),'distinct':sorted(set(errors))}
 report['limitations']=['Linux offscreen widgets only; no installed Windows, Android device, display scaling, screen-reader or native input testing.','All booking opens intercepted; no provider URL visited, booking selection, hold or transaction.','Synthetic weather and stale records do not demonstrate a live outage or forecast observation age.','Combo interface Name may return current value under Qt 6.12; property and interface are recorded separately.']
 w.close(); w.deleteLater(); app.processEvents(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete); app.processEvents()
(out/f'journey-probe-{a.phase}.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'phase':a.phase,'selection':report['selection'],'names':report['names'],'coverage_clicks':coverage['intercepted_course_card_clicks'],'callback_error_count':len(errors)},indent=2))
