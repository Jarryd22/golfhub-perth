"""Offline snapshot-boundary regressions using real isolated cache files."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import shared_cache as cache


class CacheSnapshotShapeTests(unittest.TestCase):
    date = "2033-01-02"
    holes = "18"

    def setUp(self):
        self.runtime = self.enterContext(tempfile.TemporaryDirectory(prefix="golfhub-cache-shape-"))
        self.enterContext(patch.object(cache, "LOCAL_CACHE_DIR", Path(self.runtime) / "cache"))
        self.enterContext(patch("socket.create_connection", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("webbrowser.open", side_effect=AssertionError("Offline test")))
        self.path = cache.local_snapshot_path(self.date, self.holes)

    @staticmethod
    def result(**extra):
        return {"site_name": "Araluen", "decorated_rows": [], "error": None, **extra}

    def snapshot(self, *results):
        return cache.make_snapshot(self.date, self.holes, list(results))

    def write_raw(self, payload):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def fetch_bytes(self, payload):
        with (
            patch.object(cache, "_cache_base_url", return_value="https://example.invalid/cache"),
            patch.object(cache.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as request,
        ):
            result = cache.fetch_shared_snapshot(self.date, self.holes)
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0].full_url,
                         f"https://example.invalid/cache/{self.date}/{self.holes}.json")
        return result

    def malformed_snapshots(self):
        valid = self.snapshot(self.result())
        yield {**valid, "results": [None]}
        yield {**valid, "results": ["invalid course record"]}
        yield self.snapshot(self.result(decorated_rows={"minutes": 540}))
        yield self.snapshot(self.result(decorated_rows=[None]))

    def test_rejects_nonobject_results_even_among_valid_courses(self):
        valid = self.snapshot(self.result())
        for invalid in (None, "course", 0, False, []):
            with self.subTest(record=invalid):
                payload = {**valid, "results": [self.result(), invalid, self.result(site_name="Wembley")]}
                with self.assertRaises(ValueError):
                    cache.validate_snapshot(payload, self.date, self.holes)

    def test_rejects_nonlist_rows_including_empty_containers(self):
        for invalid in ({}, {"minutes": 540}, "", "row", 0, False):
            with self.subTest(rows=invalid):
                with self.assertRaises(ValueError):
                    cache.validate_snapshot(self.snapshot(self.result(decorated_rows=invalid)),
                                            self.date, self.holes)

    def test_rejects_nonobject_rows_even_after_a_valid_tee_time(self):
        for invalid in (None, "row", 0, False, []):
            with self.subTest(row=invalid):
                rows = [{"minutes": 540, "spots": 4, "time": "9:00 am"}, invalid]
                with self.assertRaises(ValueError):
                    cache.validate_snapshot(self.snapshot(self.result(decorated_rows=rows)),
                                            self.date, self.holes)

    def test_valid_empty_error_direct_calendar_and_optional_rows_are_preserved(self):
        families = [
            [],
            [{"site_name": "Araluen"}],
            [self.result(decorated_rows=None)],
            [self.result()],
            [self.result(error="Provider unavailable")],
            [self.result(direct_booking=True, url="https://example.invalid/official")],
            [self.result(site_name="Wembley", calendar_availability="unreleased")],
            [self.result(decorated_rows=[{"minutes": 540, "spots": 4, "custom_field": "retained"}])],
        ]
        for results in families:
            with self.subTest(results=results):
                payload = self.snapshot(*results)
                before = json.dumps(payload, sort_keys=True)
                self.assertIs(cache.validate_snapshot(payload, self.date, self.holes), payload)
                self.assertEqual(json.dumps(payload, sort_keys=True), before)

    def test_existing_envelope_checks_still_reject_wrong_search_and_shape(self):
        valid = self.snapshot()
        for invalid in (None, [], {**valid, "schema": 99}, {**valid, "date": "2033-01-03"},
                        {**valid, "holes": "9"}, {**valid, "results": None}):
            with self.subTest(payload=invalid):
                with self.assertRaises(ValueError):
                    cache.validate_snapshot(invalid, self.date, self.holes)

    def test_local_loader_ignores_malformed_records_without_rewriting_file(self):
        for payload in self.malformed_snapshots():
            with self.subTest(payload=payload):
                self.write_raw(payload)
                original = self.path.read_bytes()
                self.assertIsNone(cache.load_local_snapshot(self.date, self.holes))
                self.assertEqual(self.path.read_bytes(), original)
                self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_invalid_shared_response_preserves_last_valid_snapshot_bytes(self):
        valid = self.snapshot(self.result(decorated_rows=[{"time": "9:00 am", "minutes": 540, "spots": 4}]))
        for payload in self.malformed_snapshots():
            with self.subTest(payload=payload):
                cache.save_local_snapshot(valid)
                original = self.path.read_bytes()
                self.assertIsNone(self.fetch_bytes(payload))
                self.assertEqual(self.path.read_bytes(), original)
                self.assertEqual(cache.load_local_snapshot(self.date, self.holes), valid)
                self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_invalid_shared_response_does_not_create_a_local_snapshot(self):
        payload = next(self.malformed_snapshots())
        self.assertIsNone(self.fetch_bytes(payload))
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_valid_shared_download_and_local_round_trip_keep_complete_payload(self):
        valid = self.snapshot(self.result(decorated_rows=[{"time": "9:00 am", "minutes": 540, "spots": 4}]),
                              self.result(site_name="Collier Park", error="Provider unavailable"))
        downloaded = self.fetch_bytes(valid)
        self.assertEqual(downloaded, valid)
        self.assertEqual(cache.load_local_snapshot(self.date, self.holes), valid)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), valid)
        self.assertFalse(self.path.with_suffix(".tmp").exists())
