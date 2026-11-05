"""Read-only palette proof, then an in-memory existing-selector specificity correction."""
from contextlib import ExitStack
import hashlib,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
root=Path('/workspace/golfhub-20261105');out=Path('/workspace/scratch/golfhub-20261105-disabled-style')
sys.path[:0]=[str(root),str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-disabled-style-') as runtime:
 os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
 from PySide6.QtCore import QDate
 from PySide6.QtGui import QPalette
 from PySide6.QtWidgets import QApplication,QPushButton
 from app import qt_golfhub_app as ui
 from tests.qt_test_support import cleanup_qt_widgets
 app=QApplication.instance() or QApplication([])
 with ExitStack() as stack:
  for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex','socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.ScanWorker','app.qt_golfhub_app.CacheWorker','app.course_results.get_weather_for_date'):
   stack.enter_context(patch(target,side_effect=AssertionError('Offline style probe')))
  stack.enter_context(patch.object(ui,'perth_today',return_value=QDate(2033,1,2)))
  with patch.object(ui.GolfHub,'show_initial_cache'):window=ui.GolfHub()
  window._stop_deferred_timers();window.resize(1280,800);window.show()
  plain=QPushButton('PLAIN DISABLED REFERENCE',window.centralWidget());plain.setGeometry(600,10,280,40);plain.show()
  def colors(button):
   button.ensurePolished()
   for _ in range(3):app.processEvents()
   palette=button.palette();state=QPalette.Active if button.isEnabled() else QPalette.Disabled
   return {'enabled':button.isEnabled(),'active_text':palette.color(QPalette.Active,QPalette.ButtonText).name(),
    'disabled_text':palette.color(QPalette.Disabled,QPalette.ButtonText).name(),
    'current_text':palette.color(state,QPalette.ButtonText).name(),
    'current_background':palette.color(state,QPalette.Button).name()}
  enabled=colors(window.live_button)
  window.date.set_dates([QDate(2033,1,3),QDate(2033,1,4)]);plain.setEnabled(False)
  before={'live':colors(window.live_button),'plain':colors(plain)}
  window.live_button.grab().save(str(out/'before-live.png'));plain.grab().save(str(out/'plain-disabled.png'))
  css=window.styles();original='QPushButton:disabled {';replacement='QPushButton:disabled, QPushButton#OutlineButton:disabled {'
  assert css.count(original)==1
  window.setStyleSheet(css.replace(original,replacement))
  after={'live':colors(window.live_button),'plain':colors(plain)}
  window.live_button.grab().save(str(out/'after-live.png'))
  window.date.set_dates([QDate(2033,1,3)])
  restored=colors(window.live_button)
  report={'source':str(root),'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
   'palette_constants':{k:ui.PALETTE[k] for k in ('text','faint','surface2')},'enabled':enabled,'before':before,
   'after_in_memory_selector_change':after,'restored_enabled':restored,
   'method':'Linux Qt offscreen actual palettes and button images; same existing disabled colors, in-memory selector qualification only; no source mutation, workers/network blocked'}
  (out/'probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));cleanup_qt_widgets()
