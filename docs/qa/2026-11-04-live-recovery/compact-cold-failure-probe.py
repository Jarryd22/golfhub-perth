"""Cold cache-to-live failure with an actual synchronous ScanWorker signal."""
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
from unittest.mock import MagicMock, patch

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, output = args.root.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root/'tests')]
with tempfile.TemporaryDirectory(prefix='golfhub-cold-failure-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate, QPoint, QRect
    from PySide6.QtWidgets import QApplication, QLabel
    from app import shared_cache
    from app.qt_golfhub_app import GolfHub, ScanWorker
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    errors = []
    with ExitStack() as stack:
        for target in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex',
                       'socket.getaddrinfo','webbrowser.open','app.qt_golfhub_app.fetch_site_result',
                       'app.qt_golfhub_app.save_local_snapshot'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline probe')))
        stack.enter_context(patch('app.qt_golfhub_app.perth_today',return_value=QDate(2033,1,2)))
        stack.enter_context(patch.object(shared_cache,'LOCAL_CACHE_DIR',Path(runtime)/'cache'))
        stack.enter_context(patch('sys.excepthook',side_effect=lambda *a: errors.append(str(a[1]))))
        message=stack.enter_context(patch('app.qt_golfhub_app.QMessageBox.critical'))
        thread=MagicMock(); thread.isRunning.return_value=False; thread.wait.return_value=True
        stack.enter_context(patch('app.qt_golfhub_app.QThread',return_value=thread))
        stack.enter_context(patch.object(ScanWorker,'moveToThread'))
        with patch.object(GolfHub,'show_initial_cache'):
            window=GolfHub()
        window._stop_deferred_timers(); window.resize(980,640); window.show()
        window.set_all(False)
        next(r for r in window.course_rows if r.site.name=='Araluen').check.setChecked(True)
        window.date.setDate(QDate(2033,1,2))
        window.context=window.params()
        window._active_cache_context=window._snapshot_search_context(window.context)
        window.cache_finished({})
        worker=window.scan_worker
        before={'labels':[l.text() for l in window.results_body.findChildren(QLabel)],
                'status':window.status.text(),'last_results':window.last_results}
        with patch('app.qt_golfhub_app.ThreadPoolExecutor',side_effect=RuntimeError('Synthetic executor setup failed')):
            worker.run()
        for _ in range(3): app.processEvents()
        report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
                'kind':'Linux offscreen; real cache_finished/search_live and synchronous ScanWorker.run/failed signal; native QThread creation/move intercepted; executor fails before work; real empty temporary local cache; socket/provider/browser/save blocked',
                'before':before,'after':{'labels':[l.text() for l in window.results_body.findChildren(QLabel)],
                'status':window.status.text(),'header':window.header_status.text(),
                'dialog_text':message.call_args.args[2], 'search_enabled':window.search_button.isEnabled(),
                'progress_visible':window.progress.isVisible(),'last_results':window.last_results},
                'callback_errors':errors}
        report['logical_size'] = [window.width(), window.height()]
        report['retry_controls'] = {
            name: {'visible': button.isVisible(), 'enabled': button.isEnabled(),
                   'inside_window': window.rect().contains(QRect(button.mapTo(window, QPoint(0, 0)), button.size()))}
            for name, button in [('Find Tee Times', window.search_button), ('Refresh Live', window.live_button)]}
        report['recovery_note_visible'] = any(label.isVisible() and label.text().startswith('Could not load tee-time results.')
                                               for label in window.results_body.findChildren(QLabel))
        assert report['logical_size'] == [980, 640]
        assert report['recovery_note_visible']
        assert all(all(values.values()) for values in report['retry_controls'].values())
        assert not errors
        window.grab().save(str(output/'cold-failure.png'))
        (output/'cold-failure-probe.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        window.scan_thread=None; window.scan_worker=None; worker.deleteLater(); cleanup_qt_widgets()
