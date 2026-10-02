#!/usr/bin/env python3
"""Report published-cache age and coalesce nearby automatic refresh triggers."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

COALESCE_MINUTES = 5
STALE_MINUTES = 20


def cache_age(cache: Path, base_date: date, now: datetime) -> float:
    """Trust only a complete current-window index with an aware, nonfuture stamp.

    The publisher already validates schemas and provider health. Do not rewrite
    the index here: its original timestamp is the evidence of publication age.
    """
    index = json.loads((cache / "index.json").read_text(encoding="utf-8"))
    expected = [
        {"date": (base_date + timedelta(days=offset)).isoformat(), "holes": ["18", "9"]}
        for offset in range(28)
    ]
    if not isinstance(index, dict) or index.get("schema") != 1 or index.get("range_days") != 28:
        raise ValueError("invalid index schema or range")
    if index.get("dates") != expected:
        raise ValueError("index does not cover the current 28 Perth dates")
    for entry in expected:
        for holes in entry["holes"]:
            if not (cache / entry["date"] / f"{holes}.json").is_file():
                raise ValueError("published snapshot is missing")
    stamp = datetime.fromisoformat(index["generated_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("index timestamp has no timezone")
    minutes = (now - stamp).total_seconds() / 60
    if minutes < 0:
        raise ValueError("index timestamp is in the future")
    return minutes


def refresh_status(cache: Path, base_date: date, event: str, now: datetime) -> tuple[bool, str]:
    try:
        age = cache_age(cache, base_date, now)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return True, "Prior cache is missing, incomplete, or has an invalid timestamp; refresh required."
    detail = f"Prior complete cache age: {age:.1f} minutes."
    if age > STALE_MINUTES:
        detail += f" STALE: exceeds the {STALE_MINUTES}-minute freshness threshold."
    if event in {"schedule", "workflow_run"} and age < COALESCE_MINUTES:
        return False, detail + f" Skipped duplicate automatic refresh (under {COALESCE_MINUTES} minutes)."
    return True, detail + " Refresh required (manual and source-change runs always refresh)."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--base-date", type=date.fromisoformat, required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--heartbeat-run", default="")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    refresh, detail = refresh_status(args.cache, args.base_date, args.event, datetime.now(timezone.utc))
    with args.output.open("a", encoding="utf-8") as output:
        output.write(f"refresh={str(refresh).lower()}\n")
    with args.summary.open("a", encoding="utf-8") as summary:
        summary.write(f"### Cache freshness before refresh\n\nTrigger: `{args.event}`\n\n{detail}\n")
        if args.heartbeat_run:
            summary.write(f"\nAlert heartbeat: {args.heartbeat_run}\n")
        summary.write("\nIndex age describes the published batch; individual courses may use stale fallback results.\n")
    print(detail)
    if "STALE:" in detail:
        print(f"::warning::{detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
