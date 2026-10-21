import os, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDate
from app import qt_golfhub_app as ui
from tests.qt_test_support import cleanup_qt_widgets
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
now = datetime(2032, 12, 31, 15, 59, 59, tzinfo=timezone.utc)
with patch.object(ui, 'datetime') as clock, patch.object(ui.GolfHub, 'show_initial_cache'), patch('socket.socket.connect', side_effect=AssertionError('Offline')), patch('webbrowser.open', side_effect=AssertionError('Offline')):
    clock.now.side_effect = lambda tz: now.astimezone(tz)
    window = ui.GolfHub()
    window._initial_cache_timer.stop(); window._cache_search_timer.stop()
    window.resize(980, 640)
    window.date.setDate(QDate(2032, 12, 31))
    window.show(); app.processEvents()
    now += timedelta(seconds=1)
    window.date.open_picker(); app.processEvents()
    window.grab().save(str(out / 'window.png'))
    window.date.picker_popup().grab().save(str(out / 'picker.png'))
    cleanup_qt_widgets()
