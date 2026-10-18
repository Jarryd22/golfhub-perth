"""Shared lifecycle cleanup for isolated Qt widget test suites."""

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication


def cleanup_qt_widgets():
    """Destroy test widgets while QApplication and Python are still alive.

    Closing a widget only hides it. Leaving hidden windows until interpreter
    shutdown can make Qt/Python destruction order fail after tests report OK.
    Flush their deferred deletion explicitly without changing test results.
    """
    app = QApplication.instance()
    if app is None:
        return
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
