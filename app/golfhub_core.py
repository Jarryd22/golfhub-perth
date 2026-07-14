#!/usr/bin/env python3
from __future__ import annotations

import calendar as pycalendar
import json
import http.cookiejar
import re
import ssl
import sys
import os
import threading
import traceback
import urllib.parse
import urllib.request
import webbrowser
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
import logging

CONFIG_FILE = "courses.json"
GEOCODE_CACHE: dict[str, tuple[float, float]] = {}
WEATHER_CACHE: dict[tuple[str, str], dict] = {}

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
ASSET_DIR = APP_ROOT / "assets"
ICON_DIR = ASSET_DIR / "icons"
RUNTIME_ROOT = Path(os.environ.get("LOCALAPPDATA", APP_ROOT / "runtime")) / "GolfHub"
DEBUG_DIR = RUNTIME_ROOT / "debug"
LOG_DIR = RUNTIME_ROOT / "logs"
CACHE_DIR = RUNTIME_ROOT / "cache"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CRASH_LOG_PATH = LOG_DIR / "golfhub_crash.log"
LATEST_RESULTS_CACHE = CACHE_DIR / "latest_results.json"



def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_DIR / "golfhub.log"),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

def enable_high_dpi() -> None:
    """Make Tkinter look sharper on high-DPI Windows displays."""
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    except Exception:
        pass


WEATHER_CODE_MAP = {
    0: ("☀️", "Clear"),
    1: ("🌤️", "Mostly clear"),
    2: ("⛅", "Partly cloudy"),
    3: ("☁️", "Overcast"),
    45: ("🌫️", "Fog"),
    48: ("🌫️", "Rime fog"),
    51: ("🌦️", "Light drizzle"),
    53: ("🌦️", "Drizzle"),
    55: ("🌧️", "Heavy drizzle"),
    56: ("🌧️", "Freezing drizzle"),
    57: ("🌧️", "Heavy freezing drizzle"),
    61: ("🌦️", "Light rain"),
    63: ("🌧️", "Rain"),
    65: ("🌧️", "Heavy rain"),
    66: ("🌧️", "Freezing rain"),
    67: ("🌧️", "Heavy freezing rain"),
    71: ("🌨️", "Light snow"),
    73: ("🌨️", "Snow"),
    75: ("❄️", "Heavy snow"),
    77: ("❄️", "Snow grains"),
    80: ("🌦️", "Rain showers"),
    81: ("🌧️", "Heavy showers"),
    82: ("⛈️", "Violent showers"),
    85: ("🌨️", "Snow showers"),
    86: ("❄️", "Heavy snow showers"),
    95: ("⛈️", "Thunderstorm"),
    96: ("⛈️", "Storm with hail"),
    99: ("⛈️", "Severe storm"),
}

WEATHER_ICON_FILE_MAP = {
    0: "sheet_clear.png",
    1: "sheet_clear.png",
    2: "sheet_partly_cloudy.png",
    3: "sheet_cloud.png",
    45: "sheet_fog.png",
    48: "sheet_fog.png",
    51: "sheet_partly_rain.png",
    53: "sheet_rain.png",
    55: "sheet_rain.png",
    56: "sheet_sleet.png",
    57: "sheet_sleet.png",
    61: "sheet_rain.png",
    63: "sheet_rain.png",
    65: "sheet_storm.png",
    66: "sheet_sleet.png",
    67: "sheet_sleet.png",
    71: "sheet_snow.png",
    73: "sheet_snow.png",
    75: "sheet_snow.png",
    77: "sheet_snow.png",
    80: "sheet_partly_rain.png",
    81: "sheet_rain.png",
    82: "sheet_storm.png",
    85: "sheet_snow.png",
    86: "sheet_snow.png",
    95: "sheet_storm.png",
    96: "sheet_storm.png",
    99: "sheet_storm.png",
}


def weather_icon_filename_for_code(code: int) -> str:
    return WEATHER_ICON_FILE_MAP.get(code, "sheet_partly_cloudy.png")



@dataclass(frozen=True)
class HoleOption:
    booking_resource_id: str
    fee_group_id: str | None = None
    weekday_fee_group_id: str | None = None
    weekend_fee_group_id: str | None = None
    fee_group_ids: tuple[str, ...] = ()

    def resolve_fee_group_id(self, date_str: str) -> str:
        ids = self.resolve_fee_group_ids(date_str)
        return ids[0] if ids else ""

    def resolve_fee_group_ids(self, date_str: str) -> list[str]:
        # Multiple IDs are used by oddball MiClub setups like The Vines where
        # two different 18-hole walking products can appear on different days.
        if self.fee_group_ids:
            return [x for x in self.fee_group_ids if x]

        if self.weekday_fee_group_id or self.weekend_fee_group_id:
            weekday_index = datetime.strptime(date_str, "%Y-%m-%d").weekday()
            if weekday_index >= 5:
                chosen = self.weekend_fee_group_id or self.weekday_fee_group_id or self.fee_group_id or ""
            else:
                chosen = self.weekday_fee_group_id or self.weekend_fee_group_id or self.fee_group_id or ""
            return [chosen] if chosen else []

        return [self.fee_group_id] if self.fee_group_id else []


