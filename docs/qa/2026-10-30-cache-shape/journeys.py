"""Offline control submission/rendering matrix; worker launch is intercepted."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parents[3]
out = Path(__file__).resolve().parent
sys.path[:0] = [str(root), str(root / "tests")]
with tempfile.TemporaryDirectory(prefix="golfhub-oct30-journeys-") as runtime:
    os.environ.update(QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
                      TEMP=runtime, TMP=runtime)
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from app.qt_golfhub_app import GolfHub, TeeTimeCard
    from tests.qt_test_support import cleanup_qt_widgets
    app = QApplication.instance() or QApplication([])
    errors, checks = [], []
    with ExitStack() as stack:
        for target in ("socket.create_connection", "socket.socket.connect", "webbrowser.open"):
            stack.enter_context(patch(target, side_effect=AssertionError("Offline QA")))
        stack.enter_context(patch.object(GolfHub, "show_initial_cache"))
        stack.enter_context(patch("app.qt_golfhub_app.load_local_snapshot", return_value=None))
        stack.enter_context(patch("sys.excepthook", side_effect=lambda *a: errors.append(str(a[1]))))
        window = GolfHub()
        window._stop_deferred_timers()
        window.resize(980, 640)
        window.show()
        app.processEvents()
        site = next(s for s in window.sites if s.provider != "direct" and {"9", "18"} <= set(s.holes))
        window.set_all(False)
        next(r for r in window.course_rows if r.site.name == site.name).check.setChecked(True)
        dates = [window.date.minimumDate().addDays(n) for n in (0, 2, 5)]
        window.date.set_dates(dates)
        submitted_dates = [d.toString("yyyy-MM-dd") for d in dates]
        rows = [{"time": f"{minute // 60 % 12 or 12}:{minute % 60:02d} {'am' if minute < 720 else 'pm'}",
                 "minutes": minute, "spots": spots}
                for minute in (359, 360, 540, 690, 720, 840, 870, 900, 1110, 1111)
                for spots in (1, 2, 3, 4)]
        def submit(context):
            window.context = context
            window._active_cache_context = context
            result = {"site_name": site.name, "url": "https://example.invalid/booking",
                      "hole_label": f"{context['holes']} holes", "weather": None,
                      "error": None, "decorated_rows": rows}
            payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "results": [result]}
            window.cache_finished({submitted_dates[0]: payload})
        stack.enter_context(patch.object(window, "_start_cache_search", side_effect=submit))
        presets = {"Any time": (None, None), "Morning": (360, 690),
                   "Midday": (720, 870), "Afternoon": (900, 1110), "Custom range": (540, 840)}
        for holes, button in (("18", window.holes18), ("9", window.holes9)):
            QTest.mouseClick(button, Qt.LeftButton)
            for players in (None, 1, 2, 3, 4):
                window.players.setCurrentText("Any" if players is None else str(players))
                for preset, (low, high) in presets.items():
                    window.time_preset.setCurrentText(preset)
                    if preset == "Custom range":
                        window.time_from.setCurrentText("9:00 am")
                        window.time_to.setCurrentText("2:00 pm")
                    QTest.mouseClick(window.search_button, Qt.LeftButton)
                    app.processEvents()
                    expected = [(r["minutes"], r["spots"]) for r in rows
                                if (players is None or r["spots"] >= players)
                                and (low is None or r["minutes"] >= low)
                                and (high is None or r["minutes"] <= high)]
                    actual = [(c.row["minutes"], c.row["spots"]) for c in window.findChildren(TeeTimeCard)]
                    assert actual == expected, (holes, players, preset, actual, expected)
                    assert window.context["holes"] == holes
                    assert window.context["dates"] == submitted_dates
                    assert "1 loaded day" in window.findChild(QLabel, "SummaryValue").text()
                    assert "Availability not checked" in window.day_sections[1].toggle.text()
                    checks.append({"holes": holes, "players": players, "preset": preset,
                                   "matching_rows": len(expected), "passed": True})
        window.day_sections[1].set_expanded(True)
        window.day_sections[0].set_expanded(False)
        app.processEvents()
        note = window.day_sections[1].body.findChild(QLabel)
        window.results_scroll.ensureWidgetVisible(note)
        app.processEvents()
        assert note.isVisible() and note.height() >= note.heightForWidth(note.width())
        assert window.grab().save(str(out / "compact-980x640.png"))
        cleanup_qt_widgets()
        assert not errors, errors
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "kind": "50 source-widget submission/rendering combinations; intercepted worker launch, synthetic partial cache; no native/device or live-provider test",
              "logical_window": [980, 640], "scale_factor": 1,
              "checks": checks, "callback_errors": errors}
    (out / "journeys.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {len(checks)} control/rendering combinations; compact recovery note fits; zero callback errors")
