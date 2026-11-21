"""Offline cache-age regressions against an explicit source root and test file."""
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
base = "4fe841359f1d0b3e4a261649c286f04d0bfbac54"
old_ast = ast.parse(subprocess.check_output(["git", "show", base + ":tests/test_startup_cache.py"], cwd=root, text=True))
new_ast = ast.parse(test_file.read_text())
preserved = []
for old in old_ast.body:
    if isinstance(old, (ast.ClassDef, ast.FunctionDef)):
        new = next(node for node in new_ast.body if isinstance(node, type(old)) and node.name == old.name)
        assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False), old.name
        preserved.append(old.name)

class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.methods, self.passed, self.subscenarios = [], [], []

    def startTest(self, test):
        self.methods.append(test.id())
        super().startTest(test)

    def addSuccess(self, test):
        self.passed.append(test.id())
        super().addSuccess(test)

    def addSubTest(self, test, subtest, error):
        if isinstance(test, module.CacheAgeMetadataTests):
            self.subscenarios.append({"method": test.id(), "parameters": dict(subtest.params),
                                     "status": "pass" if error is None else "fail" if issubclass(error[0], test.failureException) else "error",
                                     "exception": None if error is None else error[0].__name__,
                                     "message": None if error is None else str(error[1])})
        super().addSubTest(test, subtest, error)

def blocked(*args, **kwargs):
    raise AssertionError("Offline cache-age runner blocks networking/browser")

with tempfile.TemporaryDirectory(prefix="golfhub-age-regressions-") as runtime:
    os.environ.update(QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
                      XDG_CACHE_HOME=runtime, TMP=runtime, TEMP=runtime)
    os.chdir(root)
    sys.path[:0] = [str(root), str(root / "tests")]
    with patch("socket.create_connection", blocked), patch("socket.socket.connect", blocked), \
         patch("socket.socket.connect_ex", blocked), patch("socket.getaddrinfo", blocked), patch("webbrowser.open", blocked):
        spec = importlib.util.spec_from_file_location("test_startup_cache", test_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(unittest.defaultTestLoader.loadTestsFromModule(module))

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
record = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "base_commit": base,
    "source_root": str(root), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "qt_sha256": sha(root / "app/qt_golfhub_app.py"), "shared_cache_sha256": sha(root / "app/shared_cache.py"),
    "test_file": str(test_file), "test_sha256": sha(test_file), "preserved_original_ast": preserved,
    "tests_run": result.testsRun, "passed_methods": len(result.passed),
    "failure_records": len(result.failures), "error_records": len(result.errors), "skipped": len(result.skipped),
    "successful": result.wasSuccessful(), "method_ids": result.methods, "passed_method_ids": result.passed,
    "failure_ids": [test.id() for test, trace in result.failures], "error_ids": [test.id() for test, trace in result.errors],
    "new_test_subscenarios": result.subscenarios,
    "limits": "Isolated actual JSON files and intercepted HTTP bytes/scheduling; workers/browser/provider/booking blocked. No real native/device/live behavior."
}
(output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
print("QA_RESULT", json.dumps({key: record[key] for key in
      ("tests_run", "passed_methods", "failure_records", "error_records", "skipped", "successful")}))
sys.exit(not result.wasSuccessful())