@dataclass(frozen=True)
class Site:
    name: str
    domain: str
    holes: dict[str, HoleOption]
    weather_query: str | None = None
    provider: str = "miclub"

    def build_urls(self, date_str: str, hole_type: str) -> list[str]:
        if self.provider.lower() == "quick18":
            compact_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")
            query = urllib.parse.urlencode({"teedate": compact_date})
            return [f"https://{self.domain}/teetimes/searchmatrix?{query}"]

        option = self.holes[hole_type]
        urls = []
        for fee_group_id in option.resolve_fee_group_ids(date_str):
            query_args = {
                "bookingResourceId": option.booking_resource_id,
                "selectedDate": date_str,
                "feeGroupId": fee_group_id,
            }
            query = urllib.parse.urlencode(query_args)
            urls.append(f"https://{self.domain}/guests/bookings/ViewPublicTimesheet.msp?{query}")
        return urls

    def build_url(self, date_str: str, hole_type: str) -> str:
        urls = self.build_urls(date_str, hole_type)
        return urls[0] if urls else ""


def load_sites(config_path: Path) -> list[Site]:
    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    sites: list[Site] = []
    for item in raw.get("sites", []):
        name = str(item.get("name", "")).strip()
        domain = str(item.get("domain", "")).strip()
        holes_raw = item.get("holes", {})
        weather_query = item.get("weather_query")
        provider = str(item.get("provider", "miclub")).strip().lower() or "miclub"

        if not name or not domain or not isinstance(holes_raw, dict):
            continue

        holes: dict[str, HoleOption] = {}
        for hole_key in ("18", "9"):
            hole_data = holes_raw.get(hole_key)
            if not isinstance(hole_data, dict):
                continue

            booking_resource_id = str(hole_data.get("booking_resource_id", "")).strip()
            fee_group_id = str(hole_data.get("fee_group_id", "")).strip() or None
            weekday_fee_group_id = str(hole_data.get("weekday_fee_group_id", "")).strip() or None
            weekend_fee_group_id = str(hole_data.get("weekend_fee_group_id", "")).strip() or None

            raw_fee_group_ids = hole_data.get("fee_group_ids", [])
            fee_group_ids: tuple[str, ...] = ()
            if isinstance(raw_fee_group_ids, list):
                fee_group_ids = tuple(str(x).strip() for x in raw_fee_group_ids if str(x).strip())

            if booking_resource_id and (fee_group_id or weekday_fee_group_id or weekend_fee_group_id or fee_group_ids):
                holes[hole_key] = HoleOption(
                    booking_resource_id=booking_resource_id,
                    fee_group_id=fee_group_id,
                    weekday_fee_group_id=weekday_fee_group_id,
                    weekend_fee_group_id=weekend_fee_group_id,
                    fee_group_ids=fee_group_ids,
                )

        if holes:
            sites.append(
                Site(
                    name=name,
                    domain=domain,
                    holes=holes,
                    weather_query=str(weather_query).strip() if weather_query else None,
                    provider=provider,
                )
            )

    return sorted(sites, key=lambda site: site.name.lower())


def validate_date(date_str: str) -> str:
    datetime.strptime(date_str, "%Y-%m-%d")
    return date_str


def _browser_headers(referer: str | None = None) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def fetch_text(url: str, timeout: int = 25) -> str:
    request = urllib.request.Request(url, headers=_browser_headers())
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def fetch_site_text(site: Site, url: str, timeout: int = 25) -> str:
    """Fetch a course page.

    Wembley needs to behave more like a browser session: land on the public
    calendar first, keep cookies, then open the timesheet. Without that,
    Wembley can return a valid-looking page but with no parsed availability.
    Other MiClub sites continue to use the normal fetch path.
    """
    if "wembleygolf.com.au" not in site.domain.lower():
        return fetch_text(url, timeout=timeout)

    context = ssl.create_default_context()
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPSHandler(context=context),
    )

    base = f"https://{site.domain}"
    calendar_url = f"{base}/guests/bookings/ViewPublicCalendar.msp"

    # Prime cookies/session from the main booking page.
    calendar_request = urllib.request.Request(calendar_url, headers=_browser_headers())
    with opener.open(calendar_request, timeout=timeout) as response:
        response.read()

    # Then fetch the actual timesheet with the calendar as referer.
    page_request = urllib.request.Request(url, headers=_browser_headers(referer=calendar_url))
    with opener.open(page_request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")



def save_debug_html(site: Site, date_str: str, hole_type: str, url: str, html: str) -> None:
    """Save raw fetched HTML for troubleshooting course-specific parsing."""
    try:
        if "wembleygolf.com.au" not in site.domain.lower():
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        fee_match = re.search(r"[?&]feeGroupId=([^&]+)", url)
        fee_group = fee_match.group(1) if fee_match else "unknown"
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", site.name.lower()).strip("_")
        path = DEBUG_DIR / f"{safe_name}_{date_str}_{hole_type}_{fee_group}.html"
        path.write_text(html, encoding="utf-8", errors="replace")
    except Exception:
        pass



def _extract_anchor_hrefs(html: str) -> list[tuple[str, str]]:
    anchors = []
    for match in re.finditer(r"(?is)<a\b([^>]*)>(.*?)</a>", html):
        attrs = match.group(1)
        inner = html_to_text(match.group(2))
        href_match = re.search(r"(?i)\bhref\s*=\s*[\"']([^\"']+)[\"']", attrs)
        if href_match:
            anchors.append((href_match.group(1), inner))
    return anchors


def _normalise_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, unescape(href).replace("&amp;", "&"))


