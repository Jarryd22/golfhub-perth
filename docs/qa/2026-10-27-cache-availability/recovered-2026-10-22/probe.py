"""Offline partial-cache rendering evidence on a specified source checkout."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, output = args.root.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(root), str(root / "tests")]
with tempfile.TemporaryDirectory(prefix="golfhub-availability-probe-") as runtime:
    os.environ.update(QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
                      XDG_CACHE_HOME=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel
    from app.qt_golfhub_app import GolfHub, ResultCard, TeeTimeCard
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    errors = []
    with ExitStack() as stack:
        for target in ("socket.create_connection", "socket.socket.connect", "webbrowser.open"):
            stack.enter_context(patch(target, side_effect=AssertionError("Offline QA")))
        stack.enter_context(patch("sys.excepthook", side_effect=lambda *a: errors.append(str(a[1]))))
        stack.enter_context(patch("app.qt_golfhub_app.perth_today", return_value=QDate(2033, 1, 2)))
        stack.enter_context(patch.object(GolfHub, "show_initial_cache"))
        window = GolfHub()
        window._stop_deferred_timers()
        window.resize(1280, 800)
        window.show()
        site = next(s for s in window.sites if s.provider != "direct" and "18" in s.holes)
        dates = ["2033-01-02", "2033-01-03", "2033-01-04"]
        window.date.set_dates([QDate.fromString(d, "yyyy-MM-dd") for d in dates])
        window.context = dict(sites=[site], date=dates[0], dates=dates, holes="18",
                              players=4, **{"from": 540, "to": 720})
        def payload(rows):
            return {"generated_at": "2033-01-02T00:00:00Z", "results": [{
                "site_name": site.name, "url": "https://example.invalid/booking",
                "hole_label": "18 holes", "error": None, "weather": None,
                "decorated_rows": rows}]}
        evidence = {}
        for scenario, rows in (("empty", []), ("matches", [{
                "time": "10:00 am", "minutes": 600, "spots": 4}])):
            window.render_snapshot_batch(
                {dates[0]: payload([]), dates[2]: payload(rows)},
                {dates[0]: "Shared cache", dates[2]: "Saved on this device"})
            for section in window.day_sections:
                section.set_expanded(section.date_str == dates[1])
            app.processEvents()
            evidence[scenario] = {
                "summary": window.findChild(QLabel, "SummaryValue").text(),
                "status": window.status.text(), "header": window.header_status.text(),
                "days": [{"date": s.date_str, "title": s.toggle.text(), "built": s._built,
                          "body": [x.text() for x in s.body.findChildren(QLabel)]}
                         for s in window.day_sections],
                "result_cards": len(window.findChildren(ResultCard)),
                "time_cards": len(window.findChildren(TeeTimeCard)),
            }
            assert window.grab().save(str(output / f"{scenario}.png"))
        evidence["callback_errors"] = errors
        evidence["kind"] = "Linux offscreen; synthetic partial cache; sockets/browser blocked; no workers"
        (output / "probe.json").write_text(json.dumps(evidence, indent=2) + "\n")
        cleanup_qt_widgets()
        print(json.dumps(evidence, indent=2))
        assert not errors
