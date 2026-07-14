#!/usr/bin/env python3
"""Validate, prune, and index the merged 28-day cache."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "public" / "cache"
today = datetime.now(ZoneInfo("Australia/Perth")).date()
valid_dates = {(today + timedelta(days=offset)).isoformat() for offset in range(28)}

for item in CACHE.iterdir():
    if item.is_dir() and item.name not in valid_dates:
        shutil.rmtree(item)

dates = []
for date_str in sorted(valid_dates):
    directory = CACHE / date_str
    holes = [hole for hole in ("18", "9") if (directory / f"{hole}.json").exists()]
    if holes:
        dates.append({"date": date_str, "holes": holes})

index = {
    "schema": 1,
    "generated_at": datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"),
    "range_days": 28,
    "refresh_minutes": 10,
    "dates": dates,
}
(CACHE / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
print(f"Indexed {len(dates)} cached days")