def _url_query_map(url: str) -> dict[str, list[str]]:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.parse_qs(parsed.query, keep_blank_values=True)


def _same_date(url: str, date_str: str) -> bool:
    q = _url_query_map(url)
    return (q.get("selectedDate") or [""])[0] == date_str


def _same_fee_group(url: str, fee_group_ids: set[str]) -> bool:
    q = _url_query_map(url)
    fee = (q.get("feeGroupId") or [""])[0]
    return fee in fee_group_ids


def fetch_wembley_timesheet_urls_from_calendar(site: Site, date_str: str, hole_type: str, timeout: int = 25) -> list[str]:
    """Resolve Wembley timesheet links via its public calendar.

    Wembley is still MiClub, but unlike the other sites, it often relies on the
    public calendar page to generate timesheet links/session parameters. So for
    Wembley we first crawl the calendar pages, find ViewPublicTimesheet links
    for the selected date + configured feeGroupId values, and then scrape those.
    """
    option = site.holes[hole_type]
    fee_group_ids = set(option.resolve_fee_group_ids(date_str))
    if not fee_group_ids:
        return site.build_urls(date_str, hole_type)

    base = f"https://{site.domain}"
    start_url = f"{base}/guests/bookings/ViewPublicCalendar.msp"
    found: list[str] = []
    seen_pages: set[str] = set()
    pages_to_try = [start_url]

    for _ in range(6):
        if not pages_to_try:
            break
        calendar_url = pages_to_try.pop(0)
        if calendar_url in seen_pages:
            continue
        seen_pages.add(calendar_url)

        try:
            calendar_html = fetch_text(calendar_url, timeout=timeout)
            save_debug_html(site, date_str, hole_type, calendar_url, calendar_html)
        except Exception:
            continue

        raw_candidates = []

        for href, label in _extract_anchor_hrefs(calendar_html):
            full = _normalise_url(calendar_url, href)
            if "ViewPublicTimesheet.msp" in full:
                raw_candidates.append(full)
            elif "ViewPublicCalendar.msp" in full and "next" in label.lower():
                pages_to_try.append(full)

        # Some MiClub pages keep URLs in JavaScript snippets rather than plain anchors.
        for match in re.finditer(r"(?is)(?:href|url|location)\s*[:=]\s*[\"']([^\"']*ViewPublicTimesheet\.msp[^\"']+)[\"']", calendar_html):
            raw_candidates.append(_normalise_url(calendar_url, match.group(1)))

        for match in re.finditer(r"(?is)ViewPublicTimesheet\.msp\?[^\"'<>\s]+", calendar_html):
            raw_candidates.append(_normalise_url(calendar_url, match.group(0)))

        for candidate in raw_candidates:
            candidate = candidate.replace("&amp;", "&")
            if _same_date(candidate, date_str) and _same_fee_group(candidate, fee_group_ids):
                if candidate not in found:
                    found.append(candidate)

        if found:
            break

        # Loose Next fallback if label capture is awkward.
        for href, label in _extract_anchor_hrefs(calendar_html):
            full = _normalise_url(calendar_url, href)
            if "ViewPublicCalendar.msp" in full and full not in seen_pages and full not in pages_to_try:
                label_text = label.lower()
                if any(word in label_text for word in ("next", ">")) or "start" in full.lower() or "date" in full.lower():
                    pages_to_try.append(full)

    if found:
        return found

    return site.build_urls(date_str, hole_type)


def fetch_json(url: str, timeout: int = 25) -> dict:
    return json.loads(fetch_text(url, timeout=timeout))


