"""Run the identical calendar-mouse module against an explicit source tree."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--test', type=Path, required=True)
parser.add_argument('--metadata', type=Path, required=True)
args = parser.parse_args()
root, test = args.root.resolve(), args.test.resolve()
sys.path[:0] = [str(root), str(root / 'tests')]
spec = importlib.util.spec_from_file_location('calendar_mouse_candidate', test)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
def method_id(case):
    return getattr(case, 'test_case', case).id()
failed = sorted({method_id(case) for case, _ in result.failures})
errors = sorted({method_id(case) for case, _ in result.errors})
metadata = {
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'root': str(root),
    'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'source_status': subprocess.check_output(['git', 'status', '--short'], cwd=root, text=True),
    'app_sha256': hashlib.sha256((root / 'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
    'test_sha256': hashlib.sha256(test.read_bytes()).hexdigest(),
    'run': result.testsRun,
    'failed_methods': failed,
    'error_methods': errors,
    'passed_methods': result.testsRun - len(set(failed + errors)) - len(result.skipped),
    'failure_records': len(result.failures),
    'error_records': len(result.errors),
    'skipped': len(result.skipped),
    'exit_code': 0 if result.wasSuccessful() else 1,
}
args.metadata.write_text(json.dumps(metadata, indent=2)+'\n')
print('QA_RESULT ' + json.dumps(metadata), flush=True)
sys.exit(metadata['exit_code'])
