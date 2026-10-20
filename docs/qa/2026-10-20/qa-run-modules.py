"""Reproducible offline module QA; do not treat a crashed process as a pass."""
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
parser.add_argument("--phase", required=True)
args = parser.parse_args()
root, out = args.root.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
code = '''import json, sys, unittest
from unittest.mock import patch
sys.path[:0] = ['.', 'tests']
def blocked(*args, **kwargs): raise AssertionError('QA networking/browser blocked')
with patch('socket.create_connection', blocked), patch('socket.socket.connect', blocked), patch('webbrowser.open', blocked):
    suite = unittest.defaultTestLoader.loadTestsFromName(sys.argv[2]) if len(sys.argv)>2 else unittest.defaultTestLoader.discover('tests', pattern=sys.argv[1])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    from tests.qt_test_support import cleanup_qt_widgets
    cleanup_qt_widgets()
    print('QA_RESULT', json.dumps({'run':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors), 'skipped':len(result.skipped)}), flush=True)
    sys.exit(not result.wasSuccessful())
'''
report = {
    "phase": args.phase,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "source_sha256": hashlib.sha256((root / "app/qt_golfhub_app.py").read_bytes()).hexdigest(),
    "kind": "isolated Linux offscreen module processes with blocked sockets/browser opens",
    "external_widget_cleanup": True,
    "modules": [],
}
checks = []
for path in sorted((root / "tests").glob("test_*.py")):
    if path.name == "test_booking_dialog.py":
        checks += [(path.name, "test_booking_dialog.ResultInterpreterTests", 5),
                   (path.name, "test_booking_dialog.StaticBookingDialogTests", 4)]
    else:
        checks.append((path.name, None, None))
with tempfile.TemporaryDirectory(prefix=f"golfhub-{args.phase}-") as runtime:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu",
           "LOCALAPPDATA": runtime, "XDG_CACHE_HOME": runtime, "TMP": runtime, "TEMP": runtime}
    for module, klass, expected in checks:
        name = klass.rsplit(".", 1)[-1] if klass else module.removesuffix(".py")
        log_path = out / f"qa-{args.phase}-{name}.log"
        result = {"module": module, "class": klass, "log": log_path.name}
        cmd = [sys.executable, "-c", code, module] + ([klass] if klass else [])
        try:
            proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=60)
            log = proc.stdout + proc.stderr
            result["exit_code"] = proc.returncode
            match = re.search(r"QA_RESULT (.+)", log)
            if match:
                result.update(json.loads(match[1]))
                result["passed"] = result["run"] - result["failures"] - result["errors"] - result["skipped"]
            else:
                result["status"] = "process did not complete unittest"
                if "SUID sandbox helper" in log:
                    result["status"] = "blocked by Chromium SUID sandbox helper configuration"
                    result["blocked"] = expected
        except subprocess.TimeoutExpired as error:
            log = str(error.stdout) + str(error.stderr)
            result["status"] = "timeout"
        log_path.write_text(log)
        report["modules"].append(result)
        report["totals"] = {key: sum(r.get(key, 0) or 0 for r in report["modules"]) for key in ("passed", "failures", "errors", "skipped", "blocked")}
        (out / f"qa-{args.phase}-summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(result), flush=True)