def html_to_text(raw_html: str) -> str:
    text = raw_html.replace("\r", "\n")
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", text)

    block_tags = (
        r"br|p|div|li|ul|ol|table|thead|tbody|tfoot|tr|td|th|section|article|"
        r"header|footer|main|aside|nav|h1|h2|h3|h4|h5|h6|form|fieldset|legend|"
        r"button|a|span"
    )
    text = re.sub(rf"(?is)<(?:{block_tags})\b[^>]*>", "\n", text)
    text = re.sub(rf"(?is)</(?:{block_tags})>", "\n", text)

    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def looks_like_price_or_meta(line: str) -> bool:
    s = line.strip(" -*#")
    if not s:
        return True
    lowered = s.lower()

    if lowered in {
        "taken",
        "available",
        "click to select row.",
        "login",
        "checkout",
        "no login? sign up",
        "all am pm",
        "18 holes",
        "9 holes",
    }:
        return True
    if lowered.startswith("$"):
        return True
    if "your reservation" in lowered:
        return True
    if re.match(r"^\$\d", s):
        return True
    if re.match(r"^\d{1,2}-[a-z]{3}-\d{4}$", lowered):
        return True
    return False


def extract_course_line(block: str) -> str:
    for raw_line in block.splitlines():
        line = raw_line.strip().strip(" -*#")
        if looks_like_price_or_meta(line):
            continue
        if "weekday" in line.lower() and "$" in line:
            continue
        return line
    return ""


def parse_timesheet(html: str) -> list[dict]:
    """Parse MiClub-style public timesheets.

    Some MiClub pages separate rows with "Click to select row", while Wembley
    can render as a plain table where the next tee time is the row boundary.
    This parser handles both by splitting from each tee-time line to the next
    tee-time line.
    """
    text = html_to_text(html)

    # Match tee-time lines such as "11:24 am", "11:24am", or "01:24 pm".
    time_pattern = re.compile(
        r"(?im)^\s*(\d{1,2}:\d{2})\s*([ap]m)\s*$"
    )
    matches = list(time_pattern.finditer(text))

    rows: list[dict] = []

    for idx, match in enumerate(matches):
        time_str = f"{match.group(1)} {match.group(2).lower()}"
        block_start = match.end()
        block_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[block_start:block_end]

        available_count = len(re.findall(r"\bAvailable\b", block, flags=re.IGNORECASE))
        taken_count = len(re.findall(r"\bTaken\b", block, flags=re.IGNORECASE))

        if available_count <= 0:
            continue
        if available_count + taken_count <= 0:
            continue

        rows.append(
            {
                "time": time_str,
                "course_raw": extract_course_line(block),
                "spots": available_count,
            }
        )

    # Backward-compatible fallback for older MiClub pages if a browser renders
    # the row text differently.
    if rows:
        return rows

    pattern = re.compile(
        r"(?ims)(?:^|\n)(\d{1,2}:\d{2}\s*[ap]m)\s*\n(.*?)(?=\nClick to select row\.|\Z)"
    )

    for match in pattern.finditer(text):
        time_str = re.sub(r"\s+", " ", match.group(1).strip()).lower()
        block = match.group(2)

        available_count = len(re.findall(r"\bAvailable\b", block, flags=re.IGNORECASE))
        taken_count = len(re.findall(r"\bTaken\b", block, flags=re.IGNORECASE))

        if available_count <= 0:
            continue
        if available_count + taken_count <= 0:
            continue

        rows.append(
            {
                "time": time_str,
                "course_raw": extract_course_line(block),
                "spots": available_count,
            }
        )
    return rows



