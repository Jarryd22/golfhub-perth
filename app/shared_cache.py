"""Shared and local cache support for the Golf Hub desktop app.

The GitHub cache is deliberately read-only from the app. A scheduled workflow
refreshes public JSON snapshots; the desktop app downloads the snapshot for the
selected date/round and keeps a local copy for offline startup.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.golfhub_core import APP_ROOT


CACHE_SCHEMA = 1
CONFIG_PATH = APP_ROOT / "data" / "cache_config.json"
LOCAL_CACHE_DIR = Path(os.environ.get("LOCALAPPDATA", APP_ROOT / "data")) / "GolfHub" / "cache"


def _cache_base_url() -> str | None:
    env_url = os.environ.get("GOLFHUB_CACHE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        url = str(config.get("cache_base_url") or "").strip().rstrip("/")
        if url and "YOUR_GITHUB_USERNAME" not in url:
            return url
    except (OSError, ValueError, TypeError):
        pass
    return None


def snapshot_name(date_str: str, hole_type: str) -> str:
    return f"{date_str}/{hole_type}.json"


def local_snapshot_path(date_str: str, hole_type: str) -> Path:
    return LOCAL_CACHE_DIR / snapshot_name(date_str, hole_type)


def serialise_result(result: dict[str, Any]) -> dict[str, Any]:
    """Remove runtime-only values (notably the Site dataclass)."""
    clean = {key: value for key, value in result.items() if key != "site"}
    return json.loads(json.dumps(clean, ensure_ascii=False, default=str))


def make_snapshot(date_str: str, hole_type: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": CACHE_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "date": date_str,
        "holes": hole_type,
        "results": [serialise_result(result) for result in results],
    }


def validate_snapshot(payload: Any, date_str: str, hole_type: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Cache response is not an object")
    if payload.get("schema") != CACHE_SCHEMA:
        raise ValueError("Unsupported cache schema")
    if payload.get("date") != date_str or str(payload.get("holes")) != str(hole_type):
        raise ValueError("Cache response does not match the requested search")
    if not isinstance(payload.get("results"), list):
        raise ValueError("Cache response has no results list")
    return payload


def save_local_snapshot(payload: dict[str, Any]) -> Path:
    path = local_snapshot_path(str(payload["date"]), str(payload["holes"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)
    return path


def load_local_snapshot(date_str: str, hole_type: str) -> dict[str, Any] | None:
    path = local_snapshot_path(date_str, hole_type)
    try:
        return validate_snapshot(json.loads(path.read_text(encoding="utf-8")), date_str, hole_type)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def fetch_shared_snapshot(date_str: str, hole_type: str, timeout: int = 5) -> dict[str, Any] | None:
    base_url = _cache_base_url()
    if not base_url:
        return None
    url = f"{base_url}/{snapshot_name(date_str, hole_type)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GolfHub-Desktop/3", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        payload = validate_snapshot(payload, date_str, hole_type)
        save_local_snapshot(payload)
        return payload
    except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
        return None


def cache_age_label(generated_at: str | None) -> str:
    if not generated_at:
        return "saved earlier"
    try:
        stamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age = max(0, int((datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()))
    except (ValueError, TypeError):
        return "saved earlier"
    if age < 60:
        return "less than a minute ago"
    if age < 3600:
        minutes = age // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = age // 3600
    return f"{hours} hour{'s' if hours != 1 else ''} ago"
