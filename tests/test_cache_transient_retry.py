import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import refresh_cache_shard as shard


def make_site(name="Hamersley", provider="quick18", domain=None):
    return SimpleNamespace(
        name=name,
        provider=provider,
        domain=domain or f"{name.lower()}.example",
        holes={"18": {}, "9": {}},
    )


def make_result(site, error=None, **extra):
    return {
        "site_name": site.name,
        "url": f"https://{site.domain}",
        "decorated_rows": [],
        "error": error,
        **extra,
    }


class TransientRetryTests(unittest.TestCase):
    def test_recognizes_confirmed_transport_error_formats(self):
        for error in (
            "timed out",
            "The read operation timed out",
            "<urlopen error timed out>",
            "<urlopen error [Errno 104] Connection reset by peer>",
            "[Errno 54] Connection reset by peer",
            "[WinError 10054] An existing connection was forcibly closed by the remote host",
            "_ssl.c:989: The handshake operation timed out",
            "Remote end closed connection without response",
            "timed out; [Errno 104] Connection reset by peer",
        ):
            with self.subTest(error=error):
                self.assertTrue(shard.is_transient_transport_error(error))

    def test_does_not_retry_http_certificate_parser_or_mixed_errors(self):
        for error in (
            None,
            "",
            "HTTP Error 429: Too Many Requests",
            "HTTP Error 403: Forbidden",
            "HTTP Error 503: Service Unavailable",
            "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed>",
            "Unknown configuration: timeout",
            "Parser failed after timed out response",
            "timed out; HTTP Error 429: Too Many Requests",
            "timed out; certificate verify failed",
            "timed out; ",
        ):
            with self.subTest(error=error):
                self.assertFalse(shard.is_transient_transport_error(error))

    def test_recovery_replaces_failed_result_with_current_data(self):
        site = make_site()
        current = make_result(site, decorated_rows=[{"time": "8:00 am"}])
        results = {site.name: make_result(site, "timed out")}
        with (
            patch.object(shard, "fetch_one", return_value=current) as fetch,
            patch.object(shard, "sleep") as pause,
        ):
            stats = shard.retry_transient_results([site], results, "2026-10-04", "18", set())
        self.assertEqual(stats, (1, 1))
        self.assertIs(results[site.name], current)
        self.assertNotIn("stale", results[site.name])
        fetch.assert_called_once_with(site, "2026-10-04", "18")
        pause.assert_called_once_with(3)

    def test_does_not_retry_successes_direct_or_other_providers(self):
        sites = [make_site("live"), make_site("direct", "direct"), make_site("miclub", "miclub")]
        results = {site.name: make_result(site, None if site.name == "live" else "timed out") for site in sites}
        with patch.object(shard, "fetch_one") as fetch, patch.object(shard, "sleep") as pause:
            self.assertEqual(shard.retry_transient_results(sites, results, "2026-10-04", "18", set()), (0, 0))
        fetch.assert_not_called()
        pause.assert_not_called()

    def test_rate_limit_is_not_retried(self):
        site = make_site()
        results = {site.name: make_result(site, "HTTP Error 429: Too Many Requests")}
        with patch.object(shard, "fetch_one") as fetch, patch.object(shard, "sleep") as pause:
            self.assertEqual(shard.retry_transient_results([site], results, "2026-10-04", "18", set()), (0, 0))
        fetch.assert_not_called()
        pause.assert_not_called()

    def test_domain_is_only_retried_once_across_dates_and_rounds(self):
        first = make_site(domain="QUICK18.example")
        second = make_site("Other course", domain="quick18.example")
        retried_domains = set()
        with (
            patch.object(shard, "fetch_one", return_value=make_result(first, "timed out")) as fetch,
            patch.object(shard, "sleep"),
        ):
            for site, day, holes in ((first, "2026-10-04", "18"), (second, "2026-10-05", "9")):
                results = {site.name: make_result(site, "timed out")}
                shard.retry_transient_results([site], results, day, holes, retried_domains)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(retried_domains, {"quick18.example"})

    def test_shard_budget_is_capped_at_three_domains_even_after_recovery(self):
        sites = [make_site(f"course{number}") for number in range(4)]
        results = {site.name: make_result(site, "timed out") for site in sites}
        with (
            patch.object(shard, "fetch_one", side_effect=lambda site, *_: make_result(site)) as fetch,
            patch.object(shard, "sleep") as pause,
        ):
            stats = shard.retry_transient_results(sites, results, "2026-10-04", "18", set())
        self.assertEqual(stats, (3, 3))
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(pause.call_count, 3)
        self.assertEqual(results[sites[-1].name]["error"], "timed out")

    def test_persistent_failure_keeps_latest_error_and_original_stale_since(self):
        site = make_site()
        results = {site.name: make_result(site, "timed out")}
        failure = make_result(site, "[Errno 104] Connection reset by peer")
        previous = {
            "generated_at": "2026-10-03T23:23:00+00:00",
            "results": [make_result(
                site,
                stale=True,
                stale_since="2026-10-03T23:06:00+00:00",
                stale_reason="prior timeout",
                last_refresh_attempt_at="2026-10-03T23:23:00+00:00",
                decorated_rows=[{"time": "7:00 am"}],
            )],
        }
        with patch.object(shard, "fetch_one", return_value=failure), patch.object(shard, "sleep"):
            stats = shard.retry_transient_results([site], results, "2026-10-04", "18", set())
        self.assertEqual(stats, (1, 0))
        self.assertEqual(results[site.name]["error"], failure["error"])
        reused, did_reuse = shard.reuse_prior_good_result(site, results[site.name], previous)
        self.assertTrue(did_reuse)
        self.assertTrue(reused["stale"])
        self.assertEqual(reused["stale_since"], "2026-10-03T23:06:00+00:00")
        self.assertEqual(reused["stale_reason"], failure["error"])
        self.assertNotEqual(reused["last_refresh_attempt_at"], "2026-10-03T23:23:00+00:00")
        self.assertEqual(reused["decorated_rows"], [{"time": "7:00 am"}])

    def test_unexpected_retry_exception_remains_visible(self):
        site = make_site()
        results = {site.name: make_result(site, "timed out")}
        with patch.object(shard, "fetch_one", side_effect=RuntimeError("parse failure")), patch.object(shard, "sleep"):
            self.assertEqual(shard.retry_transient_results([site], results, "2026-10-04", "18", set()), (1, 0))
        self.assertEqual(results[site.name]["error"], "parse failure")

    def test_main_publishes_recovery_and_preserves_shard_wide_budget(self):
        sites = [make_site(), make_site("other", "miclub"), make_site("third", "miclub")]
        calls = 0

        def fetch(site, *args):
            nonlocal calls
            if site.provider == "quick18":
                calls += 1
                if calls != 2:
                    return make_result(site, "timed out")
            return make_result(site)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            argv = ["refresh_cache_shard.py", "--start-offset", "0", "--days", "1",
                    "--base-date", "2026-10-04", "--output", str(output)]
            with (
                patch("sys.argv", argv),
                patch.object(shard, "load_sites", return_value=sites),
                patch.object(shard, "fetch_one", side_effect=fetch),
                patch.object(shard, "sleep"),
            ):
                self.assertEqual(shard.main(), 0)
            first = json.loads((output / "2026-10-04" / "18.json").read_text())
            second = json.loads((output / "2026-10-04" / "9.json").read_text())
        self.assertEqual(first["health"]["fresh_live_successes"], 3)
        self.assertEqual(first["health"]["transient_retry_recoveries"], 1)
        self.assertEqual(first["health"]["stale_fallbacks"], 0)
        self.assertEqual(second["health"]["fresh_live_successes"], 2)
        self.assertEqual(second["health"]["transient_retries"], 0)
        self.assertEqual(second["results"][0]["error"], "timed out")
        self.assertEqual(calls, 3)

    def test_majority_gate_still_rejects_outage_before_prior_fallback(self):
        sites = [make_site(), make_site("other", "miclub"), make_site("third", "miclub")]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            argv = ["refresh_cache_shard.py", "--start-offset", "0", "--days", "1",
                    "--base-date", "2026-10-04", "--output", str(output)]
            with (
                patch("sys.argv", argv),
                patch.object(shard, "load_sites", return_value=sites),
                patch.object(shard, "fetch_one", side_effect=lambda site, *_: make_result(site, "timed out")),
                patch.object(shard, "load_previous_snapshot") as previous,
                patch.object(shard, "sleep"),
            ):
                with self.assertRaisesRegex(RuntimeError, "0/3 live providers succeeded; 2 required"):
                    shard.main()
            previous.assert_not_called()
            self.assertEqual(list(output.rglob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