def parse_wembley_timesheet(html: str) -> list[dict]:
    """Parse Wembley MiClub timesheet rows.

    Wembley does not use normal <tr> table rows for the visible tee-time list.
    The useful rows are divs like:

        <div id="row-16231013" class="row row-time ...">
            <h3>10:12 am</h3>
            <h4>Old Course 1st Tee</h4>
            <div class="cell cell-taken">Taken</div>
            <div class="cell cell-available">Available</div>
        </div>

    This parser reads those row-time blocks directly.
    """
    rows: list[dict] = []

    # Page-level course label, e.g. "OLD Course 18 Holes" or "TUART Course 18 Holes".
    fee_name = ""
    fee_match = re.search(r'(?is)<h1\b[^>]*class="[^"]*\bfeeName\b[^"]*"[^>]*>(.*?)</h1>', html)
    if fee_match:
        fee_name = html_to_text(fee_match.group(1)).strip()

    # Extract each row-time block by locating row div starts and taking content until the next row/no-rows block.
    row_starts = list(re.finditer(r'(?is)<div\b[^>]*id=["\']row-[^"\']+["\'][^>]*class=["\'][^"\']*\brow-time\b[^"\']*["\'][^>]*>', html))
    for idx, match in enumerate(row_starts):
        block_start = match.start()
        block_end = row_starts[idx + 1].start() if idx + 1 < len(row_starts) else len(html)

        no_rows_match = re.search(r'(?is)<div\b[^>]*id=["\']no-rows["\']', html[block_start:block_end])
        if no_rows_match:
            block_end = block_start + no_rows_match.start()

        block = html[block_start:block_end]
        block_text = html_to_text(block)

        time_match = re.search(r'(?is)<h3[^>]*>\s*(\d{1,2}:\d{2})\s*([ap]m)\s*</h3>', block)
        if not time_match:
            time_match = re.search(r'(?i)\b(\d{1,2}:\d{2})\s*([ap]m)\b', block_text)
        if not time_match:
            continue

        course_label = ""
        course_match = re.search(r'(?is)<h4[^>]*>(.*?)</h4>', block)
        if course_match:
            course_label = html_to_text(course_match.group(1)).strip()

        if not course_label:
            course_label = fee_name or extract_course_line(block_text)

        available_count = len(re.findall(r'\bcell-available\b', block, flags=re.IGNORECASE))
        taken_count = len(re.findall(r'\bcell-taken\b', block, flags=re.IGNORECASE))

        # Fallback to visible text if classes change.
        if available_count + taken_count <= 0:
            available_count = len(re.findall(r'\bAvailable\b', block_text, flags=re.IGNORECASE))
            taken_count = len(re.findall(r'\bTaken\b', block_text, flags=re.IGNORECASE))

        if available_count <= 0:
            continue
        if available_count + taken_count <= 0:
            continue

        rows.append(
            {
                "time": f"{time_match.group(1)} {time_match.group(2).lower()}",
                "course_raw": course_label,
                "spots": available_count,
            }
        )

    if rows:
        return rows

    # Secondary parser for pages that may render with actual table rows.
    tr_blocks = re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", html)
    for block in tr_blocks:
        block_text = html_to_text(block)
        time_match = re.search(r"(?i)\b(\d{1,2}:\d{2})\s*([ap]m)\b", block_text)
        if not time_match:
            continue

        available_count = len(re.findall(r"\bAvailable\b", block_text, flags=re.IGNORECASE))
        taken_count = len(re.findall(r"\bTaken\b", block_text, flags=re.IGNORECASE))
        if available_count <= 0 or available_count + taken_count <= 0:
            continue

        rows.append(
            {
                "time": f"{time_match.group(1)} {time_match.group(2).lower()}",
                "course_raw": fee_name or extract_course_line(block_text),
                "spots": available_count,
            }
        )

    if rows:
        return rows

    # Final fallback: generic MiClub parser.
    return parse_timesheet(html)

def _quick18_is_row_start(lines: list[str], idx: int) -> bool:
    if idx >= len(lines):
        return False
    line = lines[idx].strip()
    if re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)$", line, flags=re.IGNORECASE):
        return True
    if re.match(r"^\d{1,2}:\d{2}$", line) and idx + 1 < len(lines):
        return bool(re.match(r"^(AM|PM)$", lines[idx + 1].strip(), flags=re.IGNORECASE))
    return False


def _quick18_parse_time(lines: list[str], idx: int) -> tuple[str, int]:
    line = lines[idx].strip()
    match = re.match(r"^(\d{1,2}:\d{2})\s*(AM|PM)$", line, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)} {match.group(2).upper()}", idx + 1
    return f"{line} {lines[idx + 1].strip().upper()}", idx + 2


