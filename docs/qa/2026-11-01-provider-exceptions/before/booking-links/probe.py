"""Synthetic booking-link and configured-course audit. No external handoffs."""
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path('/workspace/golfhub-20261031')
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]

with tempfile.TemporaryDirectory(prefix='golfhub-booking-links-') as runtime:
    os.environ.update(QT_QPA_PLATFORM='offscreen', LOCALAPPDATA=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtWidgets import QApplication, QPushButton
    from app import golfhub_core as core
    from app.course_results import direct_result
    from app.qt_golfhub_app import GolfHub, ResultCard, DirectCourseCard
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    checks, callback_errors = [], []
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect',
                       'app.qt_golfhub_app.CacheWorker', 'app.qt_golfhub_app.ScanWorker'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline diagnostic')))
        browser = stack.enter_context(patch('webbrowser.open', return_value=True))
        stack.enter_context(patch('sys.excepthook', side_effect=lambda *a: callback_errors.append(str(a[1]))))
        stack.enter_context(patch.object(core, 'get_weather_for_date', return_value=None))
        stack.enter_context(patch.object(core, 'fetch_site_text', side_effect=RuntimeError('Synthetic provider failure')))
        stack.enter_context(patch.object(core, 'fetch_text', side_effect=RuntimeError('Synthetic calendar failure')))
        sites = core.load_sites(core.DATA_DIR/core.CONFIG_FILE)
        base = date(2033,1,1)
        dates = [(base+timedelta(days=(weekday-base.weekday())%7)).isoformat() for weekday in (0,5)]
        for day in dates:
            for site in sites:
                for holes in site.holes:
                    result = (direct_result(site, holes) if site.provider == 'direct' else
                              core.fetch_site_result(site, day, holes, None, None, None))
                    target = result.get('url')
                    parsed = urlparse(target or '')
                    card = (DirectCourseCard(result, date_str=day) if site.provider == 'direct' else
                            ResultCard(result, [], date_str=day))
                    browser.reset_mock()
                    button = card.findChild(QPushButton)
                    button.click()
                    actual = [call.args[0] for call in browser.call_args_list]
                    checks.append({'scenario':'configured card handoff', 'site':site.name,
                                   'holes':holes, 'date':day, 'provider':site.provider,
                                   'target':target, 'button':button.text(),
                                   'pass':bool(parsed.scheme == 'https' and parsed.netloc and actual == [target])})
                    card.deleteLater()
        with patch.object(GolfHub,'show_initial_cache'):
            window=GolfHub()
        window._stop_deferred_timers()
        for holes, button in (('18',window.holes18),('9',window.holes9)):
            button.setChecked(True)
            actual=sorted(s.name for s in window.selected_sites())
            expected=sorted(s.name for s in sites if holes in s.holes)
            checks.append({'scenario':'unsupported rounds excluded before request', 'holes':holes,
                           'selected_count':len(actual), 'pass':actual==expected})
        window.context={'players':None}
        for source, fallback, expected in (
            ('https://example.invalid/row','https://example.invalid/course','https://example.invalid/row'),
            (None,'https://example.invalid/course','https://example.invalid/course'),
            (None,None,None),
        ):
            browser.reset_mock()
            with patch('app.qt_golfhub_app.QMessageBox.information') as info:
                window.open_tee_time({'site_name':'Araluen','url':fallback},{'time':'9:00 am','source_url':source})
            actual=[call.args[0] for call in browser.call_args_list]
            explained_missing=(info.call_count==1 and info.call_args.args[1]=='Booking page unavailable') if expected is None else not info.called
            checks.append({'scenario':'row handoff fallback or missing-link explanation', 'row_url':source,
                           'course_url':fallback, 'actual':actual,
                           'pass':actual==([] if expected is None else [expected]) and explained_missing})
        report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                                 ('app/golfhub_core.py','app/qt_golfhub_app.py','data/courses.json')},
                'scope':'Linux offscreen, configured sites, synthetic provider failures and intercepted browser handoffs; no provider access, live bookings, holds, or native-device validation',
                'sites':len(sites),'checks':checks,'callback_errors':callback_errors}
        (OUT/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
        cleanup_qt_widgets()
        print(json.dumps({'sites':len(sites),'checks':len(checks),'passed':sum(c['pass'] for c in checks),'callback_errors':callback_errors}))
        assert all(c['pass'] for c in checks)
        assert not callback_errors
