"""Read-only alert source audit; no worker main, Firebase, or network execution."""
from __future__ import annotations

import hashlib
import importlib
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from datetime import datetime, timedelta, timezone, date

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("release-alert-service.json")
sys.path.insert(0, str(ROOT))


def blocked(*args, **kwargs):
    raise AssertionError("Network access blocked by read-only alert audit")


def run():
    archive = ROOT / ".github/alerts-runtime.zip"
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "network": "socket connect/connect_ex/create_connection/send/sendall/sendto blocked",
        "worker_main_invoked": False,
        "firebase_initialized": False,
        "real_delivery_attempted": False,
        "archive_path": str(archive.relative_to(ROOT)),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "source_imports": {},
    }
    for name in ["service.push_logic", "service.push_worker", "service.tests.test_push_delivery", "service.tests.test_recurrence"]:
        try:
            importlib.import_module(name)
            result["source_imports"][name] = {"imported": True}
        except Exception as exc:
            result["source_imports"][name] = {"imported": False, "blocker": f"{type(exc).__name__}: {exc}"}
    result["root_alert_suite"] = {"tests_run": 0, "status": "not run: import blockers above; these are not assertion failures"}
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        result["archive_files"] = names
        result["archive_test_files"] = [name for name in names if "/tests/" in name or Path(name).name.startswith("test_")]
        result["missing_root_modules_present_in_archive"] = [name for name in names if name.endswith(".py") and not (ROOT / name).exists()]
        result["shared_module_bytes_match_archive"] = {
            name: (ROOT / name).read_bytes() == z.read(name)
            for name in names if name.endswith(".py") and (ROOT / name).exists()
        }
        result["archive_requirements"] = z.read("service/requirements-push.txt").decode()
        with tempfile.TemporaryDirectory(prefix="golfhub-alert-audit-") as folder:
            for name in names:
                path = Path(name)
                if path.is_absolute() or ".." in path.parts:
                    raise AssertionError("Unsafe archive path")
            z.extractall(folder)
            for name in list(sys.modules):
                if name == "app" or name == "service" or name.startswith(("app.", "service.")):
                    del sys.modules[name]
            sys.path.insert(0, folder)
            from service.catalog import Catalog
            from service.push_logic import validate_watch, generation, transition, event_id, valid_matches, quiet_now, delivery_ttl
            from service.recurrence import recurrence_dates, pending_rounds
            clock = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)
            catalog = Catalog()
            spec = dict(enabled=True, dates=["2026-10-19"], course_ids=["araluen"], holes=18, players=4, from_minutes=360, to_minutes=600)

            def course(**changes):
                return dict(status="available", freshness="fresh", checked_at=clock.isoformat(), times=[dict(minutes=420, time="07:00 am", spots=4, course="Araluen")], **changes)

            class ArchivedLogicAudit(unittest.TestCase):
                def test_watch_filters_and_disabled_rejection(self):
                    self.assertEqual(validate_watch(spec, catalog, clock)["course_ids"], ["araluen"])
                    with self.assertRaises(ValueError):
                        validate_watch({**spec, "enabled": False}, catalog, clock)

                def test_invalid_group_time_and_course_rejected(self):
                    for changes in ({"players": True}, {"players": 5}, {"from_minutes": 601}, {"course_ids": ["unknown"]}):
                        with self.subTest(changes=changes), self.assertRaises(ValueError):
                            validate_watch({**spec, **changes}, catalog, clock)

                def test_stale_future_and_unknown_data_preserve_baseline(self):
                    previous = {"checked_at": (clock - timedelta(minutes=1)).isoformat(), "available": []}
                    for changes in ({"freshness": "stale"}, {"checked_at": (clock-timedelta(minutes=16)).isoformat()}, {"checked_at": (clock+timedelta(seconds=61)).isoformat()}, {"status": "unknown"}):
                        value = {**course(), **changes}
                        self.assertIsNone(valid_matches(value, "2026-10-19", clock))
                        self.assertEqual(transition(previous, value, "2026-10-19", clock), (previous, []))

                def test_new_watch_is_quiet_unless_explicitly_requested(self):
                    self.assertEqual(transition(None, course(), "2026-10-19", clock)[1], [])
                    self.assertEqual(len(transition(None, course(), "2026-10-19", clock, True)[1]), 1)

                def test_new_opening_once_and_old_snapshot_rejected(self):
                    previous = {"checked_at": (clock-timedelta(minutes=1)).isoformat(), "available": []}
                    state, new = transition(previous, course(), "2026-10-19", clock)
                    self.assertEqual(len(new), 1)
                    self.assertEqual(transition(state, course(), "2026-10-19", clock), (state, []))

                def test_past_tee_times_are_not_matches(self):
                    value = {**course(), "times": [dict(minutes=359, course="Araluen"), dict(minutes=420, course="Araluen")]}
                    self.assertEqual([v["minutes"] for v in valid_matches(value, "2026-10-19", clock)], [420])

                def test_quiet_hours_and_ttl_use_perth_clock(self):
                    quiet = dict(quiet_from_minutes=22*60, quiet_to_minutes=7*60)
                    self.assertTrue(quiet_now(quiet, clock))
                    self.assertEqual(delivery_ttl(quiet, clock), 0)
                    before = datetime(2026,10,19,13,59,tzinfo=timezone.utc)
                    self.assertFalse(quiet_now(quiet, before))
                    self.assertEqual(delivery_ttl(quiet, before), 60)

                def test_weekly_recurrence_and_acknowledgement(self):
                    rule = dict(kind="weekly", anchor="2026-09-28", weekday=1, day=31, ordinal=5)
                    dates = recurrence_dates(rule, date(2026,10,19))
                    self.assertEqual(dates, ["2026-10-19", "2026-10-26", "2026-11-02", "2026-11-09"])
                    self.assertEqual(pending_rounds(dict(dates=dates, recurrence=rule), {"dates": ["2026-10-19"]}), ["2026-10-26"])

                def test_invalid_recurrence_rejected(self):
                    rule = dict(kind="weekly", anchor="2026-09-28", weekday=1, day=31, ordinal=5)
                    for changes in ({"weekday": True}, {"kind": "daily"}, {"anchor": "2026-02-30"}):
                        with self.assertRaises((TypeError, ValueError)):
                            recurrence_dates({**rule, **changes}, date(2026,10,19))

                def test_reenable_and_event_identifiers(self):
                    self.assertNotEqual(generation(spec), generation({**spec, "created_at": clock.isoformat()}))
                    self.assertEqual(event_id("users/test/watches/test", "generation", []), event_id("users/test/watches/test", "generation", []))

            suite = unittest.defaultTestLoader.loadTestsFromTestCase(ArchivedLogicAudit)
            names = [test.id().split(".")[-1] for test in suite]
            output = io.StringIO()
            outcome = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
            result["isolated_archive_pure_logic_audit"] = {
                "tests_run": outcome.testsRun, "failures": len(outcome.failures), "errors": len(outcome.errors),
                "test_methods": names, "log": output.getvalue(),
                "scope": "New deterministic audit cases against isolated committed runtime archive; no archived test files exist. Not root suite or phone delivery tests.",
            }
            try:
                importlib.import_module("service.push_worker")
                result["archive_worker_import"] = {"imported": True}
            except Exception as exc:
                result["archive_worker_import"] = {"imported": False, "blocker": f"{type(exc).__name__}: {exc}"}
            result["delivery_tests"] = {"tests_run": 0, "status": "not run: firebase_admin dependency absent; no dependency installation or credential access attempted"}
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k in ("source_imports", "root_alert_suite", "isolated_archive_pure_logic_audit", "archive_worker_import", "delivery_tests")}, indent=2))
    return 0 if outcome.wasSuccessful() else 1


if __name__ == "__main__":
    with patch("socket.socket.connect", blocked), patch("socket.socket.connect_ex", blocked), patch("socket.create_connection", blocked), patch("socket.socket.send", blocked), patch("socket.socket.sendall", blocked), patch("socket.socket.sendto", blocked):
        sys.exit(run())