def _quick18_parse_player_spots(line: str) -> int | None:
    s = line.strip()
    patterns = [
        r"^(?:1\s+to\s+)?(?P<max>\d+)\s+players?$",
        r"^1\s+or\s+(?P<max>\d+)\s+players?$",
        r"^(?P<min>\d+)\s+to\s+(?P<max>\d+)\s+players?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, s, flags=re.IGNORECASE)
        if match:
            return int(match.group("max"))
    return None


def _quick18_parse_course_players(line: str) -> tuple[str, int] | None:
    s = line.strip()
    patterns = [
        r"^(?P<course>.+?)\s+(?P<min>\d+)\s+to\s+(?P<max>\d+)\s+players?$",
        r"^(?P<course>.+?)\s+(?P<min>\d+)\s+or\s+(?P<max>\d+)\s+players?$",
        r"^(?P<course>.+?)\s+(?P<max>\d+)\s+players?$",
        r"^(?P<course>.+?)\s+(?P<max>\d+)\s+player$",
    ]
    for pattern in patterns:
        match = re.match(pattern, s, flags=re.IGNORECASE)
        if match:
            course = match.group("course").strip()
            spots = int(match.group("max"))
            return course, spots
    return None


def _quick18_find_table_start(lines: list[str]) -> int:
    for idx in range(len(lines)):
        window = " ".join(lines[idx:idx + 40]).lower()
        if (
            "tee time" in window
            and "players" in window
            and ("9 holes" in window or "18 holes" in window)
        ):
            # Start at the first actual tee-time row after the heading area.
            for j in range(idx + 1, min(idx + 60, len(lines))):
                if _quick18_is_row_start(lines, j):
                    return j
            return idx + 1
    return 0


def _quick18_find_course_players(block: list[str]) -> tuple[str, int, int] | None:
    for local_idx, block_line in enumerate(block):
        # Lake Claremont-style Quick18 pages have no Course column. The row is:
        # time -> players -> 9-hole product columns.
        # Example: "1 player", "1 or 2 players", "1 to 4 players".
        player_only_spots = _quick18_parse_player_spots(block_line)
        if player_only_spots is not None:
            return "", player_only_spots, local_idx

        parsed = _quick18_parse_course_players(block_line)
        if parsed:
            course_raw, spots = parsed
            return course_raw, spots, local_idx

        # Some Quick18 pages split Course and Players into two separate text lines.
        if local_idx + 1 < len(block):
            spots = _quick18_parse_player_spots(block[local_idx + 1])
            if spots is not None:
                course_raw = block_line.strip()
                low = course_raw.lower()
                if course_raw and not course_raw.startswith("$") and low not in {"select", "n/a", "na"}:
                    return course_raw, spots, local_idx + 1

    return None


def _quick18_product_flags(lines: list[str], start_idx: int) -> list[bool]:
    # Product order on Hamersley/Hamersley Quick18:
    # 9 Holes, 9 Holes Concession, Twilight Unlimited Golf, 18 holes, 18 Holes Concession
    flags: list[bool] = []
    idx = start_idx
    while idx < len(lines) and len(flags) < 5:
        line = lines[idx].strip()
        low = line.lower()

        if re.match(r"^\$\d", line):
            flags.append(True)
            idx += 1
            if idx < len(lines) and lines[idx].strip().lower() == "select":
                idx += 1
            continue

        if low in {"n/a", "na"}:
            flags.append(False)
            idx += 1
            if idx < len(lines) and "rate not available" in lines[idx].strip().lower():
                idx += 1
            continue

        if "sold" in low or "not available" in low or "rate not available" in low:
            # Usually follows an N/A line, but keep this as a safety net.
            idx += 1
            continue

        idx += 1

    return flags


def parse_quick18_timesheet(html: str, hole_type: str) -> list[dict]:
    text = html_to_text(html)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    idx = _quick18_find_table_start(lines)

    rows: list[dict] = []

    while idx < len(lines):
        if not _quick18_is_row_start(lines, idx):
            idx += 1
            continue

        time_label, next_idx = _quick18_parse_time(lines, idx)
        row_end = next_idx
        while row_end < len(lines) and not _quick18_is_row_start(lines, row_end):
            row_end += 1

        block = lines[next_idx:row_end]
        parsed = _quick18_find_course_players(block)

        if parsed:
            course_raw, spots, player_line_idx = parsed
            flags = _quick18_product_flags(block, player_line_idx + 1)

            if hole_type == "18":
                available = (len(flags) > 3 and flags[3]) or (len(flags) > 4 and flags[4])
            else:
                # Hamersley has 5 products where the first two are 9-hole products.
                # Lake Claremont has only 9-hole products: 9 Holes, Seniors, Juniors.
                if len(flags) <= 3:
                    available = any(flags)
                else:
                    available = (len(flags) > 0 and flags[0]) or (len(flags) > 1 and flags[1])

            if available:
                dt = datetime.strptime(time_label.upper(), "%I:%M %p")
                rows.append(
                    {
                        "time": dt.strftime("%I:%M %p").lstrip("0").lower(),
                        "course_raw": course_raw,
                        "spots": spots,
                    }
                )

        idx = row_end

    return rows

def time_to_minutes_12h(time_str: str) -> int:
    dt = datetime.strptime(time_str.upper(), "%I:%M %p")
    return dt.hour * 60 + dt.minute


def minutes_to_label(minutes: int) -> str:
    hour = minutes // 60
    minute = minutes % 60
    dt = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M")
    return dt.strftime("%I:%M %p").lstrip("0").lower()


def parse_user_time(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text or text.lower() == "any":
        return None

    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%H%M"):
        try:
            dt = datetime.strptime(text.upper(), fmt)
            return dt.hour * 60 + dt.minute
        except ValueError:
            pass
    return None


def clean_course_label(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""

    low = raw.lower()
    if "1st tee" in low:
        return ""
    if low == "pines":
        return "Pines"
    if low == "lake":
        return "Lake"
    if low == "island":
        return "Island"

    has_pines = "pines" in low
    has_lake = "lake" in low
    has_island = "island" in low

    if has_pines and has_lake and not has_island:
        return "Pines/Lake"
    if has_lake and has_island and not has_pines:
        return "Lake/Island"
    if has_island and has_pines and not has_lake:
        return "Island/Pines"

    raw = re.sub(r"\([^)]*\)", "", raw)
    raw = re.sub(r"\s+or\s+", "/", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*&\s*", "/", raw)
    raw = re.sub(r"\s{2,}", " ", raw).strip(" /")
    return raw


def decorate_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        row = dict(row)
        row["course"] = clean_course_label(row.get("course_raw", ""))
        row["minutes"] = time_to_minutes_12h(row["time"])
        out.append(row)
    return sorted(out, key=lambda r: (r["minutes"], -r["spots"], r["course"]))


def group_rows(rows: list[dict]) -> dict[int, dict[str, list[str]]]:
    grouped_by_spots: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped_by_spots[row["spots"]][row["course"]].append(row["time"])
    return grouped_by_spots


def format_time_list(items: list[str]) -> str:
    return ", ".join(items)


def grouped_rows_for_display(
    rows: list[dict],
    pref_group: int | None,
    pref_from: int | None,
    pref_to: int | None,
) -> dict[int, dict[str, list[str]]]:
    filtered = rows

    if pref_group is not None:
        filtered = [r for r in filtered if r["spots"] == pref_group]

    if pref_from is not None and pref_to is not None:
        lo = min(pref_from, pref_to)
        hi = max(pref_from, pref_to)
        filtered = [r for r in filtered if lo <= r["minutes"] <= hi]
    elif pref_from is not None:
        filtered = [r for r in filtered if r["minutes"] >= pref_from]
    elif pref_to is not None:
        filtered = [r for r in filtered if r["minutes"] <= pref_to]

    grouped_by_spots: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in filtered:
        grouped_by_spots[row["spots"]][row["course"]].append(row["time"])
    return grouped_by_spots


def summarize_preference(
    rows: list[dict],
    pref_from: int | None,
    pref_to: int | None,
    pref_group: int | None,
) -> tuple[str, str]:
    if not rows:
        return ("No available times", "")

    candidates = rows
    if pref_group is not None:
        candidates = [r for r in rows if r["spots"] == pref_group]
        if not candidates:
            return (f"No {pref_group}-spot times available", "")

    if pref_from is None and pref_to is None:
        best = candidates[0]
        if pref_group is not None:
            return (f"Best {pref_group}-spot option: {best['time']}", best["course"])
        return (f"Best overall option: {best['time']}", best["course"])

    if pref_from is not None and pref_to is not None:
        lo = min(pref_from, pref_to)
        hi = max(pref_from, pref_to)
        target = (lo + hi) / 2
        in_window = [r for r in candidates if lo <= r["minutes"] <= hi]
        if in_window:
            best = min(in_window, key=lambda r: (abs(r["minutes"] - target), -r["spots"], r["minutes"]))
            return (f"Best in preferred window: {best['time']}", best["course"])
        best = min(candidates, key=lambda r: (abs(r["minutes"] - target), -r["spots"], r["minutes"]))
        return (f"Closest outside window: {best['time']}", best["course"])

    target = pref_from if pref_from is not None else pref_to
    best = min(candidates, key=lambda r: (abs(r["minutes"] - target), -r["spots"], r["minutes"]))
    return (f"Closest to preference: {best['time']}", best["course"])


def geocode_location(query: str) -> tuple[float, float] | None:
    if query in GEOCODE_CACHE:
        return GEOCODE_CACHE[query]

    if query.lower().startswith("coords:"):
        try:
            lat_text, lon_text = query.split(":", 1)[1].split(",", 1)
            coords = (float(lat_text.strip()), float(lon_text.strip()))
            GEOCODE_CACHE[query] = coords
            return coords
        except Exception:
            return None

    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"format": "jsonv2", "limit": 1, "q": query}
    )
    data = fetch_json(url)
    if not data:
        return None

    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])
    GEOCODE_CACHE[query] = (lat, lon)
    return lat, lon


