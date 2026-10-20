"""Offline Qt journey smoke test and screenshots; never opens booking sites.

Run from the repository: python scripts/qa_desktop_smoke.py --output <directory>
Requires the desktop requirements. This tests source widgets, not an installer.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--synchronous-cache", action="store_true", help="Bypass Qt worker lifecycle; test controls and rendering only")
    parser.add_argument("--retain-worker-wrappers", action="store_true", help="Diagnostic experiment only")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["LOCALAPPDATA"] = f"/tmp/golfhub-smoke-{args.phase}-runtime"
    os.environ["XDG_CACHE_HOME"] = f"/tmp/golfhub-smoke-{args.phase}-fontcache"
    sys.path.insert(0, str(args.root.resolve()))

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QAccessible, QFont, QFontDatabase
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton
    from app.qt_golfhub_app import GolfHub, ResultCard, TeeTimeCard
    from tests.qt_test_support import cleanup_qt_widgets

    app = QApplication.instance() or QApplication([])
    # Windows' offscreen plugin may not discover system fonts automatically.
    for name in ("segoeui.ttf", "segoeuib.ttf"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Segoe UI", 10))
    checks = []
    report = {"kind": "offscreen Qt widgets with synthetic data", "phase": args.phase, "retains_completed_worker_wrappers": args.retain_worker_wrappers, "synchronous_cache_fixture": args.synchronous_cache, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(), "platform": platform.platform(), "source_sha256": hashlib.sha256((args.root / "app/qt_golfhub_app.py").read_bytes()).hexdigest(), "checks": checks}
    callback_errors = []

    def capture_callback_error(kind, value, tb):
        callback_errors.append("".join(traceback.format_exception(kind, value, tb)))


    def record(name, **evidence):
        checks.append({"name": name, "passed": True, **evidence})

    def screenshot(window, name):
        app.processEvents()
        if args.phase.startswith("after") and name in ("results-980x640.png", "results-1280x800.png"):
            assert window.grab().save(str(output / ("journey-" + name)))

    with ExitStack() as stack:
        stack.enter_context(patch("sys.excepthook", capture_callback_error))
        stack.enter_context(patch("socket.create_connection", side_effect=AssertionError("QA is offline")))
        stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("QA is offline")))
        browser = stack.enter_context(patch("app.qt_golfhub_app.webbrowser.open"))
        local = stack.enter_context(patch("app.qt_golfhub_app.load_local_snapshot", return_value=None))
        stack.enter_context(patch("app.qt_golfhub_app.save_local_snapshot"))
        stack.enter_context(patch.object(GolfHub, "show_initial_cache"))
        window = GolfHub()
        window._stop_deferred_timers()
        try:
            window.resize(1280, 800)
            window.show()
            app.processEvents()
            screenshot(window, "first-launch.png")
            assert "Choose a date" in " ".join(x.text() for x in window.findChildren(QLabel))
            record("first launch", courses=len(window.sites), default_dates=window.selected_dates())

            site = next(s for s in window.sites if s.provider != "direct" and "18" in s.holes and "9" in s.holes)
            window.set_all(False)
            row = next(r for r in window.course_rows if r.site.name == site.name)
            row.check.setChecked(True)
            window.course_panel.show()
            window.course_search.setFocus()
            QTest.keyClicks(window.course_search, site.name)
            app.processEvents()
            assert [r.site.name for r in window.course_rows if not r.isHidden()] == [site.name]
            record("course name search", visible_courses=[site.name])
            window.course_search.clear()
            window.course_panel.hide()
            day = window.selected_dates()[0]
            url = site.build_url(day, "18")
            result = {
                "site_name": site.name, "url": url, "hole_label": "18 holes", "error": None,
                "weather": {"label": "Clear", "tmin": 12, "tmax": 24, "rain_chance": 10, "wind": 15},
                "decorated_rows": [
                    {"time": "9:00 am", "minutes": 540, "spots": 2, "source_url": url},
                    {"time": "10:00 am", "minutes": 600, "spots": 4, "source_url": url},
                    {"time": "3:00 pm", "minutes": 900, "spots": 4, "source_url": url},
                ],
            }

            def snapshot(date, holes):
                course_url = site.build_url(date, holes)
                return {"schema": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
                        "date": date, "holes": holes, "results": [{
                            **result, "hole_label": f"{holes} holes", "url": course_url,
                            "decorated_rows": [{**row, "source_url": course_url} for row in result["decorated_rows"]],
                        }]}

            shared = stack.enter_context(patch("app.qt_golfhub_app.fetch_shared_snapshot", side_effect=snapshot))

            retained_workers = []
            # Optional diagnostic experiment. Initial before/after worker crashes
            # are retained as evidence; wrapper retention did not resolve the stall.
            if args.synchronous_cache:
                def deliver_snapshot(p):
                    window._active_cache_context = p
                    window.context = p
                    window.cache_finished({day: shared(day, p["holes"]) for day in p["dates"]})
                    window.cache_thread_done()
                stack.enter_context(patch.object(window, "_start_cache_search", side_effect=deliver_snapshot))
            def search():
                QTest.mouseClick(window.search_button, Qt.LeftButton)
                if args.retain_worker_wrappers:
                    retained_workers.append((window.cache_thread, window.cache_worker))
                deadline = time.monotonic() + 5
                while window.cache_thread is not None and time.monotonic() < deadline:
                    app.processEvents()
                    QTest.qWait(10)
                assert window.cache_thread is None, "Cache worker did not complete"
                app.processEvents()

            search()
            assert len(window.findChildren(TeeTimeCard)) == 3
            assert "less than a minute" in " ".join(x.text() for x in window.findChildren(QLabel))
            record("cache search and course card", displayed_times=3, source="synthetic shared cache")
            QTest.mouseClick(window.findChildren(TeeTimeCard)[0].findChild(QPushButton), Qt.LeftButton)
            browser.assert_called_once_with(url)
            record("booking handoff", intercepted_url=url, actual_navigation=False)

            window.players.setCurrentText("4")
            window.time_preset.setCurrentText("Morning")
            search()
            assert [c.row["minutes"] for c in window.findChildren(TeeTimeCard)] == [600]
            screenshot(window, "filtered-results.png")
            record("group and time filters", minutes=[600], spots=[4])
            filter_matrix = []
            preset_minutes = {"Any time": [540, 600, 900], "Morning": [540, 600], "Midday": [], "Afternoon": [900], "Custom range": [540, 600]}
            for players in ("Any", "1", "2", "3", "4"):
                window.players.setCurrentText(players)
                for preset, expected_minutes in preset_minutes.items():
                    window.time_preset.setCurrentText(preset)
                    if preset == "Custom range":
                        window.time_from.setCurrentText("9:00 am")
                        window.time_to.setCurrentText("10:00 am")
                    window.context = window.params()
                    actual = [r["minutes"] for r in window.filtered_rows(result["decorated_rows"])]
                    expected = [n for n in expected_minutes if players in ("Any", "1", "2") or n != 540]
                    assert actual == expected, (players, preset, actual, expected)
                    filter_matrix.append({"players": players, "preset": preset, "minutes": actual})
            record("all player and time choices", combinations=filter_matrix)
            window.players.setCurrentText("4")
            window.time_preset.setCurrentText("Morning")
            QTest.mouseClick(window.holes9, Qt.LeftButton)
            search()
            assert shared.call_args.args[1] == "9"
            assert window.findChildren(TeeTimeCard)[0].url == site.build_url(day, "9")
            record("9-hole search", requested_round=window.context["holes"])

            dates = [window.date.minimumDate(), window.date.minimumDate().addDays(2)]
            window.date.set_dates(dates)
            search()
            assert len(window.day_sections) == 2 and not window.live_button.isEnabled()
            record("nonconsecutive dates", dates=window.selected_dates(), live_disabled=True)
            full_window = [window.date.minimumDate().addDays(i) for i in range(28)]
            window.date.set_dates(full_window)
            search()
            assert len(window.day_sections) == 28 and not window.live_button.isEnabled()
            assert sum(section._built for section in window.day_sections) == 1
            window.day_sections[-1].set_expanded(True)
            app.processEvents()
            assert window.day_sections[-1]._built
            assert sum(section._built for section in window.day_sections) == 2
            record("full 28-day window and lazy expansion", dates=window.selected_dates(), initially_built=1, built_after_last_open=2)
            window.date.set_dates(dates)
            shared.side_effect = None
            shared.return_value = None
            search()
            assert window.header_status.text() == "SHARED CACHE UNAVAILABLE"
            screenshot(window, "offline-multiday.png")
            record("offline without saved data", status=window.status.text())

            window.date.set_dates([dates[0]])
            local.side_effect = snapshot
            search()
            assert window.header_status.text().startswith("SAVED CACHE")
            record("offline with saved data", status=window.header_status.text())
            local.side_effect = None
            window.context = window.params()
            result = snapshot(window.context["date"], window.context["holes"])["results"][0]
            window.render_results([{**result, "decorated_rows": [], "weather": None, "error": "fixture failure"}], "QA fixture")
            assert "Live times were unavailable" in " ".join(x.text() for x in window.findChildren(QLabel))
            assert "Forecast unavailable" in " ".join(x.text() for x in window.findChildren(QLabel))
            record("provider error and unavailable weather", booking_button_available=True)
            window.render_results([{**result, "decorated_rows": []}], "QA fixture")
            assert "Try Any time" in " ".join(x.text() for x in window.findChildren(QLabel))
            record("empty filtered results", recovery_copy_present=True)

            window.time_preset.setCurrentText("Custom range")
            window.time_from.setCurrentText("3:00 pm")
            window.time_to.setCurrentText("9:00 am")
            window.render_empty("QA fixture: previous results remain until a valid search.")
            captured = []

            def close_validation_dialog():
                dialog = app.activeModalWidget()
                if isinstance(dialog, QMessageBox):
                    captured.append(dialog.text())
                    screenshot(dialog, "after-range-message.png")
                    screenshot(window, "after-range-window.png")
                    dialog.accept()

            QTimer.singleShot(30, close_validation_dialog)
            params = window.params()
            app.processEvents()
            assert params is None and captured, "Reversed time range must be rejected"
            assert window.focusWidget() is window.time_to, "Return focus to the end time for correction"
            record("invalid time range", message=captured[0], focus="End time", no_search_started=True)
            window.time_from.setCurrentText("9:00 am")
            window.time_to.setCurrentText("3:00 pm")
            window.context = window.params()
            window.render_results([result], "QA fixture")
            assert len(window.findChildren(TeeTimeCard)) == 2
            record("corrected time range", matching_times=2)
            for width, height in ((980, 640), (1280, 800), (1600, 1000)):
                window.resize(width, height)
                screenshot(window, f"results-{width}x{height}.png")
                assert window.search_button.isVisible() and window.live_button.isVisible()
                record("resize", requested=[width, height], actual=[window.width(), window.height()])
            report["accessibility"] = {
                key: QAccessible.queryAccessibleInterface(widget).text(QAccessible.Name)
                for key, widget in (("start_time", window.time_from), ("end_time", window.time_to),
                                    ("players", window.players), ("course_checkbox", row.check))
            }
            report["limitations"] = ["No native desktop driver, screen reader, installer, or Android test.",
                                      "Provider/cache/weather data mocked; no live availability claim."]
        finally:
            cleanup_qt_widgets()
    report["callback_errors"] = {"count": len(callback_errors), "distinct": sorted(set(callback_errors))}
    report["status"] = "completed_with_known_findings" if callback_errors else "passed"
    (output / f"journey-smoke-{args.phase}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if any("toggled() only accepts 0 argument(s), 1 given!" not in error for error in callback_errors):
        raise SystemExit("Unexpected Qt callback error; inspect smoke-report.json")


if __name__ == "__main__":
    main()
