"""Run the identical regression file against an explicit source tree, offline."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--tests", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, tests, output = args.root.resolve(), args.tests.resolve(), args.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
code = '''import importlib.util, json, sys, unittest
from unittest.mock import patch
sys.path[:0] = [sys.argv[1], str(__import__('pathlib').Path(sys.argv[1]) / 'tests')]
def blocked(*args, **kwargs): raise AssertionError('QA network/browser blocked')
with patch('socket.create_connection', blocked), patch('socket.socket.connect', blocked), patch('webbrowser.open', blocked):
    spec = importlib.util.spec_from_file_location('cache_state_regressions', sys.argv[2])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
    print('QA_RESULT', json.dumps({'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}), flush=True)
    sys.exit(not result.wasSuccessful())
'''
report = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "source_sha256": hashlib.sha256((root / "app/qt_golfhub_app.py").read_bytes()).hexdigest(),
    "test_sha256": hashlib.sha256(tests.read_bytes()).hexdigest(),
}
with tempfile.TemporaryDirectory(prefix="golfhub-availability-regressions-") as runtime:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
               XDG_CACHE_HOME=runtime, TEMP=runtime, TMP=runtime, PYTHONUNBUFFERED="1")
    try:
        run = subprocess.run([sys.executable, "-X", "faulthandler", "-c", code, str(root), str(tests)],
                             cwd=root, env=env, text=True, capture_output=True, timeout=60)
        log = run.stdout + run.stderr
        report["exit_code"] = run.returncode
        result_line = next(line for line in run.stdout.splitlines() if line.startswith("QA_RESULT "))
        report.update(json.loads(result_line.removeprefix("QA_RESULT ")))
    except subprocess.TimeoutExpired as exc:
        report["timeout"] = True
        log = str(exc.stdout) + str(exc.stderr)
output.with_suffix(".log").write_text(log)
output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
sys.exit(report.get("exit_code", 1))
