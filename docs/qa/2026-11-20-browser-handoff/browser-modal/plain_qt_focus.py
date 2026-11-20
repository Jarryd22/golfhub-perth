"""Plain Qt modal reference; no Golf Hub import or browser action."""
import hashlib,json,os
from pathlib import Path
import socket,sys,tempfile,traceback
from unittest.mock import patch
out=Path(__file__).resolve().parent/'plain-qt-reference'
out.mkdir(exist_ok=True)
report={'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'callback_errors':[]}
with tempfile.TemporaryDirectory(prefix='golfhub-plain-qt-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime,XDG_CACHE_HOME=runtime)
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QFrame,QMessageBox,QPushButton,QVBoxLayout,QWidget
    app=QApplication.instance() or QApplication([])
    def events():
        for _ in range(4):app.processEvents()
    def state():
        focus,active=app.focusWidget(),app.activeWindow()
        return {'focus_class':type(focus).__name__ if focus else None,
                'focus_text':focus.text() if focus and hasattr(focus,'text') else None,
                'active_window_class':type(active).__name__ if active else None,
                'button_has_focus':button.hasFocus(),'window_active':host.isActiveWindow()}
    with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('socket.create_connection',side_effect=AssertionError('No network')),patch('sys.excepthook',side_effect=lambda kind,value,_tb:report['callback_errors'].append(str(value))):
        host=QWidget()
        host.setWindowTitle('Plain Qt reference')
        host.resize(980,640)
        layout=QVBoxLayout(host)
        card=QFrame(host)
        layout.addWidget(card)
        inner=QVBoxLayout(card)
        button=QPushButton('Plain Qt warning',card)
        inner.addWidget(button)
        button.clicked.connect(lambda:QMessageBox.warning(card,'Plain reference','Plain Qt warning without any Golf Hub helper.'))
        host.show()
        button.setFocus()
        events()
        report['before']=state()
        def dismiss():
            message=app.activeModalWidget()
            report['real_message_box']=isinstance(message,QMessageBox)
            if isinstance(message,QMessageBox):
                ok=message.button(QMessageBox.Ok)
                ok.setFocus()
                QTest.keyClick(ok,Qt.Key_Return)
        QTimer.singleShot(20,dismiss)
        QTest.keyClick(button,Qt.Key_Space)
        QTest.qWait(40)
        events()
        report['after_keyboard_dismissal']=state()
        host.activateWindow()
        events()
        report['after_explicit_window_activation']=state()
        host.close()
        host.deleteLater()
        from PySide6.QtCore import QCoreApplication,QEvent
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        events()
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
