"""Offline focused verification; each Qt module runs in a fresh process."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, out = args.root.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
modules = ["test_retained_search_context.py", "test_startup_cache.py", "test_provider_error_states.py", "test_result_counts.py", "test_booking_assist.py", "test_booking_assist_guards.py",
           "test_booking_assist_optin.py", "test_booking_ui_integration.py",
           "test_v5_ui_requirements.py", "test_collier_behavior.py", "test_multiday_cache_states.py", "test_midnight_rollover.py", "test_booking_context.py", "test_course_controls.py",
           "test_calendar_keyboard.py", "test_multiday_ui.py",
           "test_perth_dates.py", "test_time_range_ui.py", "test_search_race.py",
           "test_thread_lifecycle.py", "test_cache*.py"]
code = '''import json, sys, unittest
from unittest.mock import patch
sys.path[:0] = ['.', 'tests']
def blocked(*args, **kwargs): raise AssertionError('QA networking/browser blocked')
with patch('socket.create_connection', blocked), patch('socket.socket.connect', blocked), patch('webbrowser.open', blocked):
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests', pattern=sys.argv[1]))
    from tests.qt_test_support import cleanup_qt_widgets
    cleanup_qt_widgets()
    print('QA_RESULT', json.dumps({'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}), flush=True)
    sys.exit(not result.wasSuccessful())
'''
report = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "status": subprocess.check_output(["git", "status", "--short"], cwd=root, text=True),
    "source_sha256": hashlib.sha256((root / "app/qt_golfhub_app.py").read_bytes()).hexdigest(),
    "cache_source_sha256": hashlib.sha256((root / "app/shared_cache.py").read_bytes()).hexdigest(),
    "ui_source_sha256": hashlib.sha256((root / "app/qt_golfhub_app.py").read_bytes()).hexdigest(),
    "regression_sha256": hashlib.sha256((root / "tests/test_retained_search_context.py").read_bytes()).hexdigest(),
    "kind": "Linux offscreen source checks; blocked sockets and browser; separate module processes",
    "modules": [],
}
with tempfile.TemporaryDirectory(prefix="golfhub-retained-context-final-") as runtime:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
               XDG_CACHE_HOME=runtime, TMP=runtime, TEMP=runtime, PYTHONUNBUFFERED="1")
    for module in modules:
        log_path = out / (module.replace("*", "-all").replace(".py", ".log"))
        result = {"module": module, "log": log_path.name}
        try:
            run = subprocess.run([sys.executable, "-X", "faulthandler", "-c", code, module],
                                 cwd=root, env=env, capture_output=True, text=True, timeout=60)
            log = run.stdout + run.stderr
            result["exit_code"] = run.returncode
            match = re.search(r"QA_RESULT (.+)", log)
            if match:
                result.update(json.loads(match[1]))
        except subprocess.TimeoutExpired as error:
            result["timeout"] = True
            log = str(error.stdout) + str(error.stderr)
        log_path.write_text(log)
        report["modules"].append(result)
        (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(result), flush=True)
sys.exit(any(item.get("exit_code", 1) != 0 for item in report["modules"]))
