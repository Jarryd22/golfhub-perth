#!/usr/bin/env python3
"""Refresh one deterministic shard of the 28-day GolfHub cache."""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
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
    reused["last_refresh_attempt_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return reused, True


def fetch_one(site, date_str: str, hole_type: str) -> dict:
    if site.provider == "direct":
        return direct_result(site, hole_type, date_str)
    return fetch_site_result(site, date_str, hole_type, None, None, None)


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

    for offset in range(args.start_offset, args.start_offset + args.days):
        date_str = (base_date + timedelta(days=offset)).isoformat()
        for hole_type in ("18", "9"):
            eligible = [site for site in sites if hole_type in site.holes]
            by_name: dict[str, dict] = {}
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                jobs = {pool.submit(fetch_one, site, date_str, hole_type): site for site in eligible}
                for job in as_completed(jobs):
                    site = jobs[job]
                    try:
                        by_name[site.name] = job.result()
                    except Exception as exc:
                        by_name[site.name] = {
                            "site_name": site.name,
                            "url": f"https://{site.domain}",
                            "hole_label": f"{hole_type} holes",
                            "decorated_rows": [],
                            "error": str(exc),
                            "not_configured": False,
                        }

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
            payload["health"] = {
                "live_provider_count": len(live_sites),
                "fresh_live_successes": fresh_live_successes,
                "minimum_live_successes": required,
                "stale_fallbacks": stale_fallbacks,
            }
            target = args.output / date_str / f"{hole_type}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(target)
            print(
                f"Wrote {target} ({len(results)} courses, "
                f"{fresh_live_successes}/{len(live_sites)} fresh live, {stale_fallbacks} stale fallbacks)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())