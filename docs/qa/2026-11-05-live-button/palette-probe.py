"""Actual disabled palette and compact source-widget image; no style overrides."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, output = args.root.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-live-palette-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate, QPoint, QRect
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication, QPushButton
    from app import qt_golfhub_app as ui
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    callbacks = []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.getaddrinfo', 'webbrowser.open', 'app.qt_golfhub_app.ScanWorker',
                       'app.qt_golfhub_app.CacheWorker', 'app.course_results.get_weather_for_date'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline palette probe')))
        stack.enter_context(patch.object(ui, 'perth_today', return_value=QDate(2033, 1, 2)))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *a: callbacks.append(str(a[1]))))
        with patch.object(ui.GolfHub, 'show_initial_cache'):
            window = ui.GolfHub()
        window._stop_deferred_timers()
        window.resize(980, 640)
        window.show()
        reference = QPushButton('Disabled reference', window.centralWidget())
        reference.setEnabled(False)
        reference.ensurePolished()
        reference.hide()

        def settle():
            for _ in range(3):
                app.processEvents()

        def colors(button):
            button.ensurePolished()
            settle()
            palette = button.palette()
            state = QPalette.Active if button.isEnabled() else QPalette.Disabled
            return {'enabled': button.isEnabled(),
                    'active_text': palette.color(QPalette.Active, QPalette.ButtonText).name(),
                    'disabled_text': palette.color(QPalette.Disabled, QPalette.ButtonText).name(),
                    'current_text': palette.color(state, QPalette.ButtonText).name(),
                    'current_background': palette.color(state, QPalette.Button).name()}

        enabled = colors(window.live_button)
        window.date.set_dates([QDate(2033, 1, 3), QDate(2033, 1, 4)])
        disabled = colors(window.live_button)
        window.grab().save(str(output/'compact-disabled.png'))
        window.live_button.grab().save(str(output/'disabled-button.png'))
        button_rect = QRect(window.live_button.mapTo(window, QPoint(0, 0)), window.live_button.size())
        geometry = {'window': [window.width(), window.height()],
                    'button': [button_rect.x(), button_rect.y(), button_rect.width(), button_rect.height()],
                    'button_within_window': window.rect().contains(button_rect)}
        window.date.set_dates([QDate(2033, 1, 3)])
        restored = colors(window.live_button)
        window.grab().save(str(output/'compact-enabled.png'))
        report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  'app_sha256': hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'enabled': enabled, 'disabled': disabled, 'restored_enabled': restored,
                  'plain_disabled_reference': colors(reference),
                  'existing_palette': {key: ui.PALETTE[key] for key in ('text', 'faint', 'surface2')},
                  'compact_geometry': geometry, 'callback_errors': callbacks,
                  'method': 'Linux offscreen real pending-date changes and widget palettes; exact source stylesheet without overrides; workers/socket/DNS/browser/weather blocked; no native device or screen reader'}
        (output/'palette-probe.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        cleanup_qt_widgets()
