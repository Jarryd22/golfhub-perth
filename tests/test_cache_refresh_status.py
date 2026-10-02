import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.cache_refresh_status import refresh_status


class CacheRefreshStatusTests(unittest.TestCase):
    now = datetime(2026, 10, 2, 3, 30, tzinfo=timezone.utc)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        self.index = {
            "schema": 1,
            "range_days": 28,
            "generated_at": (self.now - timedelta(minutes=2)).isoformat(),
            "dates": [
                {"date": (self.now.date() + timedelta(days=i)).isoformat(), "holes": ["18", "9"]}
                for i in range(28)
            ],
        }
        for entry in self.index["dates"]:
            folder = self.cache / entry["date"]
            folder.mkdir()
            for holes in entry["holes"]:
                (folder / f"{holes}.json").write_text("{}", encoding="utf-8")
        self.save_index()

    def save_index(self):
        (self.cache / "index.json").write_text(json.dumps(self.index), encoding="utf-8")

    def status(self, event="workflow_run"):
        return refresh_status(self.cache, self.now.date(), event, self.now)

    def test_nearby_automatic_triggers_skip_without_rewriting_timestamp(self):
        before = (self.cache / "index.json").read_bytes()
        for event in ("workflow_run", "schedule"):
            with self.subTest(event=event):
                refresh, message = self.status(event)
                self.assertFalse(refresh)
                self.assertIn("2.0 minutes", message)
                self.assertIn("Skipped duplicate", message)
        self.assertEqual((self.cache / "index.json").read_bytes(), before)

    def test_manual_and_source_change_triggers_always_refresh(self):
        for event in ("workflow_dispatch", "push"):
            with self.subTest(event=event):
                self.assertTrue(self.status(event)[0])

    def test_five_minute_boundary_and_next_heartbeat_refresh(self):
        for age in (5, 8, 10, 180):
            with self.subTest(age=age):
                self.index["generated_at"] = (self.now - timedelta(minutes=age)).isoformat()
                self.save_index()
                self.assertTrue(self.status()[0])

    def test_stale_cache_age_is_reported(self):
        self.index["generated_at"] = (self.now - timedelta(hours=3)).isoformat()
        self.save_index()
        refresh, message = self.status()
        self.assertTrue(refresh)
        self.assertIn("180.0 minutes", message)
        self.assertIn("STALE:", message)

    def test_invalid_naive_future_or_missing_timestamp_cannot_suppress_refresh(self):
        for stamp in (None, 12, "bad", "2026-10-02T03:29:00", "2026-10-02T03:31:00Z"):
            with self.subTest(stamp=stamp):
                self.index["generated_at"] = stamp
                self.save_index()
                self.assertTrue(self.status()[0])
        del self.index["generated_at"]
        self.save_index()
        self.assertTrue(self.status()[0])

    def test_utc_z_and_perth_offset_timestamps_are_supported(self):
        for stamp in ("2026-10-02T03:28:00Z", "2026-10-02T11:28:00+08:00"):
            with self.subTest(stamp=stamp):
                self.index["generated_at"] = stamp
                self.save_index()
                self.assertFalse(self.status()[0])

    def test_missing_unreadable_or_wrong_shape_index_refreshes(self):
        path = self.cache / "index.json"
        for content in ("{", "null", "[]", "{}"):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.assertTrue(self.status()[0])
        path.unlink()
        self.assertTrue(self.status()[0])

    def test_wrong_schema_range_or_hole_coverage_refreshes(self):
        for key, value in (("schema", 2), ("range_days", 27), ("dates", self.index["dates"][:-1])):
            with self.subTest(key=key):
                original = self.index[key]
                self.index[key] = value
                self.save_index()
                self.assertTrue(self.status()[0])
                self.index[key] = original
        self.index["dates"][0]["holes"] = ["18"]
        self.save_index()
        self.assertTrue(self.status()[0])

    def test_missing_snapshot_refreshes_even_when_index_is_recent(self):
        (self.cache / self.index["dates"][-1]["date"] / "9.json").unlink()
        self.assertTrue(self.status()[0])

    def test_perth_midnight_refreshes_recent_previous_day_window(self):
        midnight = datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc)
        self.index["generated_at"] = (midnight - timedelta(minutes=1)).isoformat()
        self.save_index()
        tomorrow_in_perth = self.now.date() + timedelta(days=1)
        self.assertTrue(refresh_status(self.cache, tomorrow_in_perth, "workflow_run", midnight)[0])

    def test_cli_writes_action_output_and_freshness_summary(self):
        # Missing index exercises the first-run path without network or live data.
        (self.cache / "index.json").unlink()
        output, summary = self.cache / "output.txt", self.cache / "summary.md"
        script = Path(__file__).resolve().parents[1] / "scripts" / "cache_refresh_status.py"
        result = subprocess.run([
            sys.executable, str(script), "--cache", str(self.cache),
            "--base-date", "2026-10-02", "--event", "workflow_run",
            "--heartbeat-run", "https://github.com/example/repo/actions/runs/123",
            "--output", str(output), "--summary", str(summary),
        ], capture_output=True, text=True, check=True)
        self.assertEqual(output.read_text(encoding="utf-8"), "refresh=true\n")
        report = summary.read_text(encoding="utf-8")
        self.assertIn("Trigger: `workflow_run`", report)
        self.assertIn("actions/runs/123", report)
        self.assertIn("stale fallback", report)
        self.assertIn("refresh required", result.stdout)


if __name__ == "__main__":
    unittest.main()
