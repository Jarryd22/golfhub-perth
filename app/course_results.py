"""Result helpers shared by the desktop UI and GitHub cache builder."""
from __future__ import annotations

from typing import Any

from app.golfhub_core import get_weather_for_date


def direct_result(site, hole_type: str, date_str: str | None = None) -> dict[str, Any]:
    weather = None
    if date_str:
        try:
            weather = get_weather_for_date(site.weather_query, date_str, site.name)
        except Exception:
            weather = None
    return {
        "site_name": site.name,
        "url": f"https://{site.domain}",
        "hole_label": f"{hole_type} holes",
        "rows": [],
        "decorated_rows": [],
        "weather": weather,
        "error": None,
        "not_configured": False,
        "direct_booking": True,
        "booking_note": "Open the official course page for booking options or visitor instructions.",
    }