def rain_amount_label(mm: float) -> str:
    if mm <= 0:
        return "0 mm"
    if mm < 1:
        return "< 1 mm"
    if abs(mm - round(mm)) < 0.05:
        return f"{int(round(mm))} mm"
    return f"{mm:.1f} mm"


def get_weather_for_date(query: str | None, date_str: str, location_name: str | None) -> dict | None:
    if not query:
        return None

    cache_key = (query, date_str)
    if cache_key in WEATHER_CACHE:
        weather = dict(WEATHER_CACHE[cache_key])
        weather["location_name"] = location_name or weather.get("location_name")
        return weather

    coords = geocode_location(query)
    if not coords:
        return None

    lat, lon = coords
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": 16,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    daily = data.get("daily", {})
    times = daily.get("time", [])

    if date_str not in times:
        return None

    idx = times.index(date_str)
    code = int(daily.get("weather_code", [0])[idx])
    icon, label = WEATHER_CODE_MAP.get(code, ("🌤️", "Forecast"))
    icon_file = weather_icon_filename_for_code(code)
    weather = {
        "icon": icon,
        "icon_file": icon_file,
        "label": label,
        "location_name": location_name,
        "tmax": round(float(daily.get("temperature_2m_max", [0])[idx])),
        "tmin": round(float(daily.get("temperature_2m_min", [0])[idx])),
        "rain_chance": round(float(daily.get("precipitation_probability_max", [0])[idx])),
        "rain_mm": round(float(daily.get("precipitation_sum", [0])[idx]), 1),
        "rain_amount_label": rain_amount_label(float(daily.get("precipitation_sum", [0])[idx])),
        "wind": round(float(daily.get("wind_speed_10m_max", [0])[idx])),
    }
    WEATHER_CACHE[cache_key] = dict(weather)
    return weather


