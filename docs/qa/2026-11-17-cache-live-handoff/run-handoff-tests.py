"""Run the identical live-button module against a chosen source checkout."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--test-file', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, test_file, output = args.root.resolve(), args.test_file.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path[:0] = [str(root), str(root / 'tests')]
with ExitStack() as guards:
    for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex',
                   'socket.getaddrinfo', 'webbrowser.open'):
        guards.enter_context(patch(target, side_effect=AssertionError('Offline handoff regression')))
    spec = importlib.util.spec_from_file_location('test_live_button_state', test_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'source_root': str(root),
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'app_sha256': hashlib.sha256((root / 'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
    'test_file': str(test_file), 'test_sha256': hashlib.sha256(test_file.read_bytes()).hexdigest(),
    'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
    'skipped': len(result.skipped), 'successful': result.wasSuccessful(),
    'failure_ids': [str(test) for test, _ in result.failures],
    'error_ids': [str(test) for test, _ in result.errors]}
(output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
sys.exit(not result.wasSuccessful())
