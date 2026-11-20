"""Plain Qt setter-order observation; no Golf Hub, browser or modal loop."""
import json,os
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory(prefix='golfhub-flags-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=runtime,TEMP=runtime,TMP=runtime)
    from PySide6.QtCore import Qt,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QLabel,QMessageBox,QWidget
    app=QApplication([])
    parent=QWidget()
    parent.setStyleSheet('QLabel { color:#F6F6F6; } QPushButton { cursor:pointer; }')
    parent.show()
    records=[]
    for position in ('before_text','after_text','after_stylesheet'):
        message=QMessageBox(parent)
        message.setIcon(QMessageBox.Warning)
        message.setTextFormat(Qt.PlainText)
        values=[]
        def snap(stage):
            label=message.findChild(QLabel,'qt_msgbox_label')
            values.append({'stage':stage,'message_flags':message.textInteractionFlags().value,
                'label_flags':label.textInteractionFlags().value if label else None})
        snap('created')
        if position=='before_text':message.setTextInteractionFlags(Qt.TextSelectableByMouse|Qt.TextSelectableByKeyboard)
        snap('before_text')
        message.setText('Exact address:\nhttps://example.invalid/long?date=2033-01-03&round=18')
        if position=='after_text':message.setTextInteractionFlags(Qt.TextSelectableByMouse|Qt.TextSelectableByKeyboard)
        snap('after_text')
        message.setStandardButtons(QMessageBox.Ok)
        message.setStyleSheet('QMessageBox { background:#111111; color:#F6F6F6; } QMessageBox QLabel { color:#F6F6F6; } QMessageBox QPushButton {background:#F59E0B;color:#090909;}')
        snap('after_stylesheet_before_flags')
        if position=='after_stylesheet':message.setTextInteractionFlags(Qt.TextSelectableByMouse|Qt.TextSelectableByKeyboard)
        snap('before_show')
        message.show()
        for _ in range(4):app.processEvents()
        snap('shown')
        records.append({'flags_position':position,'stages':values})
        message.close()
        message.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    parent.close()
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    app.processEvents()
out=Path(__file__).resolve().parent/'flags-order'
out.mkdir(exist_ok=True)
(out/'result.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))
