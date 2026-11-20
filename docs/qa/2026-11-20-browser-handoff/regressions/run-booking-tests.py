"""Bounded offline external runner; retain method and subscenario counts separately."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--test-file", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, test_file, output = args.root.resolve(), args.test_file.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
base = "66eaf00f76e748cf6f76ef6a758574a3d996360c"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
before = ast.parse(subprocess.check_output(["git", "show", base + ":tests/test_booking_context.py"], cwd=root, text=True))
after = ast.parse(test_file.read_text())
original = next(node for node in before.body if isinstance(node, ast.ClassDef) and node.name == "BookingContextTests")
preserved = next(node for node in after.body if isinstance(node, ast.ClassDef) and node.name == "BookingContextTests")
assert ast.dump(original, include_attributes=False) == ast.dump(preserved, include_attributes=False)

class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.method_ids, self.passed_method_ids, self.subscenario_records = [], [], []

    def startTest(self, test):
        self.method_ids.append(test.id())
        super().startTest(test)

    def addSuccess(self, test):
        self.passed_method_ids.append(test.id())
        super().addSuccess(test)

    def addSubTest(self, test, subtest, error):
        if isinstance(test, module.BrowserHandoffTests):
            self.subscenario_records.append({
                "method": test.id(), "params": dict(subtest.params),
                "status": "pass" if error is None else "fail" if issubclass(error[0], test.failureException) else "error",
                "exception": None if error is None else error[0].__name__,
                "message": None if error is None else str(error[1]),
            })
        super().addSubTest(test, subtest, error)

def blocked(*args, **kwargs):
    raise AssertionError("Offline regression runner: networking/browser blocked")

with tempfile.TemporaryDirectory(prefix="golfhub-browser-regressions-") as runtime:
    os.environ.update(QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
                      XDG_CACHE_HOME=runtime, TMP=runtime, TEMP=runtime)
    os.chdir(root)
    sys.path[:0] = [str(root), str(root / "tests")]
    with patch("socket.create_connection", blocked), patch("socket.socket.connect", blocked), \
         patch("socket.socket.connect_ex", blocked), patch("socket.getaddrinfo", blocked), patch("webbrowser.open", blocked):
        spec = importlib.util.spec_from_file_location("test_booking_context", test_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
        from tests.qt_test_support import cleanup_qt_widgets
        cleanup_qt_widgets()

record = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "base_commit": base, "source_root": str(root),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "app_sha256": sha(root / "app/qt_golfhub_app.py"),
    "test_file": str(test_file), "test_sha256": sha(test_file),
    "original_class_ast_identical": True, "tests_run": result.testsRun,
    "passed_methods": len(result.passed_method_ids), "failure_records": len(result.failures),
    "error_records": len(result.errors), "skipped": len(result.skipped),
    "successful": result.wasSuccessful(), "method_ids": result.method_ids,
    "passed_method_ids": result.passed_method_ids,
    "failure_ids": [test.id() for test, trace in result.failures],
    "error_ids": [test.id() for test, trace in result.errors],
    "subscenarios": result.subscenario_records,
    "matrix_subscenarios": sum("outcome" in item["params"] for item in result.subscenario_records),
    "guard_subscenarios": sum("outcome" not in item["params"] for item in result.subscenario_records),
    "limits": "Qt button.click, intercepted browser/dialogs/persistence, blocked sockets/DNS/worker bodies; no native browser, provider, WebEngine or hold",
}
(output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
print("QA_RESULT", json.dumps({key: record[key] for key in
      ("tests_run", "passed_methods", "failure_records", "error_records", "skipped", "matrix_subscenarios", "guard_subscenarios", "successful")}))
sys.exit(not result.wasSuccessful())
