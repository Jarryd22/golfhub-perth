"""Reuse the existing isolated PR24 recovery fixture; no native worker runs."""
import argparse,hashlib,json,sys
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root,output=args.root.resolve(),args.output.resolve()
output.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests')]
import test_live_recovery_states as fixture
fixture.LiveRecoveryStateTests.setUpClass()
case=fixture.LiveRecoveryStateTests()
case.setUp()
try:
    worker=case.start_live()
    window=case.window
    window.close()
    before={'closing':window._closing,'visible':window.isVisible(),'live_enabled':window.live_button.isEnabled()}
    worker.finished.emit([],True)
    after={'closing':window._closing,'visible':window.isVisible(),'live_enabled':window.live_button.isEnabled(),
           'scan_thread_retained':window.scan_thread is not None}
    window.live_button.click()
    after['worker_unchanged_after_click']=window.scan_worker is worker
    result={'before':before,'after':after,'callbacks':case.callbacks,
            'app_sha256':hashlib.sha256((root/'app/qt_golfhub_app.py').read_bytes()).hexdigest(),
            'method':'Actual closeEvent + synthetic finished signal; existing isolated PR24 fixture with inert QThread and blocked network/provider/weather/booking'}
    (output/'closing-probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
finally:
    case.tearDown();case.doCleanups();fixture.tearDownModule()
