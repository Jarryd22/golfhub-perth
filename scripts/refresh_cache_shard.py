#!/usr/bin/env python3
"""Refresh one shard of the 28-day Golf Hub cache."""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.golfhub_core import CONFIG_FILE, DATA_DIR, fetch_site_result, load_sites
from app.shared_cache import make_snapshot
from app.course_results import direct_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-offset", type=int, required=True)
    parser.add_argument("--days", type=int, default=4)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sites = load_sites(DATA_DIR / CONFIG_FILE)
    def fetch_one(site, date_str, hole_type):
        if (site.provider or "").lower() == "direct":
            return direct_result(site, hole_type, date_str)
        return fetch_site_result(site, date_str, hole_type, None, None, None)
    today = datetime.now(ZoneInfo("Australia/Perth")).date()
    args.output.mkdir(parents=True, exist_ok=True)

    for offset in range(args.start_offset, args.start_offset + args.days):
        date_str = (today + timedelta(days=offset)).isoformat()
        for hole_type in ("18", "9"):
            eligible = [site for site in sites if hole_type in site.holes]
            by_name = {}
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                jobs = {
                    pool.submit(fetch_one, site, date_str, hole_type): site
                    for site in eligible
                }
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
            payload = make_snapshot(date_str, hole_type, [by_name[site.name] for site in eligible])
            target = args.output / date_str / f"{hole_type}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Wrote {target} ({len(eligible)} course results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
