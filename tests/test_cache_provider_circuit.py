import io
import json
import tempfile
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from threading import Lock
from time import sleep
from unittest.mock import patch
from urllib.parse import urlsplit

from app import golfhub_core
from app.golfhub_core import HoleOption, Site
from scripts import refresh_cache_shard as shard


def make_site(name="affected", provider="quick18", domain=None):
    return Site(
        name=name,
        provider=provider,
        domain=domain or f"{name}.example",
        holes={key: HoleOption("resource", "fee") for key in ("18", "9")},
    )


def make_result(site, error=None, **extra):
    return {
        "site_name": site.name,
        "url": f"https://{site.domain}",
        "decorated_rows": [],
        "error": error,
        **extra,
    }


class ProviderCircuitTests(unittest.TestCase):
    base_date = date(2026, 10, 4)
    prior_attempt = "2026-10-03T23:23:00+00:00"
    prior_stale_since = "2026-10-03T23:06:00+00:00"

    def setUp(self):
        self.affected = make_site()
        self.healthy = [make_site(f"healthy{i}", "miclub") for i in range(2)]
        self.sites = [self.affected, *self.healthy]

    def run_shard(self, output, sites=None, fallback=None):
        argv = [
            "refresh_cache_shard.py", "--start-offset", "0", "--days", "4",
            "--base-date", self.base_date.isoformat(), "--output", str(output),
        ]
        if fallback is not None:
            argv.extend(["--fallback", str(fallback)])
        with (
            patch("sys.argv", argv),
            patch.object(shard, "load_sites", return_value=self.sites if sites is None else sites),
            patch.object(shard, "sleep"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(shard.main(), 0)
        snapshots = []
        for offset in range(4):
            date_str = (self.base_date + timedelta(days=offset)).isoformat()
            for holes in ("18", "9"):
                snapshots.append(json.loads((output / date_str / f"{holes}.json").read_text()))
        self.assertEqual(len(list(output.rglob("*.json"))), 8)
        return snapshots

    def write_prior_snapshots(self, root):
        for offset in range(4):
            date_str = (self.base_date + timedelta(days=offset)).isoformat()
            for holes in ("18", "9"):
                payload = {
                    "schema": 1,
                    "date": date_str,
                    "holes": holes,
                    "generated_at": self.prior_attempt,
                    "results": [make_result(
                        self.affected,
                        stale=True,
                        stale_since=self.prior_stale_since,
                        last_refresh_attempt_at=self.prior_attempt,
                        decorated_rows=[{"time": "7:00 am"}],
                    )],
                }
                target = root / date_str / f"{holes}.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(payload), encoding="utf-8")

    def test_persistent_outage_caps_actual_http_requests_and_keeps_complete_shard(self):
        failing = [make_site(f"affected{i}") for i in range(3)]
        healthy = [make_site(f"healthy{i}", "miclub") for i in range(4)]
        sites = [*failing, *healthy]
        calls = Counter()

        def fetch_text(url, **kwargs):
            domain = urlsplit(url).hostname
            calls[domain] += 1
            if domain.startswith("affected"):
                raise TimeoutError("timed out")
            return "<html><body>No available times</body></html>"

        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.object(golfhub_core, "fetch_text", side_effect=fetch_text),
                patch.object(golfhub_core, "get_weather_for_date", return_value=None),
                patch.object(golfhub_core, "save_debug_html"),
                patch("time.sleep"),
            ):
                snapshots = self.run_shard(Path(temporary), sites=sites)
        for site in failing:
            self.assertEqual(calls[site.domain], 4)
        for site in healthy:
            self.assertEqual(calls[site.domain], 8)
        for snapshot in snapshots:
            self.assertEqual(len(snapshot["results"]), 7)
            self.assertEqual(snapshot["health"]["fresh_live_successes"], 4)
            self.assertEqual(snapshot["health"]["minimum_live_successes"], 4)
            self.assertEqual(snapshot["health"]["stale_fallbacks"], 0)
            for result in snapshot["results"][:3]:
                self.assertTrue(result["error"])
        for snapshot in snapshots[1:]:
            self.assertEqual(snapshot["health"]["provider_circuit_skips"], 3)
            for result in snapshot["results"][:3]:
                self.assertTrue(result["refresh_skipped"])
                self.assertEqual(result["refresh_skip_reason"], "provider_circuit_open")
                self.assertEqual(result["provider_last_error"], "timed out")
                self.assertEqual(result["provider_transient_failures"], 2)
                self.assertIn("provider circuit open", result["error"].lower())
                self.assertIn("timed out", result["error"])
                self.assertLessEqual(result["provider_last_attempt_at"], result["last_refresh_skipped_at"])
                self.assertNotIn("last_refresh_attempt_at", result)

    def test_skipped_fallback_keeps_original_staleness_and_actual_attempt_time(self):
        def fetch(site, *_):
            return make_result(site, "timed out" if site.provider == "quick18" else None)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_prior_snapshots(root / "previous")
            with patch.object(shard, "fetch_one", side_effect=fetch):
                snapshots = self.run_shard(root / "output", fallback=root / "previous")
        first = snapshots[0]["results"][0]
        self.assertNotEqual(first["last_refresh_attempt_at"], self.prior_attempt)
        self.assertFalse(first.get("refresh_skipped", False))
        for snapshot in snapshots:
            result = snapshot["results"][0]
            self.assertIsNone(result["error"])
            self.assertTrue(result["stale"])
            self.assertEqual(result["stale_since"], self.prior_stale_since)
            self.assertEqual(result["decorated_rows"], [{"time": "7:00 am"}])
            self.assertEqual(snapshot["health"]["stale_fallbacks"], 1)
            self.assertEqual(snapshot["health"]["fresh_live_successes"], 2)
        for snapshot in snapshots[1:]:
            result = snapshot["results"][0]
            self.assertTrue(result["refresh_skipped"])
            self.assertEqual(result["refresh_skip_reason"], "provider_circuit_open")
            self.assertEqual(result["last_refresh_attempt_at"], self.prior_attempt)
            self.assertTrue(result["stale_reason"])

    def test_successful_delayed_recovery_keeps_fetching_remaining_dates(self):
        calls = Counter()

        def fetch(site, *_):
            calls[site.name] += 1
            if site.provider == "quick18" and calls[site.name] == 1:
                return make_result(site, "timed out")
            return make_result(site, decorated_rows=[{"time": "8:00 am"}])

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(shard, "fetch_one", side_effect=fetch):
                snapshots = self.run_shard(Path(temporary))
        self.assertEqual(calls[self.affected.name], 9)
        for snapshot in snapshots:
            result = snapshot["results"][0]
            self.assertIsNone(result["error"])
            self.assertFalse(result.get("stale", False))
            self.assertFalse(result.get("refresh_skipped", False))
            self.assertEqual(result["decorated_rows"], [{"time": "8:00 am"}])
            self.assertEqual(snapshot["health"]["fresh_live_successes"], 3)

    def test_failures_accumulate_across_successes_within_one_shard(self):
        calls = Counter()

        def fetch(site, *_):
            calls[site.name] += 1
            if site.provider == "quick18" and calls[site.name] in (1, 4):
                return make_result(site, "timed out")
            return make_result(site)

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(shard, "fetch_one", side_effect=fetch):
                snapshots = self.run_shard(Path(temporary))
        self.assertEqual(calls[self.affected.name], 4)
        self.assertIsNone(snapshots[0]["results"][0]["error"])
        self.assertIsNone(snapshots[1]["results"][0]["error"])
        self.assertEqual(snapshots[2]["results"][0]["error"], "timed out")
        for snapshot in snapshots[3:]:
            self.assertTrue(snapshot["results"][0]["refresh_skipped"])

    def test_new_shard_starts_with_fresh_circuit_and_can_recover(self):
        calls = Counter()

        def failed_fetch(site, *_):
            calls[site.name] += 1
            return make_result(site, "timed out" if site.provider == "quick18" else None)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(shard, "fetch_one", side_effect=failed_fetch):
                self.run_shard(root / "failed")
            self.assertEqual(calls[self.affected.name], 2)
            with patch.object(shard, "fetch_one", side_effect=lambda site, *_: make_result(site)) as fetch:
                recovered = self.run_shard(root / "recovered", fallback=root / "failed")
        self.assertEqual(fetch.call_count, 24)
        for snapshot in recovered:
            result = snapshot["results"][0]
            self.assertIsNone(result["error"])
            self.assertFalse(result.get("refresh_skipped", False))
            self.assertFalse(result.get("stale", False))

    def test_all_provider_outage_fails_majority_gate_before_any_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(shard, "fetch_one", side_effect=lambda site, *_: make_result(site, "timed out")),
                patch.object(shard, "load_previous_snapshot") as prior,
            ):
                with self.assertRaisesRegex(RuntimeError, "0/3 live providers succeeded; 2 required"):
                    self.run_shard(root)
            prior.assert_not_called()
            self.assertEqual(list(root.rglob("*.json")), [])

    def test_concurrent_same_domain_aliases_cannot_exceed_failure_budget(self):
        circuit = shard.ProviderCircuit()
        sites = [make_site("alias1", domain="QUICK18.example"), make_site("alias2", domain="quick18.example")]
        counter_lock = Lock()
        active = maximum_active = calls = 0

        def failed_fetch(site, *_):
            nonlocal active, maximum_active, calls
            with counter_lock:
                calls += 1
                active += 1
                maximum_active = max(maximum_active, active)
            sleep(0.005)
            with counter_lock:
                active -= 1
            return make_result(site, "timed out")

        with patch.object(shard, "fetch_one", side_effect=failed_fetch), redirect_stdout(io.StringIO()):
            with ThreadPoolExecutor(max_workers=8) as pool:
                jobs = [pool.submit(circuit.fetch, sites[i % 2], "2026-10-04", "18") for i in range(10)]
                results = [job.result() for job in jobs]
        self.assertEqual(calls, 2)
        self.assertEqual(maximum_active, 1)
        self.assertEqual(sum(bool(result.get("refresh_skipped")) for result in results), 8)

    def test_nontransport_errors_do_not_spend_transport_failure_budget(self):
        circuit = shard.ProviderCircuit()
        errors = ["HTTP Error 429: Too Many Requests", "timed out", "certificate verify failed", "timed out"]
        with (
            patch.object(shard, "fetch_one", side_effect=[make_result(self.affected, error) for error in errors]) as fetch,
            redirect_stdout(io.StringIO()),
        ):
            for error in errors:
                result = circuit.fetch(self.affected, "2026-10-04", "18")
                self.assertEqual(result["error"], error)
                self.assertFalse(result.get("refresh_skipped", False))
            skipped = circuit.fetch(self.affected, "2026-10-05", "9")
        self.assertEqual(fetch.call_count, 4)
        self.assertTrue(skipped["refresh_skipped"])

    def test_miclub_and_direct_results_are_not_subject_to_quick18_circuit(self):
        circuit = shard.ProviderCircuit()
        sites = [make_site("miclub", "miclub"), make_site("direct", "direct")]
        with patch.object(shard, "fetch_one", side_effect=lambda site, *_: make_result(site, "timed out")) as fetch:
            for site in sites:
                for _ in range(3):
                    result = circuit.fetch(site, "2026-10-04", "18")
                    self.assertEqual(result["error"], "timed out")
                    self.assertFalse(result.get("refresh_skipped", False))
        self.assertEqual(fetch.call_count, 6)

    def test_actual_failed_refresh_clears_previous_skip_metadata(self):
        skip_metadata = {
            "refresh_skipped": True,
            "refresh_skip_reason": "provider_circuit_open",
            "last_refresh_skipped_at": "2026-10-03T23:30:00+00:00",
            "provider_last_error": "timed out",
            "provider_last_attempt_at": self.prior_attempt,
            "provider_transient_failures": 2,
        }
        previous = {
            "generated_at": "2026-10-03T23:30:00+00:00",
            "results": [make_result(
                self.affected,
                stale=True,
                stale_since=self.prior_stale_since,
                last_refresh_attempt_at=self.prior_attempt,
                **skip_metadata,
            )],
        }
        current_attempt = "2026-10-03T23:40:00+00:00"
        failed = make_result(self.affected, "timed out", last_refresh_attempt_at=current_attempt)
        reused, did_reuse = shard.reuse_prior_good_result(self.affected, failed, previous)
        self.assertTrue(did_reuse)
        self.assertTrue(reused["stale"])
        self.assertEqual(reused["stale_since"], self.prior_stale_since)
        self.assertEqual(reused["last_refresh_attempt_at"], current_attempt)
        for key in skip_metadata:
            self.assertNotIn(key, reused)

    def test_delayed_retry_does_not_sleep_or_spend_quota_when_circuit_is_open(self):
        circuit = shard.ProviderCircuit()
        retried_domains = set()
        with (
            patch.object(shard, "fetch_one", return_value=make_result(self.affected, "timed out")) as fetch,
            patch.object(shard, "sleep") as pause,
            redirect_stdout(io.StringIO()),
        ):
            first = circuit.fetch(self.affected, "2026-10-04", "18")
            circuit.fetch(self.affected, "2026-10-04", "9")
            stats = shard.retry_transient_results(
                [self.affected], {self.affected.name: first}, "2026-10-04", "18",
                retried_domains, circuit=circuit,
            )
        self.assertEqual(stats, (0, 0))
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(retried_domains, set())
        pause.assert_not_called()


if __name__ == "__main__":
    unittest.main()
