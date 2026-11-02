"""Read-only synthetic calendar mouse mapping review; no providers or workers."""
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

ROOT = Path('/workspace/golfhub-20261101')
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-calendar-grid-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QTableView
    from app.qt_golfhub_app import MultiDatePopup
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    errors, grids, actions = [], [], []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.getaddrinfo', 'webbrowser.open', 'app.qt_golfhub_app.CacheWorker',
                       'app.qt_golfhub_app.ScanWorker'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline source probe only')))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *args: errors.append(str(args[1]))))
        for year, month in ((2032, 3), (2032, 11), (2033, 8), (2033, 1)):
            start = QDate(year, month, 1)
            popup = MultiDatePopup(start, start.addDays(27), [start])
            popup.show()
            app.processEvents()
            view = popup.calendar.findChild(QTableView, 'qt_calendar_calendarview')
            model = view.model()
            cells = []
            for row in range(1, model.rowCount()):
                for col in range(model.columnCount()):
                    idx = model.index(row, col)
                    center = view.visualRect(idx).center()
                    inferred = popup.calendar._date_at_view_position(center)
                    cells.append({'row': row, 'column': col, 'model_day': idx.data(),
                                  'inferred': inferred.toString('yyyy-MM-dd') if inferred else None})
            grids.append({'month': start.toString('yyyy-MM'), 'first_weekday': start.dayOfWeek(), 'cells': cells})
            for target_day in (2, 8, 15, 22, 24, 25, 26, 27, 28):
                idx = next(model.index(r,c) for r in range(1, model.rowCount())
                           for c in range(model.columnCount()) if str(model.index(r,c).data()) == str(target_day)
                           and bool(model.index(r,c).flags() & Qt.ItemIsEnabled))
                focused_before = popup.calendar.selectedDate().toString('yyyy-MM-dd')
                coordinate = view.visualRect(idx).center()
                QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(idx).center())
                app.processEvents()
                expected = QDate(year, month, target_day)
                actions.append({'month': start.toString('yyyy-MM'), 'clicked_day': target_day,
                                'row': idx.row(), 'column': idx.column(),
                                'coordinates': [coordinate.x(), coordinate.y()],
                                'model_label': idx.data(), 'enabled': bool(idx.flags() & Qt.ItemIsEnabled),
                                'focused_before': focused_before,
                                'focused': popup.calendar.selectedDate().toString('yyyy-MM-dd'),
                                'chosen': [d.toString('yyyy-MM-dd') for d in popup.selected_dates()],
                                'selected_expected': expected in popup.selected_dates()})
            popup.grab().save(str(OUT / f'calendar-{start.toString("yyyy-MM")}.png'))
            popup.close()
            cleanup_qt_widgets()
        result = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'source_sha256': hashlib.sha256((ROOT/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                  'scope': 'Synthetic Qt offscreen source widget actions, isolated paths, network/browser/workers blocked',
                  'grids': grids, 'actions': actions, 'callback_errors': errors}
        (OUT/'calendar-grid-probe.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'actions': len(actions), 'selected_expected': sum(x['selected_expected'] for x in actions),
                          'failures': [x for x in actions if not x['selected_expected']], 'callback_errors': errors}))
