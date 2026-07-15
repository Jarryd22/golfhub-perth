#!/usr/bin/env python3
"""Strictly validate and index a complete 28-day cache snapshot."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.golfhub_core import CONFIG_FILE, DATA_DIR, load_sites

PERTH = ZoneInfo("Australia/Perth")


class CacheValidationError(ValueError):
    pass


def parse_base_date(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now(PERTH).date()


def _validate_timestamp(value, label: str) -> None:
    if not isinstance(value, str):
        raise CacheValidationError(f"{label} has no generated_at timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CacheValidationError(f"{label} has an invalid generated_at timestamp") from exc
    if stamp.tzinfo is None:
        raise CacheValidationError(f"{label} generated_at must include a timezone")


def _validate_snapshot(path: Path, date_str: str, hole_type: str, expected_sites) -> None:
    label = path.as_posix()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CacheValidationError(f"{label} is not readable JSON") from exc

    if payload.get("schema") != 1:
        raise CacheValidationError(f"{label} has the wrong schema")
    if payload.get("date") != date_str or str(payload.get("holes")) != hole_type:
        raise CacheValidationError(f"{label} metadata does not match its path")
    _validate_timestamp(payload.get("generated_at"), label)

    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(expected_sites):
        raise CacheValidationError(
            f"{label} expected {len(expected_sites)} course results, found "
            f"{len(results) if isinstance(results, list) else 'no list'}"
        )
    by_name = {
        result.get("site_name"): result
        for result in results
        if isinstance(result, dict) and isinstance(result.get("site_name"), str)
    }
    expected_names = {site.name for site in expected_sites}
    if len(by_name) != len(results) or set(by_name) != expected_names:
        raise CacheValidationError(f"{label} has missing or duplicate course names")

    for site in expected_sites:
        result = by_name[site.name]
        if site.provider == "direct":
            if result.get("direct_booking") is not True or not str(result.get("url", "")).startswith("https://"):
                raise CacheValidationError(f"{label} has an invalid direct-booking result for {site.name}")

    live_count = sum(site.provider != "direct" for site in expected_sites)
    minimum = live_count // 2 + 1 if live_count else 0
    health = payload.get("health")
    if not isinstance(health, dict):
        raise CacheValidationError(f"{label} has no health metadata")
    try:
        reported_count = int(health.get("live_provider_count"))
        fresh_successes = int(health.get("fresh_live_successes"))
        reported_minimum = int(health.get("minimum_live_successes"))
        stale_fallbacks = int(health.get("stale_fallbacks"))
    except (TypeError, ValueError) as exc:
        raise CacheValidationError(f"{label} has invalid health metadata") from exc
    if reported_count != live_count or reported_minimum != minimum:
        raise CacheValidationError(f"{label} health provider counts are inconsistent")
    if fresh_successes < minimum or fresh_successes > live_count:
        raise CacheValidationError(f"{label} failed the live-provider health gate")
    if stale_fallbacks < 0 or stale_fallbacks > live_count:
        raise CacheValidationError(f"{label} has an invalid stale fallback count")


def build_cache_index(cache: Path, base_date: date, sites=None) -> dict:
    if not cache.is_dir():
        raise CacheValidationError(f"Cache directory does not exist: {cache}")
    sites = sites or load_sites(DATA_DIR / CONFIG_FILE)
    expected_dates = [(base_date + timedelta(days=offset)).isoformat() for offset in range(28)]
    expected_date_set = set(expected_dates)
    actual_date_set = {item.name for item in cache.iterdir() if item.is_dir()}
    if actual_date_set != expected_date_set:
        missing = sorted(expected_date_set - actual_date_set)
        unexpected = sorted(actual_date_set - expected_date_set)
        raise CacheValidationError(f"Cache date directories incomplete; missing={missing}, unexpected={unexpected}")

    expected_files = {f"{date_str}/{hole}.json" for date_str in expected_dates for hole in ("18", "9")}
    actual_files = {
        path.relative_to(cache).as_posix()
        for path in cache.rglob("*.json")
        if path.name != "index.json"
    }
    if actual_files != expected_files:
        raise CacheValidationError(
            f"Cache must contain exactly 56 snapshots; missing={sorted(expected_files - actual_files)}, "
            f"unexpected={sorted(actual_files - expected_files)}"
        )

    dates = []
    for date_str in expected_dates:
        for hole_type in ("18", "9"):
            expected_sites = [site for site in sites if hole_type in site.holes]
            _validate_snapshot(cache / date_str / f"{hole_type}.json", date_str, hole_type, expected_sites)
        dates.append({"date": date_str, "holes": ["18", "9"]})

    index = {
        "schema": 1,
        "generated_at": datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"),
        "range_days": 28,
        "refresh_minutes": 10,
        "dates": dates,
    }
    target = cache / "index.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, indent=2), encoding="utf-8")
    temporary.replace(target)
    print(f"Validated and indexed {len(dates)} complete cached days")
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / "public" / "cache")
    parser.add_argument("--base-date")
    args = parser.parse_args()
    try:
        build_cache_index(args.cache, parse_base_date(args.base_date))
    except CacheValidationError as exc:
        print(f"Cache validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())