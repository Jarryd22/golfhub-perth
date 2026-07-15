#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.golfhub_core import CONFIG_FILE, DATA_DIR, fetch_site_result, load_sites


def audit(site, date_str):
    started = time.monotonic()
    hole = "18" if "18" in site.holes else "9"
    url = f"https://{site.domain}"
    if site.provider == "direct":
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GolfHub-Audit/3"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                status = getattr(response, "status", 200)
            return {"course": site.name, "mode": "direct", "ok": 200 <= status < 400, "status": status, "url": url, "seconds": round(time.monotonic() - started, 2)}
        except Exception as exc:
            return {"course": site.name, "mode": "direct", "ok": False, "error": str(exc), "url": url, "seconds": round(time.monotonic() - started, 2)}

    result = fetch_site_result(site, date_str, hole, None, None, None)
    calendar_status = result.get("calendar_availability")
    ok = not bool(result.get("error"))
    if site.name == "Wembley":
        ok = ok and calendar_status in {"available", "full", "unreleased"}
    return {
        "course": site.name,
        "mode": "live",
        "ok": ok,
        "rows": len(result.get("decorated_rows", [])),
        "calendar_availability": calendar_status,
        "error": result.get("error"),
        "url": result.get("url"),
        "seconds": round(time.monotonic() - started, 2),
    }


def main():
    sites = load_sites(DATA_DIR / CONFIG_FILE)
    date_str = (datetime.now(ZoneInfo("Australia/Perth")).date() + timedelta(days=3)).isoformat()
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(audit, site, date_str): site for site in sites}
        for job in as_completed(jobs):
            result = job.result()
            results.append(result)
            print(f"[{ 'PASS' if result['ok'] else 'FAIL' }] {result['course']} ({result['mode']})")
    results.sort(key=lambda item: item["course"])
    report = {
        "tested_at": datetime.now(ZoneInfo("Australia/Perth")).isoformat(timespec="seconds"),
        "booking_date": date_str,
        "total": len(results),
        "passed": sum(1 for result in results if result["ok"]),
        "failed": sum(1 for result in results if not result["ok"]),
        "results": results,
    }
    output = ROOT / "course_audit.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("total", "passed", "failed")}, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
