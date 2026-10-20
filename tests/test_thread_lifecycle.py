"""Real Qt worker lifecycle regressions, isolated so native crashes fail a test.

Every scenario runs with socket/browser calls blocked and synthetic cache/live
fetches. Event gates hold work until the test has observed the active objects;
no retries turn a crash into a pass. Set GOLFHUB_LIFECYCLE_SOURCE_ROOT only when
comparing this exact test harness against an untouched source checkout.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest


class ThreadLifecycleTests(unittest.TestCase):
    def run_scenario(self, name):
        root = Path(os.environ.get("GOLFHUB_LIFECYCLE_SOURCE_ROOT", Path(__file__).resolve().parents[1])).resolve()
        with tempfile.TemporaryDirectory(prefix="golfhub-thread-test-") as runtime:
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=runtime,
                       XDG_CACHE_HOME=runtime, TMP=runtime, TEMP=runtime,
                       PYTHONUNBUFFERED="1")
            command = [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()),
                       "--scenario", name, "--root", str(root)]
            try:
                result = subprocess.run(command, cwd=root, env=env, text=True,
                                        capture_output=True, timeout=30)
            except subprocess.TimeoutExpired as exc:
                self.fail(f"{name} exceeded 30 seconds; real worker lifecycle stalled.\n{exc.stdout}\n{exc.stderr}")
            self.assertEqual(result.returncode, 0,
                             f"{name} process exited {result.returncode}\n{result.stdout}\n{result.stderr}")
            lines = [line for line in result.stdout.splitlines() if line.startswith("LIFECYCLE_RESULT ")]
            self.assertEqual(len(lines), 1, result.stdout + result.stderr)
            evidence = json.loads(lines[0].split(" ", 1)[1])
            self.assertEqual(evidence["scenario"], name)
            self.assertEqual(evidence["worker_destroyed"], evidence["thread_destroyed"])
            self.assertGreater(evidence["thread_destroyed"], 0)
            self.assertEqual(evidence["callback_errors"], [])
            expected_checks = ["cache" if name.startswith("cache_") else "scan"] if "_finish_" in name else []
            self.assertEqual(evidence["native_finish_checks"], expected_checks)

    def test_repeated_cache_searches_release_workers_and_threads(self):
        self.run_scenario("cache_sequence")

    def test_latest_queued_search_runs_after_old_thread_finishes(self):
        self.run_scenario("cache_queue")

    def test_close_during_cache_work_does_not_launch_queued_search(self):
        self.run_scenario("cache_close")

    def test_live_success_releases_worker_and_thread(self):
        self.run_scenario("live_success")

    def test_live_failure_releases_worker_and_preserves_cache(self):
        self.run_scenario("live_failure")

    def test_live_cancel_releases_worker_without_saving_partial_data(self):
        self.run_scenario("live_cancel")

    def test_cache_cleanup_waits_for_native_finish_before_starting_latest_search(self):
        self.run_scenario("cache_finish_queue")

    def test_close_during_native_cache_cleanup_waits_and_discards_queued_search(self):
        self.run_scenario("cache_finish_close")

    def test_live_success_retains_objects_until_native_finish(self):
        self.run_scenario("live_finish_success")

    def test_live_error_retains_objects_until_native_finish(self):
        self.run_scenario("live_finish_failure")

    def test_close_during_native_live_cleanup_waits_for_completion(self):
        self.run_scenario("live_finish_close")


def _run_child(name, root):
    from contextlib import ExitStack
    from datetime import datetime, timezone
    import threading
    import time
    import traceback
    from unittest.mock import patch

    sys.path.insert(0, str(root))
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, QTimer, Qt, Slot
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.qt_golfhub_app import GolfHub, TeeTimeCard

    app = QApplication.instance() or QApplication([])
    check = unittest.TestCase()
    errors = []
    gates = []
    native_finish_checks = []

    class DestructionObserver(QObject):
        def __init__(self):
            super().__init__()
            self.workers = 0
            self.threads = 0

        @Slot()
        def worker_gone(self):
            self.workers += 1

        @Slot()
        def thread_gone(self):
            self.threads += 1

    observer = DestructionObserver()

    def blocked(*args, **kwargs):
        raise AssertionError("Lifecycle regression has no network/browser access")

    def pump_until(predicate, description):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(1)
        check.assertTrue(predicate(), description)
        app.processEvents()

    def observe_active(window, kind):
        # Connect without retaining wrappers outside this call: keeping the last
        # Python reference would hide premature native-object destruction.
        thread = getattr(window, f"{kind}_thread")
        worker = getattr(window, f"{kind}_worker")
        check.assertIsNotNone(thread)
        check.assertIsNotNone(worker)
        thread.destroyed.connect(observer.thread_gone)
        worker.destroyed.connect(observer.worker_gone)

    def idle(window, kind, count):
        pump_until(lambda: getattr(window, f"{kind}_thread") is None and
                   getattr(window, f"{kind}_worker") is None and
                   observer.threads == count and observer.workers == count,
                   f"{kind} completion must release exactly {count} threads/workers")
        check.assertEqual(window.findChildren(QThread), [], "Finished QThreads must not accumulate on the window")

    def new_gate():
        entered, release = threading.Event(), threading.Event()
        gates.append(release)
        return entered, release

    def gated(entered, release):
        entered.set()
        if not release.wait(5):
            raise AssertionError("Fixture gate was not released")

    def hold_native_finish(window, kind):
        entered, release = new_gate()
        expired = threading.Event()

        def hold():
            # finished is emitted before all native thread cleanup completes.
            # Holding a direct receiver makes that interval deterministic without
            # replacing QThread or retaining its Python wrapper in the fixture.
            entered.set()
            if not release.wait(5):
                expired.set()

        getattr(window, f"{kind}_thread").finished.connect(hold, Qt.ConnectionType.DirectConnection)
        return entered, release, expired

    def assert_native_finish_held(window, kind, barrier):
        entered, release, expired = barrier
        pump_until(entered.is_set, "The native thread must reach its finished signal")
        ticks = []
        QTimer.singleShot(0, lambda: ticks.append(True))
        pump_until(lambda: bool(ticks), "The GUI must stay responsive during native thread cleanup")
        check.assertFalse(expired.is_set(), "Cleanup must not block the GUI until the native barrier expires")
        check.assertFalse(release.is_set())
        check.assertIsNotNone(getattr(window, f"{kind}_thread"), "Keep the QThread alive until native completion")
        check.assertIsNotNone(getattr(window, f"{kind}_worker"), "Keep the worker wrapper until native completion")
        check.assertFalse(getattr(window, f"{kind}_thread").isRunning(),
                          "Exercise native cleanup after isRunning has become false")
        check.assertFalse(getattr(window, f"{kind}_thread").wait(0), "The fixture must still hold native completion")
        check.assertEqual(observer.threads, 0, "Do not delete QThread before native completion")
        check.assertEqual(observer.workers, 0, "Worker deletion follows finished signal dispatch")
        native_finish_checks.append(kind)

    with ExitStack() as stack:
        stack.enter_context(patch("socket.create_connection", blocked))
        stack.enter_context(patch("socket.socket.connect", blocked))
        stack.enter_context(patch("socket.socket.connect_ex", blocked))
        stack.enter_context(patch("socket.getaddrinfo", blocked))
        stack.enter_context(patch("webbrowser.open", blocked))
        stack.enter_context(patch("sys.excepthook", side_effect=lambda kind, value, tb: errors.append(str(value))))
        stack.enter_context(patch("app.qt_golfhub_app.load_local_snapshot", return_value=None))
        stack.enter_context(patch("app.course_results.get_weather_for_date", return_value=None))
        saved = stack.enter_context(patch("app.qt_golfhub_app.save_local_snapshot"))
        message = stack.enter_context(patch("app.qt_golfhub_app.QMessageBox.critical"))
        with patch.object(GolfHub, "show_initial_cache"):
            window = GolfHub()
        window._stop_deferred_timers()
        window.show()
        app.processEvents()
        site = next(site for site in window.sites if site.provider != "direct" and "18" in site.holes)
        first = window.date.minimumDate().addDays(1)

        def context(offset=0, players=None):
            date = first.addDays(offset).toString("yyyy-MM-dd")
            return {"sites": [site], "date": date, "dates": [date], "holes": "18",
                    "players": players, "from": None, "to": None}

        def result(date):
            url = site.build_url(date, "18")
            return {"site_name": site.name, "url": url, "hole_label": "18 holes",
                    "decorated_rows": [{"time": "9:00 am", "minutes": 540, "spots": 2, "source_url": url},
                                       {"time": "10:00 am", "minutes": 600, "spots": 4, "source_url": url}],
                    "weather": None, "error": None}

        def snapshot(date):
            return {"schema": 1, "date": date, "holes": "18",
                    "generated_at": datetime.now(timezone.utc).isoformat(), "results": [result(date)]}

        calls = []
        executor_setups = []

        def assert_closing_rejects_searches():
            identities = tuple(id(getattr(window, attr)) for attr in
                               ("cache_thread", "cache_worker", "scan_thread", "scan_worker"))
            pending = window._pending_cache_context
            previous_calls = list(calls)
            with patch.object(window, "params", return_value=context(4)):
                window.search_cache()
                window.search_live(context(4))
            check.assertEqual(tuple(id(getattr(window, attr)) for attr in
                                    ("cache_thread", "cache_worker", "scan_thread", "scan_worker")),
                              identities, "Closing must not create or replace a cache/live worker")
            check.assertEqual(window._pending_cache_context, pending, "Closing must not queue another cache search")
            check.assertEqual(calls, previous_calls)

        try:
            if name == "cache_sequence":
                for index in range(4):
                    entered, release = new_gate()
                    def fetch(date, holes):
                        calls.append(date)
                        gated(entered, release)
                        return snapshot(date)
                    with patch("app.qt_golfhub_app.fetch_shared_snapshot", side_effect=fetch):
                        window._start_cache_search(context(index))
                        observe_active(window, "cache")
                        pump_until(entered.is_set, "Cache fetch must run in a real worker")
                        release.set()
                        idle(window, "cache", index + 1)
                    check.assertEqual(window.context["date"], context(index)["date"])
                    check.assertEqual(len(window.findChildren(TeeTimeCard)), 2)
                    check.assertTrue(window.search_button.isEnabled())
                    check.assertEqual(window.search_button.text(), "FIND TEE TIMES")
                check.assertEqual(len(calls), 4)
            elif name in ("cache_queue", "cache_close", "cache_finish_queue", "cache_finish_close"):
                entered, release = new_gate()
                next_entered, next_release = new_gate()
                old, discarded, latest = context(), context(1), context(2, players=4)
                def fetch(date, holes):
                    calls.append(date)
                    if date == old["date"]:
                        gated(entered, release)
                    else:
                        gated(next_entered, next_release)
                    return snapshot(date)
                with patch("app.qt_golfhub_app.fetch_shared_snapshot", side_effect=fetch):
                    window._start_cache_search(old)
                    observe_active(window, "cache")
                    pump_until(entered.is_set, "First cache request must be in flight")
                    with patch.object(window, "params", return_value=discarded):
                        window.search_cache()
                    with patch.object(window, "params", return_value=latest):
                        window.search_cache()
                    check.assertEqual(window._pending_cache_context, latest)
                    check.assertEqual(calls, [old["date"]])
                    barrier = hold_native_finish(window, "cache") if name.startswith("cache_finish_") else None
                    if barrier:
                        release.set()
                        assert_native_finish_held(window, "cache", barrier)
                        latest = context(3, players=4)
                        with patch.object(window, "params", return_value=latest):
                            window.search_cache()
                        check.assertEqual(window._pending_cache_context, latest)
                        check.assertEqual(calls, [old["date"]], "A queued search waits for native completion")
                        check.assertFalse(next_entered.is_set())
                    if name in ("cache_close", "cache_finish_close"):
                        window.close()
                        check.assertTrue(window._closing)
                        check.assertTrue(window.isVisible(), "Close waits for the active worker")
                        assert_closing_rejects_searches()
                        release.set()
                        if barrier:
                            check.assertFalse(barrier[2].is_set())
                            check.assertIsNotNone(window.cache_thread)
                            barrier[1].set()
                        idle(window, "cache", 1)
                        pump_until(lambda: not window.isVisible(), "Window closes after worker completion")
                        assert_closing_rejects_searches()
                        check.assertEqual(calls, [old["date"]], "Closing must not launch the queued request")
                        check.assertFalse(next_entered.is_set())
                        saved.assert_not_called()
                    else:
                        release.set()
                        if barrier:
                            barrier[1].set()
                        pump_until(next_entered.is_set, "Newest queued request must start after first completion")
                        observe_active(window, "cache")
                        check.assertEqual(window.context, latest)
                        next_release.set()
                        idle(window, "cache", 2)
                        check.assertEqual(calls, [old["date"], latest["date"]])
                        check.assertIsNone(window._pending_cache_context)
                        check.assertEqual([card.row["spots"] for card in window.findChildren(TeeTimeCard)], [4])
                        check.assertTrue(window.search_button.isEnabled())
            else:
                entered, release = new_gate()
                p = context()
                if name in ("live_failure", "live_finish_failure"):
                    def fail_executor(*args, **kwargs):
                        executor_setups.append(True)
                        gated(entered, release)
                        raise RuntimeError("Fixture worker setup failed")
                    stack.enter_context(patch("app.qt_golfhub_app.ThreadPoolExecutor", side_effect=fail_executor))
                else:
                    def fetch(*args, **kwargs):
                        calls.append(p["date"])
                        gated(entered, release)
                        return result(p["date"])
                    stack.enter_context(patch("app.qt_golfhub_app.fetch_site_result", side_effect=fetch))
                window.search_live(p)
                observe_active(window, "scan")
                pump_until(entered.is_set, "Live fetch/setup must run in a real worker")
                barrier = hold_native_finish(window, "scan") if name.startswith("live_finish_") else None
                if name == "live_cancel":
                    window.stop_scan()
                release.set()
                if barrier:
                    assert_native_finish_held(window, "scan", barrier)
                    thread_identity = id(window.scan_thread)
                    worker_identity = id(window.scan_worker)
                    window.search_live(p)
                    check.assertEqual(id(window.scan_thread), thread_identity,
                                      "A repeated live refresh must not replace an unfinished QThread")
                    check.assertEqual(id(window.scan_worker), worker_identity,
                                      "A repeated live refresh must not replace an unfinished worker")
                    if name == "live_finish_close":
                        window.close()
                        check.assertTrue(window._closing)
                        check.assertTrue(window.isVisible(), "Close waits for native live thread completion")
                        check.assertIsNotNone(window.scan_thread)
                        assert_closing_rejects_searches()
                    check.assertFalse(barrier[2].is_set())
                    barrier[1].set()
                idle(window, "scan", 1)
                if name == "live_finish_close":
                    pump_until(lambda: not window.isVisible(), "Window closes after native live thread completion")
                    assert_closing_rejects_searches()
                else:
                    check.assertTrue(window.search_button.isEnabled())
                    check.assertTrue(window.live_button.isEnabled())
                check.assertFalse(window.progress.isVisible())
                if name in ("live_success", "live_finish_success", "live_finish_close"):
                    saved.assert_called_once()
                    message.assert_not_called()
                    check.assertEqual(window.header_status.text(), "LIVE RESULTS / UPDATED NOW")
                    check.assertEqual(len(window.findChildren(TeeTimeCard)), 2)
                elif name in ("live_failure", "live_finish_failure"):
                    saved.assert_not_called()
                    message.assert_called_once()
                    check.assertEqual(executor_setups, [True], "Only one live worker setup may run")
                    check.assertEqual(window.header_status.text(), "LIVE REFRESH FAILED / CACHE PRESERVED")
                else:
                    saved.assert_not_called()
                    message.assert_not_called()
                    check.assertEqual(window.header_status.text(), "REFRESH STOPPED / CACHE PRESERVED")
                check.assertEqual(len(calls), 0 if "failure" in name else 1,
                                  "Only one live fetch may run")
            check.assertEqual(errors, [], "No Qt callback exceptions are allowed")
        finally:
            original_error = sys.exc_info()
            if original_error[0] is not None:
                # Preserve the causal assertion even if native teardown then
                # blocks until the parent subprocess timeout.
                traceback.print_exception(*original_error)
            for gate in gates:
                gate.set()
            # A failed assertion must not leave a live worker stranded. The
            # subprocess timeout remains the final bound if cleanup itself stalls.
            try:
                pump_until(lambda: window.cache_thread is None and window.scan_thread is None,
                           "All active worker threads must finish before disposing the test window")
                window.close()
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()
            except Exception:
                if original_error[0] is None:
                    raise
                traceback.print_exc()
        print("LIFECYCLE_RESULT " + json.dumps({"scenario": name,
              "worker_destroyed": observer.workers, "thread_destroyed": observer.threads,
              "callback_errors": errors, "fixture_fetches": calls,
              "native_finish_checks": native_finish_checks}), flush=True)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--scenario", choices=["cache_sequence", "cache_queue", "cache_close",
                                                  "live_success", "live_failure", "live_cancel",
                                                  "cache_finish_queue", "cache_finish_close",
                                                  "live_finish_success", "live_finish_failure",
                                                  "live_finish_close"], required=True)
        parser.add_argument("--root", type=Path, required=True)
        args = parser.parse_args()
        _run_child(args.scenario, args.root.resolve())
    else:
        unittest.main()
