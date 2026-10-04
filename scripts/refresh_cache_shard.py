#!/usr/bin/env python3
"""Refresh one deterministic shard of the 28-day GolfHub cache."""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from time import sleep
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.course_results import direct_result
from app.golfhub_core import (
    CONFIG_FILE,
    DATA_DIR,
    fetch_site_result,
    load_sites,
    preload_weather_cache,
)
from app.shared_cache import make_snapshot, validate_snapshot

PERTH = ZoneInfo("Australia/Perth")
MAX_TRANSIENT_RETRY_DOMAINS = 3
TRANSIENT_RETRY_DELAY_SECONDS = 3
MAX_PROVIDER_TRANSPORT_FAILURES = 2
REFRESH_SKIP_FIELDS = (
    "refresh_skipped", "refresh_skip_reason", "last_refresh_skipped_at",
    "provider_last_error", "provider_last_attempt_at", "provider_transient_failures",
)


def parse_base_date(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now(PERTH).date()


def minimum_live_successes(live_provider_count: int) -> int:
    """Require a strict majority of live providers to refresh successfully."""
    return live_provider_count // 2 + 1 if live_provider_count else 0


def load_weather_artifact(path: Path | None, base_date: date, sites) -> None:
    if path is None:
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != 1 or payload.get("base_date") != base_date.isoformat():
        raise ValueError("Weather artifact does not match this cache run")
    forecasts = payload.get("forecasts")
    if not isinstance(forecasts, dict):
        raise ValueError("Weather artifact has no forecasts mapping")
    expected_queries = {site.weather_query for site in sites if site.weather_query}
    missing = sorted(expected_queries.difference(forecasts))
    if missing:
        raise ValueError(f"Weather artifact is missing {len(missing)} course locations")
    # Empty mappings are intentional negative-cache entries. Once preloaded,
    # shards never call the weather provider independently.
    preload_weather_cache(forecasts)


def load_previous_snapshot(root: Path | None, date_str: str, hole_type: str) -> dict | None:
    if root is None:
        return None
    path = root / date_str / f"{hole_type}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return validate_snapshot(payload, date_str, hole_type)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def reuse_prior_good_result(site, fresh: dict, previous: dict | None) -> tuple[dict, bool]:
    """Substitute a prior same-course result after an isolated live failure."""
    if site.provider == "direct" or not fresh.get("error") or not previous:
        return fresh, False
    prior_by_name = {
        result.get("site_name"): result
        for result in previous.get("results", [])
        if isinstance(result, dict) and result.get("site_name")
    }
    prior = prior_by_name.get(site.name)
    if not isinstance(prior, dict) or prior.get("error"):
        return fresh, False
    reused = dict(prior)
    reused["error"] = None
    reused["stale"] = True
    reused["stale_reason"] = str(fresh.get("error"))
    reused["stale_since"] = reused.get("stale_since") or previous.get("generated_at")
    # A circuit skip did not request this date/round. Keep its prior actual
    # attempt timestamp, and label the domain's last observed failure separately.
    for key in REFRESH_SKIP_FIELDS:
        reused.pop(key, None)
    if fresh.get("refresh_skipped"):
        reused.update({key: fresh[key] for key in REFRESH_SKIP_FIELDS if key in fresh})
    else:
        reused["last_refresh_attempt_at"] = fresh.get("last_refresh_attempt_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return reused, True


def fetch_one(site, date_str: str, hole_type: str) -> dict:
    if site.provider == "direct":
        return direct_result(site, hole_type, date_str)
    return fetch_site_result(site, date_str, hole_type, None, None, None)


def is_transient_transport_error(error) -> bool:
    """Recognize only transport failures retained as strings by the core fetcher."""
    if not isinstance(error, str) or not error.strip():
        return False
    for part in error.lower().split(";"):
        part = part.strip()
        if part.startswith("<urlopen error ") and part.endswith(">"):
            part = part[len("<urlopen error "):-1]
        # Full matches keep HTTP errors, certificate failures, parser errors,
        # and mixed transport/HTTP failures out of the retry path.
        if not re.fullmatch(
            r"timed out|the read operation timed out|"
            r"(?:_ssl\.c:\d+: )?the handshake operation timed out|"
            r"(?:\[errno (?:54|104)\] )?connection reset by peer|"
            r"\[winerror 10054\] an existing connection was forcibly closed by the remote host\.?|"
            r"remote end closed connection without response",
            part,
        ):
            return False
    return True


def failed_result(site, hole_type: str, error: str) -> dict:
    return {
        "site_name": site.name,
        "url": f"https://{site.domain}",
        "hole_label": f"{hole_type} holes",
        "decorated_rows": [],
        "error": error,
        "not_configured": False,
    }


@dataclass
class _ProviderState:
    lock: Lock = field(default_factory=Lock)
    failures: int = 0
    last_error: str = ""
    last_attempt_at: str | None = None


class ProviderCircuit:
    """Limit failed Quick18 fetches across all dates, rounds and retries.

    Two logical transport failures exhaust the domain's budget for this shard.
    Successes do not reset the budget: intermittent timeouts must also be bounded.
    Each main invocation starts fresh, so the next shard/run probes normally.
    This bounds requests, not the duration of an individual socket operation.
    """

    def __init__(self):
        self._states: dict[str, _ProviderState] = {}
        self._lock = Lock()

    def _state(self, site) -> _ProviderState:
        with self._lock:
            return self._states.setdefault(site.domain.lower(), _ProviderState())

    def is_open(self, site) -> bool:
        if site.provider != "quick18":
            return False
        state = self._state(site)
        with state.lock:
            return state.failures >= MAX_PROVIDER_TRANSPORT_FAILURES

    def fetch(self, site, date_str: str, hole_type: str) -> dict:
        if site.provider != "quick18":
            return fetch_one(site, date_str, hole_type)
        state = self._state(site)
        # Serialize aliases sharing a domain so simultaneous jobs cannot exceed
        # its failure budget. Unrelated providers remain parallel.
        with state.lock:
            if state.failures >= MAX_PROVIDER_TRANSPORT_FAILURES:
                result = failed_result(
                    site, hole_type,
                    f"Quick18 provider circuit open after {state.failures} transport failures; "
                    f"request skipped for {date_str} {hole_type} holes. "
                    f"Last observed provider error: {state.last_error}",
                )
                result.update(
                    refresh_skipped=True,
                    refresh_skip_reason="provider_circuit_open",
                    last_refresh_skipped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    provider_last_error=state.last_error,
                    provider_last_attempt_at=state.last_attempt_at,
                    provider_transient_failures=state.failures,
                )
                return result
            state.last_attempt_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                result = fetch_one(site, date_str, hole_type)
            except Exception as exc:
                result = failed_result(site, hole_type, str(exc))
            result["last_refresh_attempt_at"] = state.last_attempt_at
            if is_transient_transport_error(result.get("error")):
                state.failures += 1
                state.last_error = result["error"]
                if state.failures >= MAX_PROVIDER_TRANSPORT_FAILURES:
                    print(
                        f"::warning::Quick18 circuit opened for {site.domain}: "
                        f"{state.failures} transport failures; remaining date/round requests "
                        "in this shard will be skipped. The next run starts with a fresh budget.",
                        flush=True,
                    )
            return result


def retry_transient_results(
    sites, by_name: dict[str, dict], date_str: str, hole_type: str, retried_domains: set[str],
    circuit: ProviderCircuit | None = None,
) -> tuple[int, int]:
    """Give isolated Quick18 failures one delayed, serial chance per domain/shard.

    Quick18 already retries once inside fetch_site_text. This later attempt is
    deliberately limited to three domains across the entire shard, adding at
    most six HTTP requests with today's one-URL Quick18 fetch path. Persistent
    failures therefore cannot start a retry sweep over every date and round.
    """
    attempts = recovered = 0
    for site in sites:
        failed = by_name[site.name]
        domain = site.domain.lower()
        if (
            site.provider != "quick18"
            or domain in retried_domains
            or len(retried_domains) >= MAX_TRANSIENT_RETRY_DOMAINS
            or (circuit is not None and circuit.is_open(site))
            or not is_transient_transport_error(failed.get("error"))
        ):
            continue
        retried_domains.add(domain)
        attempts += 1
        print(
            f"Delayed cache retry for {site.name} {date_str} {hole_type} holes "
            f"after transport failure: {failed['error']}"
        )
        sleep(TRANSIENT_RETRY_DELAY_SECONDS)
        try:
            result = circuit.fetch(site, date_str, hole_type) if circuit is not None else fetch_one(site, date_str, hole_type)
        except Exception as exc:
            result = {**failed, "error": str(exc)}
        by_name[site.name] = result
        if result.get("error"):
            print(f"Delayed cache retry failed for {site.name}: {result['error']}")
        else:
            recovered += 1
            print(f"Delayed cache retry recovered {site.name} {date_str} {hole_type} holes")
    return attempts, recovered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-offset", type=int, required=True)
    parser.add_argument("--days", type=int, default=4)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-date", help="Shared Perth date in YYYY-MM-DD form")
    parser.add_argument("--fallback", type=Path, help="Previous cache-branch snapshot root")
    parser.add_argument("--weather-cache", type=Path, help="Prepared run-wide weather artifact")
    args = parser.parse_args()

    if args.start_offset < 0 or args.days < 1 or args.start_offset + args.days > 28:
        parser.error("shard offsets must stay inside the 0..27 cache window")

    base_date = parse_base_date(args.base_date)
    sites = load_sites(DATA_DIR / CONFIG_FILE)
    load_weather_artifact(args.weather_cache, base_date, sites)
    args.output.mkdir(parents=True, exist_ok=True)
    retried_domains: set[str] = set()
    circuit = ProviderCircuit()

    for offset in range(args.start_offset, args.start_offset + args.days):
        date_str = (base_date + timedelta(days=offset)).isoformat()
        for hole_type in ("18", "9"):
            eligible = [site for site in sites if hole_type in site.holes]
            by_name: dict[str, dict] = {}
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                jobs = {pool.submit(circuit.fetch, site, date_str, hole_type): site for site in eligible}
                for job in as_completed(jobs):
                    site = jobs[job]
                    try:
                        by_name[site.name] = job.result()
                    except Exception as exc:
                        by_name[site.name] = failed_result(site, hole_type, str(exc))

            retry_attempts, retry_recoveries = retry_transient_results(
                eligible, by_name, date_str, hole_type, retried_domains, circuit
            )
            live_sites = [site for site in eligible if site.provider != "direct"]
            fresh_live_successes = sum(not by_name[site.name].get("error") for site in live_sites)
            required = minimum_live_successes(len(live_sites))
            if fresh_live_successes < required:
                raise RuntimeError(
                    f"Health gate failed for {date_str} {hole_type} holes: "
                    f"{fresh_live_successes}/{len(live_sites)} live providers succeeded; {required} required"
                )

            previous = load_previous_snapshot(args.fallback, date_str, hole_type)
            stale_fallbacks = 0
            results = []
            for site in eligible:
                result, reused = reuse_prior_good_result(site, by_name[site.name], previous)
                stale_fallbacks += int(reused)
                results.append(result)

            direct_failures = [
                site.name
                for site in eligible
                if site.provider == "direct" and by_name[site.name].get("error")
            ]
            if direct_failures:
                raise RuntimeError(f"Direct booking result construction failed: {', '.join(direct_failures)}")

            payload = make_snapshot(date_str, hole_type, results)
            circuit_skips = sum(bool(result.get("refresh_skipped")) for result in by_name.values())
            payload["health"] = {
                "live_provider_count": len(live_sites),
                "fresh_live_successes": fresh_live_successes,
                "minimum_live_successes": required,
                "stale_fallbacks": stale_fallbacks,
                "transient_retries": retry_attempts,
                "transient_retry_recoveries": retry_recoveries,
                "provider_circuit_skips": circuit_skips,
            }
            target = args.output / date_str / f"{hole_type}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(target)
            print(
                f"Wrote {target} ({len(results)} courses, "
                f"{fresh_live_successes}/{len(live_sites)} fresh live, {stale_fallbacks} stale fallbacks, "
                f"{circuit_skips} provider circuit skips)",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
