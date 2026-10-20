"""Read-only offscreen fixture; run from the source checkout being inspected."""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd()))

from PySide6.QtCore import QDate, QPoint
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.qt_golfhub_app import GolfHub
from tests.qt_test_support import cleanup_qt_widgets

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--tag", required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
app = QApplication([])
with (
    patch.object(GolfHub, "show_initial_cache"),
    patch("socket.create_connection", side_effect=AssertionError("Offline probe")),
    patch("socket.socket.connect", side_effect=AssertionError("Offline probe")),
    patch("app.qt_golfhub_app.webbrowser.open"),
    patch("app.qt_golfhub_app.save_local_snapshot"),
):
    window = GolfHub()
    window._stop_deferred_timers()
    window.date.setDate(QDate(2026, 10, 20))
    window.time_preset.setCurrentText("Custom range")
    window.time_from.setCurrentText("9:00 am")
    window.time_to.setCurrentText("3:00 pm")
    window.context = dict(window.params(), date="2026-10-20", dates=["2026-10-20"])
    result = {
        "site_name": "Araluen", "hole_label": "18 holes",
        "url": "https://example.invalid/course", "weather": None,
        "decorated_rows": [{"time": "10:00 am", "minutes": 600, "spots": 4,
                            "source_url": "https://example.invalid/time"}],
    }
    window.render_results([result], "Offline synthetic fixture")
    window.resize(980, 640)
    window.show()
    app.processEvents()
    controls = []
    for combo in (window.time_from, window.time_to):
        interface = QAccessible.queryAccessibleInterface(combo)
        label_relations = [related.object().text() for related, _ in interface.relations(QAccessible.RelationFlag.Label)
                           if isinstance(related.object(), QLabel)]
        pos = combo.mapTo(window, QPoint(0, 0))
        controls.append({"name_property": combo.accessibleName(),
                         "interface_name": interface.text(QAccessible.Name),
                         "visible_label_relations": label_relations,
                         "geometry": [pos.x(), pos.y(), combo.width(), combo.height()],
                         "inside_window": 0 <= pos.x() and pos.x() + combo.width() <= window.width()
                         and 0 <= pos.y() and pos.y() + combo.height() <= window.height()})
    actions = [{"visible": button.text(), "name_property": button.accessibleName(),
                "interface_name": QAccessible.queryAccessibleInterface(button).text(QAccessible.Name)}
               for button in window.results_body.findChildren(QPushButton)]
    evidence = {"kind": "Linux Qt offscreen synthetic source widgets; no native or screen-reader test",
                "window_size": [window.width(), window.height()], "controls": controls, "actions": actions}
    (args.output / f"booking-context-{args.tag}.json").write_text(json.dumps(evidence, indent=2) + "\n")
    window.grab().save(str(args.output / f"booking-context-{args.tag}.png"))
    cleanup_qt_widgets()
