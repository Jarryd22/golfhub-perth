#!/usr/bin/env python3
"""Fetch one shared weather forecast per GolfHub course location."""
from __future__ import annotations

import argparse
import json
import sys
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from time import sleep
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.golfhub_core import (
    CONFIG_FILE,
    DATA_DIR,
    WeatherRetryBudget,
    get_weather_for_date,
    load_sites,
    preload_weather_cache,
    weather_cache_snapshot,
)


def prepare_forecasts(
    queries: list[str],
    base_date: date,
    workers: int,
    retry_delays: tuple[float, ...] = (),
    checkpoint: Callable[[dict], None] | None = None,
) -> dict[str, dict[str, dict]]:
    """Fetch each location with a shared, bounded timeout retry allowance.

    Production never sweeps empty forecasts: they can mean HTTP 429. Only typed
    transport timeouts qualify for one retry, at most four extras per run, all
    inside the existing killable worker and its unchanged preparation deadline.
    """
    retry_budget = WeatherRetryBudget()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = [pool.submit(get_weather_for_date, query, base_date.isoformat(), None,
                            retry_budget=retry_budget) for query in queries]
        for job in as_completed(jobs):
            job.result()
            if checkpoint:
                checkpoint(weather_cache_snapshot())

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


def write_artifact(path: Path, base_date: date, queries: list[str], forecasts: dict, **metadata) -> dict:
    payload = {
        "schema": 1,
        "base_date": base_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # All locations must be present, including unavailable ones, so seven
        # shards cannot turn weather failure into a fresh burst of requests.
        "forecasts": {query: forecasts.get(query, {}) for query in queries},
        **metadata,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return payload


def prepare_bounded(
    output: Path, base_date: date, queries: list[str], workers: int, budget_seconds: float,
    *, worker_command: list[str] | None = None,
) -> dict:
    """Isolate network work in a killable process, retaining atomic checkpoints.

    A timeout on a Future is insufficient: ThreadPoolExecutor waits for its
    threads when exiting. subprocess.run kills and waits for the worker instead.
    """
    write_artifact(output, base_date, queries, {})
    command = worker_command or [
        sys.executable, str(Path(__file__).resolve()), "--fetch-worker",
        "--base-date", base_date.isoformat(), "--workers", str(workers),
        "--output", str(output),
    ]
    status = "complete"
    try:
        subprocess.run(command, timeout=budget_seconds, check=True)
    except subprocess.TimeoutExpired:
        status = "timed_out"
    except (subprocess.CalledProcessError, OSError):
        status = "worker_failed"

    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("schema") != 1 or payload.get("base_date") != base_date.isoformat():
            raise ValueError("Weather checkpoint belongs to a different run")
        forecasts = payload["forecasts"]
        if not isinstance(forecasts, dict) or any(
            not isinstance(value, dict) or any(not isinstance(day, dict) for day in value.values())
            for value in forecasts.values()
        ):
            raise ValueError("Invalid forecast checkpoint")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        forecasts = {}
        status = "invalid_checkpoint"

    unavailable = [query for query in queries if not forecasts.get(query)]
    if unavailable and status == "complete":
        status = "partial"
    payload = write_artifact(
        output, base_date, queries, forecasts,
        preparation={"status": status, "budget_seconds": budget_seconds, "unavailable_locations": unavailable},
    )
    message = (
        f"Weather preparation {status}: {len(queries) - len(unavailable)}/{len(queries)} "
        f"locations available; network budget {budget_seconds:g}s. "
        "Unavailable weather will not be fetched again by tee-time shards."
    )
    print(f"::warning::{message}" if status != "complete" else message, flush=True)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(f"\n### Shared weather\n\n{message}\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--budget-seconds", type=float, default=90)
    parser.add_argument("--fetch-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0 < args.budget_seconds <= 120:
        parser.error("weather budget must be between 0 and 120 seconds")
    base_date = date.fromisoformat(args.base_date)

    sites = load_sites(DATA_DIR / CONFIG_FILE)
    queries = sorted({site.weather_query for site in sites if site.weather_query})
    if args.fetch_worker:
        checkpoint = lambda forecasts: write_artifact(args.output, base_date, queries, forecasts)
        checkpoint(prepare_forecasts(queries, base_date, args.workers, checkpoint=checkpoint))
    else:
        prepare_bounded(args.output, base_date, queries, args.workers, args.budget_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
