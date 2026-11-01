"""Offline provider-exception regressions at core and cache producer boundaries."""
from concurrent.futures import Future
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import golfhub_core as core
from app.shared_cache import make_snapshot
from scripts import refresh_cache_shard as shard


class ImmediateExecutor:
    """Completed local futures; never start provider threads in shard tests."""

    def __init__(self, **_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def submit(self, function, *args):
        future = Future()
        try:
            future.set_result(function(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future


class CacheProviderExceptionTests(unittest.TestCase):
    date = "2033-01-02"

    def setUp(self):
        self.enterContext(patch("socket.create_connection", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Offline test")))
        self.enterContext(patch("webbrowser.open", side_effect=AssertionError("Offline test")))
        self.enterContext(patch.object(core, "get_weather_for_date", return_value=None))
        self.enterContext(patch.object(core, "save_debug_html"))
        self.enterContext(patch("sys.stdout", new_callable=io.StringIO))
        self.runtime = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="golfhub-provider-errors-")))

    @staticmethod
    def site(name="Fixture", provider="miclub", *, domain=None, urls=None):
        domain = domain or f"{name.lower()}.example.invalid"
        return SimpleNamespace(
            name=name, provider=provider, domain=domain, weather_query=None,
            holes={key: SimpleNamespace(booking_resource_id="3000000") for key in ("18", "9")},
            build_urls=lambda *_: urls or [f"https://{domain}/fixture"],
        )

    @staticmethod
    def result(site, **extra):
        return {"site_name": site.name, "url": f"https://{site.domain}",
                "decorated_rows": [], "error": None, **extra}

    def fetch_core(self, site):
        return core.fetch_site_result(site, self.date, "18", None, None, None)

    def run_shard(self, sites, fetch, *, previous=None):
        output = self.runtime / "output"
        args = ["offline-shard-test", "--start-offset", "0", "--days", "1",
                "--base-date", self.date, "--output", str(output)]
        if previous is not None:
            fallback = self.runtime / "previous"
            args.extend(["--fallback", str(fallback)])
            for holes in ("18", "9"):
                path = fallback / self.date / f"{holes}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(make_snapshot(self.date, holes, previous)), encoding="utf-8")
        with (
            patch("sys.argv", args),
            patch.object(shard, "load_sites", return_value=sites),
            patch.object(shard, "load_weather_artifact") as weather,
            patch.object(shard, "fetch_one", side_effect=fetch),
            patch.object(shard, "ThreadPoolExecutor", ImmediateExecutor),
            patch.object(shard, "sleep", side_effect=AssertionError("No retry expected")),
        ):
            code = shard.main()
        self.assertEqual(code, 0)
        weather.assert_called_once()
        return [json.loads((output / self.date / f"{holes}.json").read_text()) for holes in ("18", "9")]

    def test_blank_page_exceptions_remain_failed_provider_results(self):
        site = self.site()
        for exception in (TimeoutError(), RuntimeError(), ValueError(" \t\n")):
            with self.subTest(exception=type(exception).__name__):
                with patch.object(core, "fetch_site_text", side_effect=exception) as fetch:
                    result = self.fetch_core(site)
                self.assertEqual(result["error"], type(exception).__name__)
                self.assertEqual(result["decorated_rows"], [])
                self.assertFalse(result["not_configured"])
                fetch.assert_called_once()

    def test_nonblank_provider_diagnostics_are_preserved_exactly(self):
        for message in ("timed out", "  HTTP Error 403: Forbidden  ", "Parser failed"):
            with self.subTest(message=message):
                with patch.object(core, "fetch_site_text", side_effect=RuntimeError(message)):
                    self.assertEqual(self.fetch_core(self.site())["error"], message)

    def test_multi_page_failures_retain_both_exception_diagnostics(self):
        site = self.site(urls=["https://example.invalid/one", "https://example.invalid/two"])
        with patch.object(core, "fetch_site_text", side_effect=[TimeoutError(), RuntimeError("HTTP Error 403: Forbidden")]) as fetch:
            result = self.fetch_core(site)
        self.assertEqual(result["error"], "TimeoutError; HTTP Error 403: Forbidden")
        self.assertEqual(fetch.call_count, 2)
        self.assertFalse(shard.is_transient_transport_error(result["error"]))

    def test_blank_wembley_calendar_exception_remains_failed(self):
        site = self.site("Wembley", domain="wembleygolf.com.au")
        with (
            patch.object(core, "fetch_text", side_effect=TimeoutError()) as calendar,
            patch.object(core, "fetch_site_text") as timesheet,
        ):
            result = self.fetch_core(site)
        self.assertEqual(result["error"], "TimeoutError")
        self.assertEqual(result["decorated_rows"], [])
        self.assertNotIn("calendar_availability", result)
        calendar.assert_called_once()
        timesheet.assert_not_called()

    def test_blank_outer_processing_exception_remains_failed(self):
        with (
            patch.object(core, "fetch_site_text", return_value="<html></html>"),
            patch.object(core, "parse_timesheet", return_value=[]),
            patch.object(core, "decorate_rows", side_effect=RuntimeError()),
        ):
            result = self.fetch_core(self.site())
        self.assertEqual(result["error"], "RuntimeError")
        self.assertEqual(result["decorated_rows"], [])

    def test_successfully_checked_empty_page_remains_an_empty_success(self):
        with (
            patch.object(core, "fetch_site_text", return_value="<html>No tee times</html>"),
            patch.object(core, "parse_timesheet", return_value=[]),
        ):
            result = self.fetch_core(self.site())
        self.assertIsNone(result["error"])
        self.assertEqual(result["decorated_rows"], [])

    def test_blank_retry_exception_is_not_a_recovery_or_a_new_retry_class(self):
        site = self.site(provider="quick18")
        for exception in (TimeoutError(), RuntimeError(" \t")):
            with self.subTest(exception=type(exception).__name__):
                results = {site.name: self.result(site, error="timed out")}
                domains = set()
                with patch.object(shard, "fetch_one", side_effect=exception) as fetch, patch.object(shard, "sleep") as pause:
                    stats = shard.retry_transient_results([site], results, self.date, "18", domains)
                self.assertEqual(stats, (1, 0))
                self.assertEqual(results[site.name]["error"], type(exception).__name__)
                self.assertEqual(domains, {site.domain})
                self.assertFalse(shard.is_transient_transport_error(results[site.name]["error"]))
                fetch.assert_called_once()
                pause.assert_called_once_with(shard.TRANSIENT_RETRY_DELAY_SECONDS)

    def test_blank_worker_failures_do_not_pass_the_fresh_majority_gate(self):
        sites = [self.site(f"Course{i}") for i in range(3)]

        def failed_fetch(*_):
            raise TimeoutError()

        with patch.object(shard, "load_previous_snapshot") as previous:
            with self.assertRaisesRegex(RuntimeError, "0/3 live providers succeeded; 2 required"):
                self.run_shard(sites, failed_fetch)
        previous.assert_not_called()
        self.assertEqual(list((self.runtime / "output").rglob("*.json")), [])

    def test_blank_worker_failure_is_published_as_unknown_when_majority_succeeds(self):
        failed = self.site("Failed")
        sites = [failed, self.site("Healthy1"), self.site("Healthy2")]

        def fetch(site, *_):
            if site is failed:
                raise RuntimeError()
            return self.result(site)

        for payload in self.run_shard(sites, fetch):
            result = next(r for r in payload["results"] if r["site_name"] == failed.name)
            self.assertEqual(payload["health"]["fresh_live_successes"], 2)
            self.assertEqual(payload["health"]["stale_fallbacks"], 0)
            self.assertEqual(result["error"], "RuntimeError")
            self.assertEqual(result["decorated_rows"], [])

    def test_blank_worker_failure_can_reuse_prior_good_data_with_stale_reason(self):
        failed = self.site("Failed")
        sites = [failed, self.site("Healthy1"), self.site("Healthy2")]
        prior = self.result(failed, decorated_rows=[{"time": "8:00 am", "minutes": 480, "spots": 4}],
                            stale=True, stale_since="2033-01-01T00:00:00Z")

        def fetch(site, *_):
            if site is failed:
                raise TimeoutError()
            return self.result(site)

        for payload in self.run_shard(sites, fetch, previous=[prior]):
            result = next(r for r in payload["results"] if r["site_name"] == failed.name)
            self.assertEqual(payload["health"]["fresh_live_successes"], 2)
            self.assertEqual(payload["health"]["stale_fallbacks"], 1)
            self.assertTrue(result["stale"])
            self.assertEqual(result["stale_reason"], "TimeoutError")
            self.assertEqual(result["stale_since"], prior["stale_since"])
            self.assertEqual(result["decorated_rows"], prior["decorated_rows"])
            self.assertIsNone(result["error"])

    def test_blank_direct_constructor_exception_still_blocks_publication(self):
        direct = self.site("Direct", provider="direct")
        sites = [self.site("Healthy"), direct]

        def fetch(site, *_):
            if site is direct:
                raise RuntimeError()
            return self.result(site)

        with self.assertRaisesRegex(RuntimeError, "Direct booking result construction failed: Direct"):
            self.run_shard(sites, fetch)
        self.assertEqual(list((self.runtime / "output").rglob("*.json")), [])
