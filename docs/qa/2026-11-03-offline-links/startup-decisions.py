"""Five offline startup/fallback decisions; scheduled and live work is intercepted."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import traceback
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, output = args.root.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / "tests")]
source_path = root / "app/qt_golfhub_app.py"
source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
report = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "source_sha256": source_hash,
    "kind": "Five diagnostic scenarios, not unit tests; actual startup/callback methods with synthetic saved data and intercepted scheduled/live work",
    "python": platform.python_version(),
    "platform": platform.platform(),
    "scenarios": [],
    "callback_errors": [],
}
with tempfile.TemporaryDirectory(prefix="golfhub-startup-decisions-") as runtime:
    os.environ.update(QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
                      XDG_CACHE_HOME=runtime, TEMP=runtime, TMP=runtime)
    import PySide6
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel
    from app.qt_golfhub_app import GolfHub
    from tests.qt_test_support import cleanup_qt_widgets
    report["qt"] = PySide6.__version__
    app = QApplication.instance() or QApplication([])
    with ExitStack() as guards:
        for target in ("socket.create_connection", "socket.socket.connect",
                       "socket.socket.connect_ex", "socket.getaddrinfo", "webbrowser.open"):
            guards.enter_context(patch(target, side_effect=AssertionError("Offline startup QA")))
        guards.enter_context(patch("app.qt_golfhub_app.save_local_snapshot",
                                   side_effect=AssertionError("Startup probe must not save")))
        guards.enter_context(patch("app.qt_golfhub_app.perth_today", return_value=QDate(2033, 1, 2)))
        guards.enter_context(patch("sys.excepthook", side_effect=lambda *a: report["callback_errors"].append(str(a[1]))))
        for scenario in ("startup-no-saved-data", "startup-saved-empty", "startup-saved-error",
                         "single-date-missing-cache", "multi-date-missing-cache"):
            record = {"name": scenario, "passed": False}
            report["scenarios"].append(record)
            try:
                # Prevent the constructor's queued callback; invoke the real
                # method explicitly below after installing decision guards.
                with patch.object(GolfHub, "show_initial_cache"):
                    window = GolfHub()
                window._stop_deferred_timers()
                site = next(s for s in window.sites if s.provider != "direct" and "18" in s.holes)
                window.set_all(False)
                next(r for r in window.course_rows if r.site.name == site.name).check.setChecked(True)
                window.date.setDate(QDate(2033, 1, 2))
                submitted = window.params()
                payload = None
                if scenario in ("startup-saved-empty", "startup-saved-error"):
                    payload = {
                        "schema": 1, "date": submitted["date"], "holes": submitted["holes"],
                        "generated_at": "2033-01-02T00:00:00Z", "results": [{
                            "site_name": site.name, "url": "https://example.invalid/booking",
                            "hole_label": "18 holes", "decorated_rows": [], "weather": None,
                            "error": "Synthetic provider failure" if scenario.endswith("error") else None,
                        }],
                    }
                with patch("app.qt_golfhub_app.load_local_snapshot", return_value=payload) as local, \
                        patch.object(window._cache_search_timer, "start") as schedule, \
                        patch.object(window, "_start_cache_search", side_effect=AssertionError("No cache worker")) as worker, \
                        patch.object(window, "search_live") as live:
                    if scenario.startswith("startup-"):
                        window.show_initial_cache()
                        local.assert_called_once_with(submitted["date"], submitted["holes"])
                        schedule.assert_called_once_with(100)
                        live.assert_not_called()
                        if payload:
                            assert window.context == submitted
                            assert window.header_status.text().startswith("SAVED CACHE / ")
                        else:
                            assert window.context == {}
                            assert any("Choose a date" in label.text()
                                       for label in window.results_body.findChildren(QLabel))
                    else:
                        if scenario.startswith("multi-"):
                            submitted["dates"] = [submitted["date"], "2033-01-04"]
                        window.context = submitted
                        window._active_cache_context = submitted
                        # Editing controls must not rewrite the submitted date
                        # used for a single-date cache-to-live fallback.
                        window.date.setDate(QDate(2033, 1, 3))
                        window.cache_finished({})
                        schedule.assert_not_called()
                        assert [call.args for call in local.call_args_list] == [
                            (date, submitted["holes"]) for date in submitted["dates"]]
                        if scenario.startswith("single-"):
                            live.assert_called_once_with(submitted)
                            assert live.call_args.args[0]["date"] == "2033-01-02"
                        else:
                            live.assert_not_called()
                            assert window.status.text() == "Multi-day cache temporarily unavailable"
                            assert window.header_status.text() == "SHARED CACHE UNAVAILABLE"
                            labels = [label.text() for label in window.results_body.findChildren(QLabel)]
                            assert any("No cached results were available" in text for text in labels)
                            assert not any("0 matching" in text for text in labels)
                    worker.assert_not_called()
                    assert window.cache_thread is None and window.scan_thread is None
                    summary = window.results_body.findChild(QLabel, "SummaryValue")
                    record.update(
                        passed=True, saved_payload=payload is not None,
                        scheduled_cache_delay_ms=[call.args[0] for call in schedule.call_args_list],
                        live_fallback_calls=live.call_count,
                        local_requests=[list(call.args) for call in local.call_args_list],
                        submitted_dates=list(submitted["dates"]),
                        live_fallback_date=live.call_args.args[0]["date"] if live.called else None,
                        summary=summary.text() if summary else None,
                        status=window.status.text(), header=window.header_status.text(),
                        labels=[label.text() for label in window.results_body.findChildren(QLabel)],
                        cache_worker_calls=worker.call_count,
                    )
            except Exception:
                record["failure"] = traceback.format_exc()
            finally:
                cleanup_qt_widgets()
            print(json.dumps(record), flush=True)
report["source_unchanged_during_run"] = hashlib.sha256(source_path.read_bytes()).hexdigest() == source_hash
report["passed"] = (all(item["passed"] for item in report["scenarios"])
                    and not report["callback_errors"] and report["source_unchanged_during_run"])
(output / "startup-decisions.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"{'PASS' if report['passed'] else 'FAIL'}: {sum(s['passed'] for s in report['scenarios'])}/5 diagnostic scenarios; no actual scheduled/live workers")
sys.exit(not report["passed"])
