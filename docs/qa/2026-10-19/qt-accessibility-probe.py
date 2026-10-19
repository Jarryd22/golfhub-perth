"""Standalone QComboBox probe; run with the Qt version being inspected.

No Golf Hub imports, provider access, or native screen-reader testing.
Qt's Unix Name/Value behavior is implemented in QAccessibleComboBox::text:
https://github.com/qt/qtbase/blob/v6.12.0/src/widgets/accessible/complexwidgets.cpp
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import __version__
from PySide6.QtCore import qVersion
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QVBoxLayout, QWidget

app = QApplication([])
window = QWidget()
layout = QVBoxLayout(window)
controls = []
for has_buddy in (False, True):
    combo = QComboBox()
    combo.addItems(["Any", "9:00 am"])
    combo.setAccessibleName("Start time")
    if has_buddy:
        label = QLabel("Start time")
        label.setBuddy(combo)
        layout.addWidget(label)
    layout.addWidget(combo)
    controls.append((has_buddy, combo))
window.show()
app.processEvents()
cases = []
for has_buddy, combo in controls:
    for value in ("Any", "9:00 am"):
        combo.setCurrentText(value)
        interface = QAccessible.queryAccessibleInterface(combo)
        cases.append({
            "has_buddy": has_buddy,
            "current_text": combo.currentText(),
            "widget_accessible_name": combo.accessibleName(),
            "interface_name": interface.text(QAccessible.Name),
            "interface_value": interface.text(QAccessible.Value),
            "label_relations": [
                other.text(QAccessible.Name)
                for other, relation in interface.relations()
                if relation & QAccessible.RelationFlag.Label
            ],
        })
print(json.dumps({
    "pyside_version": __version__, "qt_version": qVersion(),
    "system_platform": sys.platform, "qt_platform": app.platformName(),
    "cases": cases,
}, indent=2))
