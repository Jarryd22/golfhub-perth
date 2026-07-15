#!/usr/bin/env python3
"""Fetch one shared weather forecast per GolfHub course location."""
from __future__ import annotations

import argparse
import json
import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from time import sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.golfhub_core import (
    CONFIG_FILE,
    DATA_DIR,
    get_weather_for_date,
    load_sites,
    preload_weather_cache,
    weather_cache_snapshot,
)


def prepare_forecasts(
    queries: list[str],
    base_date: date,
    workers: int,
    retry_delays: tuple[float, ...] = (2.0, 5.0),
) -> dict[str, dict[str, dict]]:
    """Fetch all locations, then retry only empty forecasts sequentially.

    The second pass avoids short Open-Meteo rate-limit bursts without turning a
    weather problem into a tee-time outage.
    """
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(lambda query: get_weather_for_date(query, base_date.isoformat(), None), queries))

    forecasts = weather_cache_snapshot()
    for delay in retry_delays:
        empty = [query for query in queries if not forecasts.get(query)]
        if not empty:
            break
        logging.warning("Retrying %d empty weather forecasts after %.1fs", len(empty), delay)
        sleep(delay)
        preload_weather_cache({query: value for query, value in forecasts.items() if value})
        for query in empty:
            get_weather_for_date(query, base_date.isoformat(), None)
        forecasts = weather_cache_snapshot()
    return forecasts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    base_date = date.fromisoformat(args.base_date)

    sites = load_sites(DATA_DIR / CONFIG_FILE)
    queries = sorted({site.weather_query for site in sites if site.weather_query})
    forecasts = prepare_forecasts(queries, base_date, args.workers)
    missing = sorted(set(queries).difference(forecasts))
    if missing:
        raise RuntimeError(f"Weather preparation omitted {len(missing)} locations")

    payload = {
        "schema": 1,
        "base_date": base_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "forecasts": forecasts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(args.output)
    available = sum(bool(value) for value in forecasts.values())
    print(f"Prepared {len(forecasts)} course forecasts ({available} currently available)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())