def weather_summary_text(weather: dict | None) -> str:
    if not weather:
        return "🌤️ Weather unavailable"
    location = weather.get("location_name") or "Course"
    return (
        f"{weather['icon']} {location}: {weather['label']} • "
        f"{weather['tmax']}°/{weather['tmin']}° • "
        f"{weather['rain_chance']}% rain • {weather['rain_amount_label']} • "
        f"{weather['wind']} km/h wind"
    )


def fetch_site_result(
    site: Site,
    date_str: str,
    hole_type: str,
    pref_from: int | None,
    pref_to: int | None,
    pref_group: int | None,
) -> dict:
    hole_label = "18 holes" if hole_type == "18" else "9 holes"
    weather = get_weather_for_date(site.weather_query, date_str, site.name)

    if hole_type not in site.holes:
        return {
            "site": site,
            "site_name": site.name,
            "url": None,
            "hole_label": hole_label,
            "rows": [],
            "decorated_rows": [],
            "grouped": {},
            "preference_text": "Not configured for this round type",
            "preference_course": "",
            "display_group": None,
            "display_earliest": None,
            "earliest_group_times": [],
            "weather": weather,
            "error": None,
            "not_configured": True,
        }

    urls = site.build_urls(date_str, hole_type)
    url = urls[0] if urls else ""

    try:
        rows = []
        fetch_errors = []
        for one_url in urls:
            try:
                html = fetch_site_text(site, one_url)
                save_debug_html(site, date_str, hole_type, one_url, html)
                if site.provider.lower() == "quick18":
                    page_rows = parse_quick18_timesheet(html, hole_type)
                elif "wembleygolf.com.au" in site.domain.lower():
                    page_rows = parse_wembley_timesheet(html)
                else:
                    page_rows = parse_timesheet(html)
                for row in page_rows:
                    row["source_url"] = one_url
                rows.extend(page_rows)
            except Exception as page_exc:
                fetch_errors.append(str(page_exc))

        if not rows and fetch_errors:
            raise RuntimeError("; ".join(fetch_errors))

        # Dedupe across multiple feeGroup pages while keeping genuine different-course rows.
        unique_rows = []
        seen = set()
        for row in rows:
            key = (row.get("time"), row.get("spots"), row.get("course_raw"), row.get("source_url"))
            if key not in seen:
                seen.add(key)
                unique_rows.append(row)

        rows = unique_rows
        decorated = decorate_rows(rows)
        grouped = group_rows(decorated)
        pref_text, pref_course = summarize_preference(decorated, pref_from, pref_to, pref_group)

        display_group = None
        display_earliest = None
        earliest_group_times = []

        # Build the summary pills from the same filters used for the visible results.
        # This avoids the previous bug where grouped dict values were treated like row dicts.
        summary_rows = decorated

        if pref_group is not None:
            summary_rows = [r for r in summary_rows if r["spots"] == pref_group]

        if pref_from is not None and pref_to is not None:
            lo = min(pref_from, pref_to)
            hi = max(pref_from, pref_to)
            summary_rows = [r for r in summary_rows if lo <= r["minutes"] <= hi]
        elif pref_from is not None:
            summary_rows = [r for r in summary_rows if r["minutes"] >= pref_from]
        elif pref_to is not None:
            summary_rows = [r for r in summary_rows if r["minutes"] <= pref_to]

        best_url = url

        if pref_group is not None:
            if summary_rows:
                display_group = pref_group
                display_earliest = summary_rows[0]["time"]
                earliest_group_times = [(pref_group, summary_rows[0]["time"])]
                best_url = summary_rows[0].get("source_url") or best_url
        else:
            seen_groups = set()
            for row in sorted(summary_rows, key=lambda r: (r["minutes"], -r["spots"], r["course"])):
                spots = row["spots"]
                if spots not in seen_groups:
                    earliest_group_times.append((spots, row["time"]))
                    seen_groups.add(spots)
                    if best_url == url:
                        best_url = row.get("source_url") or best_url

            if earliest_group_times:
                display_group = max(spots for spots, _time in earliest_group_times)
                display_earliest = earliest_group_times[0][1]

        url = best_url

        return {
            "site": site,
            "site_name": site.name,
            "url": url,
            "hole_label": hole_label,
            "rows": rows,
            "decorated_rows": decorated,
            "grouped": grouped,
            "preference_text": pref_text,
            "preference_course": pref_course,
            "display_group": display_group,
            "display_earliest": display_earliest,
            "earliest_group_times": earliest_group_times,
            "weather": weather,
            "error": None,
            "not_configured": False,
        }
    except Exception as exc:
        return {
            "site": site,
            "site_name": site.name,
            "url": url,
            "hole_label": hole_label,
            "rows": [],
            "decorated_rows": [],
            "grouped": {},
            "preference_text": "Could not load live results",
            "preference_course": "",
            "display_group": None,
            "display_earliest": None,
            "earliest_group_times": [],
            "weather": weather,
            "error": str(exc),
            "not_configured": False,
        }
