"""Offline provider-error presentation evidence on an explicit source tree."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
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
with tempfile.TemporaryDirectory(prefix="golfhub-provider-errors-probe-") as runtime:
    os.environ.update(QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
                      XDG_CACHE_HOME=runtime, TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
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
        sites = {s.name: s for s in window.sites}
        live, collier, wembley = (sites[name] for name in ("Araluen", "Collier Park", "Wembley"))
        dates = ["2033-01-02", "2033-01-03"]
        def context(selected, multiple=False):
            selected_dates = dates if multiple else dates[:1]
            window.date.set_dates([QDate.fromString(d, "yyyy-MM-dd") for d in selected_dates])
            window.context = dict(sites=selected, date=dates[0], dates=selected_dates,
                                  holes="18", players=None, **{"from": None, "to": None})
        def result(site, rows=(), **extra):
            return {"site_name": site.name, "url": "https://example.invalid/booking",
                    "hole_label": "18 holes", "weather": None, "error": None,
                    "decorated_rows": list(rows), **extra}
        def payload(*results):
            return {"generated_at": "2033-01-02T00:00:00Z", "results": list(results)}
        def capture():
            layout_passes = []
            for pass_number in range(1, 4):
                app.processEvents()
                labels = []
                for label in window.results_body.findChildren(QLabel):
                    origin = label.mapTo(window.results_body, label.rect().topLeft())
                    labels.append({"name": label.objectName(), "text": label.text(),
                                   "x": origin.x(), "y": origin.y(),
                                   "width": label.width(), "height": label.height(),
                                   "size_hint_height": label.sizeHint().height(),
                                   "height_for_width": label.heightForWidth(label.width())})
                layout_passes.append({"pass": pass_number, "body_height": window.results_body.height(),
                                      "scroll_maximum": window.results_scroll.verticalScrollBar().maximum(),
                                      "labels": labels})
            summary = window.findChild(QLabel, "SummaryValue")
            return {
                "layout_passes": layout_passes,
                "summary": summary.text() if summary else None,
                "status": window.status.text(), "header": window.header_status.text(),
                "labels": [label.text() for label in window.results_body.findChildren(QLabel)],
                "buttons": [{"text": b.text(), "name": b.accessibleName()}
                            for b in window.results_body.findChildren(QPushButton)],
                "exact_time_cards": len(window.findChildren(TeeTimeCard)),
                "cards": [{"site": card.result["site_name"],
                           "labels": [label.text() for label in card.findChildren(QLabel)]}
                          for card in window.findChildren(ResultCard)],
            }
        row = {"time": "9:00 am", "minutes": 540, "spots": 4}
        failure = result(live, error="Synthetic provider failure")
        evidence = {}
        for name, selected, results in (
            ("single-error", [live], [failure]),
            ("collier-error", [collier], [result(collier, error="Synthetic provider failure")]),
            ("mixed-empty-error", [live, collier], [failure, result(collier)]),
            ("mixed-row-error", [live, collier], [failure, result(collier, [row])]),
            ("available-calendar-error", [live, wembley], [failure, result(wembley, calendar_availability="available")]),
            ("unreleased-calendar-error", [live, wembley], [failure, result(wembley, calendar_availability="unreleased")]),
        ):
            context(selected)
            window.render_snapshot(payload(*results), "Shared cache")
            evidence[name] = capture()
            if name in {"single-error", "collier-error"}:
                assert window.grab().save(str(output / f"{name}.png"))
        context([live], multiple=True)
        snapshots = {date: payload(failure) for date in dates}
        window.render_snapshot_batch(snapshots, {date: "Shared cache" for date in dates})
        evidence["multiday-all-error"] = capture()
        evidence["multiday-all-error"]["days"] = [
            {"date": section.date_str, "title": section.toggle.text(), "built": section._built}
            for section in window.day_sections]
        assert window.grab().save(str(output / "multiday-all-error.png"))
        window.render_snapshot_batch({dates[0]: payload(failure)}, {dates[0]: "Shared cache"})
        evidence["error-and-missing-date"] = capture()
        evidence["error-and-missing-date"]["days"] = [section.toggle.text() for section in window.day_sections]
        context([live])
        with patch("app.qt_golfhub_app.load_local_snapshot", return_value=payload(failure)), \
                patch.object(window, "search_live") as live_search:
            window.cache_finished({})
            assert not live_search.called
        evidence["saved-error-fallback"] = capture()
        evidence["callback_errors"] = errors
        evidence["provenance"] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "source_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True),
            "source_sha256": hashlib.sha256((root / "app/qt_golfhub_app.py").read_bytes()).hexdigest(),
            "kind": "Linux offscreen; synthetic shared/saved results; sockets/browser blocked; no workers",
            "logical_window": [1280, 800],
        }
        (output / "probe.json").write_text(json.dumps(evidence, indent=2) + "\n")
        cleanup_qt_widgets()
        print(json.dumps(evidence, indent=2))
        assert not errors
