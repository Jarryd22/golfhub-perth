"""Validated, age-bounded weather reuse and a run-wide forecast request gate."""
from __future__ import annotations

import math
import threading
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError

from app import golfhub_core as core

MAX_FORECAST_AGE_SECONDS = core.WEATHER_MAX_AGE_SECONDS
DEFAULT_COOLDOWN_SECONDS = 3600
DAILY_FIELDS = (
    "weather_code", "temperature_2m_max", "temperature_2m_min",
    "precipitation_probability_max", "precipitation_sum", "wind_speed_10m_max",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing weather timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Weather timestamp must include a timezone")
    return stamp.astimezone(timezone.utc)


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_daily(data: dict) -> None:
    """Do not persist zero defaults fabricated from missing provider values."""
    daily = data.get("daily") if isinstance(data, dict) else None
    days = daily.get("time") if isinstance(daily, dict) else None
    if not isinstance(days, list) or not 1 <= len(days) <= 16 or len(set(days)) != len(days):
        raise ValueError("Invalid forecast dates")
    for day in days:
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("Invalid forecast date")
    for key in DAILY_FIELDS:
        values = daily.get(key)
        if (not isinstance(values, list) or len(values) != len(days)
                or not all(finite_number(value) for value in values)):
            raise ValueError(f"Incomplete forecast field: {key}")
    if any(value not in core.WEATHER_CODE_MAP for value in daily["weather_code"]):
        raise ValueError("Unknown weather code")
    if any(not 0 <= value <= 100 for value in daily["precipitation_probability_max"]):
        raise ValueError("Invalid precipitation probability")
    if any(value < 0 for key in ("precipitation_sum", "wind_speed_10m_max") for value in daily[key]):
        raise ValueError("Invalid precipitation or wind")


def validated_forecasts(payload, queries, now=None, *, reused=None, required_date=None) -> dict:
    now = now or utc_now()
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        return {}
    forecasts = payload.get("forecasts")
    if not isinstance(forecasts, dict):
        return {}
    clean = {}
    for query in queries:
        days = forecasts.get(query)
        if (not isinstance(days, dict) or not 1 <= len(days) <= 16
                or (required_date is not None and required_date not in days)):
            continue
        copied = {}
        source_time = None
        try:
            for day, value in days.items():
                if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                    raise ValueError("Invalid forecast date")
                if not isinstance(value, dict):
                    raise ValueError("Invalid forecast")
                stamp = timestamp(value.get("fetched_at"))
                age = (now - stamp).total_seconds()
                if not 0 <= age < MAX_FORECAST_AGE_SECONDS or (source_time and stamp != source_time):
                    raise ValueError("Expired or inconsistent forecast")
                source_time = stamp
                if any(not isinstance(value.get(key), str) or not value[key]
                       for key in ("icon", "icon_file", "label", "rain_amount_label")):
                    raise ValueError("Missing forecast labels")
                if any(not finite_number(value.get(key))
                       for key in ("tmin", "tmax", "rain_chance", "rain_mm", "wind")):
                    raise ValueError("Invalid forecast values")
                if not 0 <= value["rain_chance"] <= 100 or value["rain_mm"] < 0 or value["wind"] < 0:
                    raise ValueError("Invalid rain or wind")
                copied[day] = dict(value)
                if reused is not None:
                    copied[day]["reused"] = reused
            clean[query] = copied
        except (ValueError, TypeError, OverflowError):
            continue
    return clean


def reusable_forecasts(payload, queries, now=None, *, required_date=None) -> dict:
    return validated_forecasts(payload, queries, now, reused=True, required_date=required_date)


def rate_limit_from(payload, now=None) -> dict | None:
    now = now or utc_now()
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        return None
    value = payload.get("rate_limit")
    if not isinstance(value, dict):
        return None
    try:
        observed = timestamp(value.get("observed_at"))
        until = timestamp(value.get("cooldown_until"))
        if observed > now or until <= now or until <= observed:
            return None
        return {"observed_at": observed.isoformat(), "cooldown_until": until.isoformat(),
                "retry_after": str(value.get("retry_after") or "")[:200]}
    except (ValueError, TypeError, OverflowError):
        return None


def cooldown_after_429(error: HTTPError, now=None) -> dict:
    now = now or utc_now()
    header = str(error.headers.get("Retry-After") or "").strip() if error.headers else ""
    until = now + timedelta(seconds=DEFAULT_COOLDOWN_SECONDS)
    try:
        if header.isascii() and header.isdecimal():
            candidate = now + timedelta(seconds=int(header))
        else:
            candidate = parsedate_to_datetime(header)
            if candidate.tzinfo is None:
                raise ValueError("Retry-After date lacks timezone")
        if candidate > now:
            until = candidate
    except (ValueError, TypeError, OverflowError):
        pass
    return {"observed_at": now.isoformat(), "cooldown_until": until.isoformat(), "retry_after": header[:200]}


class WeatherRequestPolicy(core.WeatherRetryBudget):
    """Gate initial requests and PR #4's retries; never retry an HTTP 429."""

    def __init__(self, rate_limit=None, checkpoint=None):
        super().__init__()
        self._state_lock = threading.Lock()
        self._rate_limit = rate_limit_from({"schema": 1, "rate_limit": rate_limit})
        self._stopped = self._rate_limit is not None
        self.checkpoint = checkpoint

    def snapshot(self):
        with self._state_lock:
            return dict(self._rate_limit) if self._rate_limit else None

    def fetch_json(self, url):
        # Reserving a request here defines in-flight work. At most the existing
        # worker count can already be in flight when another observes a 429.
        with self._state_lock:
            if self._stopped:
                raise RuntimeError("Weather requests paused after provider rate limit")
        try:
            data = core.fetch_json(url)
        except HTTPError as exc:
            if exc.code == 429:
                limit = cooldown_after_429(exc)
                with self._state_lock:
                    self._stopped = True
                    if (not self._rate_limit or timestamp(limit["cooldown_until"])
                            > timestamp(self._rate_limit["cooldown_until"])):
                        self._rate_limit = limit
                # Persist before the core converts the error into an empty
                # forecast, so killing another hung worker retains cooldown.
                if self.checkpoint:
                    self.checkpoint()
            raise
        validate_daily(data)
        return data
