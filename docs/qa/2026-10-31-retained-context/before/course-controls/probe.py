"""Read-only offscreen keyboard/course-filter probe against exact PR19."""
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

ROOT = Path('/workspace/golfhub-20261030')
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-course-keyboard-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea
    from app.qt_golfhub_app import GolfHub
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    errors, checks = [], []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'webbrowser.open',
                       'app.qt_golfhub_app.CacheWorker', 'app.qt_golfhub_app.ScanWorker'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline probe only')))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *args: errors.append(str(args[1]))))
        with patch.object(GolfHub, 'show_initial_cache'):
            window = GolfHub()
        window._stop_deferred_timers()
        window.resize(980, 640)
        window.show()
        app.processEvents()
        window.course_button.setFocus()
        QTest.keyClick(window.course_button, Qt.Key_Space)
        app.processEvents()
        checks.append({'scenario': 'keyboard opens panel', 'pass': window.course_panel.isVisible()})
        path = []
        for _ in range(6):
            focus = app.focusWidget()
            path.append({'type': type(focus).__name__, 'name': focus.accessibleName(),
                         'text': focus.text() if hasattr(focus, 'text') else None})
            if focus is window.course_search:
                break
            QTest.keyClick(focus, Qt.Key_Tab)
        checks.append({'scenario': 'course search reachable by Tab', 'pass': app.focusWidget() is window.course_search,
                       'focus_path': path})
        select = next(b for b in window.course_panel.findChildren(QPushButton) if b.text() == 'Select visible')
        clear = next(b for b in window.course_panel.findChildren(QPushButton) if b.text() == 'Clear')
        for holes, button in (('18', window.holes18), ('9', window.holes9), ('18', window.holes18)):
            button.setChecked(True)
            for query in ('park', '  PARK  ', 'no-such-course', ''):
                clear.setFocus()
                QTest.keyClick(clear, Qt.Key_Space)
                window.course_search.setFocus()
                window.course_search.setText(query)
                QTest.keyClick(window.course_search, Qt.Key_Tab)
                focus_is_select = app.focusWidget() is select
                QTest.keyClick(select, Qt.Key_Space)
                actual = sorted(s.name for s in window.selected_sites())
                expected = sorted(s.name for s in window.sites if holes in s.holes and query.strip().lower() in s.name.lower())
                checks.append({'scenario': f'keyboard clear/filter/select {holes} {query!r}',
                               'pass': actual == expected and focus_is_select,
                               'actual': actual, 'expected': expected, 'tab_to_select': focus_is_select})
        window.course_search.clear()
        eligible = [r for r in window.course_rows if not r.isHidden()]
        eligible[0].check.setFocus()
        for _ in range(len(eligible) - 1):
            QTest.keyClick(app.focusWidget(), Qt.Key_Tab)
        app.processEvents()
        last = eligible[-1]
        area = window.course_panel.findChild(QScrollArea)
        position = last.check.mapTo(area.viewport(), last.check.rect().center())
        checks.append({'scenario': 'Tab reaches and scrolls to last course',
                       'pass': app.focusWidget() is last.check and area.viewport().rect().contains(position),
                       'last_course': last.site.name, 'viewport_y': position.y(),
                       'viewport_height': area.viewport().height()})
        selected_before = len(window.selected_sites())
        QTest.keyClick(last.check, Qt.Key_Space)
        checks.append({'scenario': 'Space toggles scrolled checkbox and count',
                       'pass': len(window.selected_sites()) == selected_before - 1 and
                       window.selected_count.text() == f'{selected_before - 1} selected'})
        report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'source_head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                  'source_sha256': hashlib.sha256((ROOT/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'scope': 'Linux Qt offscreen 980x640 synthetic input; network/browser/workers blocked; no native device test',
                  'checks': checks, 'callback_errors': errors}
        (OUT/'probe.json').write_text(json.dumps(report, indent=2)+'\n')
        window.grab().save(str(OUT/'scrolled-keyboard-course.png'))
        cleanup_qt_widgets()
        print(json.dumps({'checks': len(checks), 'passed': sum(c['pass'] for c in checks), 'callback_errors': errors}))
        assert not errors
        assert all(c['pass'] for c in checks)
