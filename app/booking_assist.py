"""Safe hand-off plans for completing a tee-time booking on provider sites.

GolfHub deliberately does not submit bookings, solve CAPTCHAs, or call provider
cart/checkout endpoints.  The public MiClub timesheet is especially important:
clicking an ``Available`` player cell immediately calls ``lockCell`` and locks
inventory in the visitor's session.  Consequently MiClub player selection is a
user action, not a side-effect-free operation that GolfHub may perform merely
by opening a URL.

This module is intentionally UI-independent.  A desktop or web UI can build a
``BookingAssistPlan``, open ``open_url``, and show the returned instructions.
Opening ``open_url`` is the only default automatic action.  A MiClub
temporary-hold helper is produced only after explicit, correctly typed user
confirmation and always includes a release-only companion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


MIN_PLAYERS = 1
MAX_PLAYERS = 4


class BookingAssistError(ValueError):
    """Raised when a booking hand-off cannot be constructed safely."""


class AssistMode(str, Enum):
    """The strongest safe hand-off supported by a provider."""

    EXACT_TIMESHEET = "exact_timesheet"
    PROVIDER_SEARCH = "provider_search"
    PROVIDER_HOME = "provider_home"


class PreselectionPolicy(str, Enum):
    """How the requested number of players can be selected."""

    USER_SELECTS = "user_selects"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    mode: AssistMode
    preselection_policy: PreselectionPolicy
    exact_date_supported: bool
    exact_product_supported: bool
    automatic_player_preselection: bool
    confirmed_temporary_hold_supported: bool
    preselection_has_side_effects: bool
    captcha_policy: str
    reason: str


@dataclass(frozen=True)
class BookingAssistPlan:
    """A safe, immutable booking-site hand-off.

    Without explicit temporary-hold confirmation, ``automatic_actions`` is
    limited to opening a public page.  Confirmed MiClub plans may use the page's
    own cell handler to create a reversible hold, but still stop at details.
    """

    provider: str
    capability: ProviderCapability
    course_name: str
    open_url: str
    tee_time: str
    requested_players: int
    available_spots: int | None
    automatic_actions: tuple[str, ...]
    user_instructions: tuple[str, ...]
    stop_before: str
    stripped_query_parameters: tuple[str, ...]
    temporary_hold_confirmed: bool
    temporary_hold_script: str | None
    rollback_script: str | None
    rollback_guidance: tuple[str, ...]

    @property
    def automatic_preselection_allowed(self) -> bool:
        return bool(self.temporary_hold_confirmed and self.temporary_hold_script)


@dataclass(frozen=True)
class MiClubRowTarget:
    """Read-only metadata describing one MiClub timesheet row.

    Cell IDs are useful for diagnostics and for checking that the requested
    number of players is available.  They must not be sent to ``lockCell`` by
    GolfHub because that would reserve inventory in the provider session.
    """

    row_id: str
    tee_time: str
    requested_players: int
    available_cell_ids: tuple[str, ...]
    selected_cell_ids: tuple[str, ...]
    minimum_booking_limit: int
    enough_available_spots: bool
    meets_minimum_booking_limit: bool
    technically_selectable: bool
    automatic_preselection_safe: bool
    side_effect_endpoint: str
    stop_control: str


PROVIDER_CAPABILITIES: dict[str, ProviderCapability] = {
    "miclub": ProviderCapability(
        provider="miclub",
        mode=AssistMode.EXACT_TIMESHEET,
        preselection_policy=PreselectionPolicy.USER_SELECTS,
        exact_date_supported=True,
        exact_product_supported=True,
        automatic_player_preselection=False,
        confirmed_temporary_hold_supported=True,
        preselection_has_side_effects=True,
        captcha_policy="user_only_never_replay_tokens",
        reason=(
            "Selecting a MiClub player cell calls lockCell immediately and "
            "therefore temporarily locks live inventory."
        ),
    ),
    "quick18": ProviderCapability(
        provider="quick18",
        mode=AssistMode.PROVIDER_SEARCH,
        preselection_policy=PreselectionPolicy.USER_SELECTS,
        exact_date_supported=True,
        exact_product_supported=False,
        automatic_player_preselection=False,
        confirmed_temporary_hold_supported=False,
        preselection_has_side_effects=False,
        captcha_policy="user_only",
        reason=(
            "Quick18 configurations do not expose one stable, verified public "
            "player-count deep link across all courses."
        ),
    ),
    "direct": ProviderCapability(
        provider="direct",
        mode=AssistMode.PROVIDER_HOME,
        preselection_policy=PreselectionPolicy.UNSUPPORTED,
        exact_date_supported=False,
        exact_product_supported=False,
        automatic_player_preselection=False,
        confirmed_temporary_hold_supported=False,
        preselection_has_side_effects=False,
        captcha_policy="user_only",
        reason=(
            "Direct providers use different booking systems, so GolfHub opens "
            "the official page without pretending a player count was selected."
        ),
    ),
}


# Parameters that either carry a short-lived challenge/session value or can
# trigger/select state in a booking/cart workflow.  They are never replayed by
# a GolfHub-generated hand-off URL.
_STRIPPED_QUERY_KEYS = {
    "captcha",
    "cells",
    "doaction",
    "g-recaptcha-response",
    "h-captcha-response",
    "lockrow",
    "recaptcharesponse",
    "rowxindex",
    "unlockrow",
}

_UNSAFE_PATH_PARTS = (
    "/guests/ajax",
    "/guests/bookings/checkout.msp",
    "/payment",
)


def _normalise_provider(provider: str | None, url: str) -> str:
    configured = (provider or "").strip().lower()
    if configured in PROVIDER_CAPABILITIES:
        return configured

    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path.lower()
    if "quick18.com" in host or "/teetimes/searchmatrix" in path:
        return "quick18"
    if (
        "miclub" in host
        or path.endswith("viewpublictimesheet.msp")
        or path.endswith("viewpubliccalendar.msp")
    ):
        return "miclub"
    return "direct"


def _normalise_time(value: str) -> str:
    raw = re.sub(r"\s+", " ", str(value or "").strip()).lower()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([ap]m)", raw)
    if not match:
        raise BookingAssistError(f"Unsupported tee-time value: {value!r}")

    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour < 1 or hour > 12 or minute > 59:
        raise BookingAssistError(f"Invalid tee-time value: {value!r}")
    return f"{hour:02d}:{minute:02d} {match.group(3)}"


def _validate_players(players: int, available_spots: int | None) -> tuple[int, int | None]:
    if isinstance(players, bool) or not isinstance(players, int):
        raise BookingAssistError("Players must be a whole number from 1 to 4.")
    if not MIN_PLAYERS <= players <= MAX_PLAYERS:
        raise BookingAssistError("Players must be from 1 to 4.")

    if available_spots is None:
        return players, None
    if isinstance(available_spots, bool) or not isinstance(available_spots, int):
        raise BookingAssistError("Available spots must be a whole number.")
    if available_spots < 0:
        raise BookingAssistError("Available spots cannot be negative.")
    if players > available_spots:
        raise BookingAssistError(
            f"This tee time has {available_spots} available spot(s), not {players}."
        )
    return players, available_spots


def sanitise_booking_url(url: str) -> tuple[str, tuple[str, ...]]:
    """Return a navigation-only URL and the names of discarded parameters."""

    raw = str(url or "").strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise BookingAssistError("Booking URL must be a public HTTP(S) URL.")
    if parts.username or parts.password:
        raise BookingAssistError("Booking URLs containing credentials are not allowed.")

    lowered_path = parts.path.lower().rstrip("/")
    if any(part in lowered_path for part in _UNSAFE_PATH_PARTS):
        raise BookingAssistError("GolfHub will not open an action, checkout, or payment endpoint.")

    safe_query: list[tuple[str, str]] = []
    stripped: list[str] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in _STRIPPED_QUERY_KEYS:
            stripped.append(key)
        else:
            safe_query.append((key, value))

    safe_url = urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc,
            parts.path,
            urlencode(safe_query, doseq=True),
            parts.fragment,
        )
    )
    return safe_url, tuple(dict.fromkeys(stripped))



def _build_miclub_temporary_hold_script(tee_time: str, players: int) -> str:
    """Create a fail-closed script after explicit temporary-hold consent.

    The script uses MiClub's existing cell click handler so its documented
    lock/unlock lifecycle remains intact.  It opens only the player-details
    modal and never invokes a cart, confirmation, checkout, or CAPTCHA action.
    """

    intent = json.dumps({"teeTime": tee_time, "players": players}, separators=(",", ":"))
    return f"""(() => {{
  "use strict";
  const intent = {intent};
  const selectedByGolfHub = [];
  const normalise = value => String(value || "").trim().toLowerCase().replace(/\\s+/g, " ").replace(/^0/, "");
  const releaseSelected = () => {{
    for (const id of selectedByGolfHub.slice().reverse()) {{
      const cell = document.getElementById(id);
      if (cell && cell.classList.contains("cell-selected")) cell.click();
    }}
  }};
  try {{
    if (document.querySelectorAll(".cell-selected").length !== 0) {{
      return {{ok:false, code:"existing_selection", held:0}};
    }}
    const rows = Array.from(document.querySelectorAll("div.row-time")).filter(row => {{
      const heading = row.querySelector("h3");
      return heading && normalise(heading.textContent) === normalise(intent.teeTime);
    }});
    if (rows.length !== 1) return {{ok:false, code:"tee_time_not_unique", held:0}};
    const row = rows[0];
    const available = Array.from(row.querySelectorAll("div.cell.cell-available"));
    if (available.length < intent.players) {{
      return {{ok:false, code:"not_enough_spots", held:0, available:available.length}};
    }}
    const bookButton = document.getElementById("bookNowBtn");
    if (!bookButton || typeof bookButton.click !== "function") {{
      return {{ok:false, code:"details_modal_unavailable", held:0}};
    }}
    for (const cell of available.slice(0, intent.players)) {{
      cell.click();
      if (!cell.classList.contains("cell-selected")) {{
        releaseSelected();
        return {{ok:false, code:"spot_changed", held:0}};
      }}
      selectedByGolfHub.push(cell.id);
    }}
    if (selectedByGolfHub.length !== intent.players) {{
      releaseSelected();
      return {{ok:false, code:"selection_incomplete", held:0}};
    }}
    if (bookButton.disabled) {{
      releaseSelected();
      return {{ok:false, code:"minimum_booking_limit_not_met", held:0}};
    }}
    globalThis.__golfHubTemporaryHold = {{
      rowId: row.getAttribute("data-value") || row.id,
      teeTime: intent.teeTime,
      players: intent.players,
      selectedCellIds: selectedByGolfHub.slice()
    }};
    // Use MiClub's own Book Now control instead of reaching into a named page
    // function. This follows the same official event path as a visitor click
    // and remains compatible if MiClub changes that implementation detail.
    bookButton.click();
    // Bootstrap opens the details modal after its fade transition begins.
    // BookingAssistDialog verifies that visible state after a short owned-Qt
    // timer; checking synchronously here would reject a valid MiClub click.
    return {{ok:true, code:"player_details_open", held:selectedByGolfHub.length}};
  }} catch (error) {{
    releaseSelected();
    delete globalThis.__golfHubTemporaryHold;
    return {{ok:false, code:"assist_error", held:0}};
  }}
}})()"""


def _build_miclub_rollback_script() -> str:
    """Create a release-only companion for a confirmed MiClub hold."""

    return r"""(() => {
  "use strict";
  const state = globalThis.__golfHubTemporaryHold;
  if (!state || !Array.isArray(state.selectedCellIds)) {
    return {ok:true, code:"nothing_to_release", released:0, waitBeforeCloseMs:0};
  }
  try {
    const modal = globalThis.jQuery ? globalThis.jQuery("#detailsModal") : null;
    if (modal && typeof modal.modal === "function") modal.modal("hide");
    let released = 0;
    for (const id of state.selectedCellIds.slice().reverse()) {
      const cell = document.getElementById(id);
      if (cell && cell.classList.contains("cell-selected")) {
        cell.click();
        released += 1;
      }
    }
    const remaining = state.selectedCellIds.filter(id => {
      const cell = document.getElementById(id);
      return cell && cell.classList.contains("cell-selected");
    });
    if (remaining.length === 0) delete globalThis.__golfHubTemporaryHold;
    return {
      ok:remaining.length === 0,
      code:remaining.length === 0 ? "release_requested" : "release_incomplete",
      released:released,
      remaining:remaining.length,
      waitBeforeCloseMs:1500
    };
  } catch (error) {
    return {ok:false, code:"release_error", released:0, waitBeforeCloseMs:1500};
  }
})()"""

def build_booking_assist_plan(
    *,
    source_url: str,
    tee_time: str,
    players: int,
    available_spots: int | None = None,
    provider: str | None = None,
    course_name: str = "",
    temporary_hold_confirmed: bool = False,
) -> BookingAssistPlan:
    """Build a provider-aware, navigation-only booking hand-off."""

    safe_url, stripped = sanitise_booking_url(source_url)
    player_count, spot_count = _validate_players(players, available_spots)
    normal_time = _normalise_time(tee_time)
    provider_key = _normalise_provider(provider, safe_url)
    capability = PROVIDER_CAPABILITIES[provider_key]
    if not isinstance(temporary_hold_confirmed, bool):
        raise BookingAssistError("Temporary-hold confirmation must be a boolean.")

    hold_script = None
    rollback_script = None
    rollback_guidance: tuple[str, ...] = ()
    automatic_actions = ("open_public_booking_page",)
    if temporary_hold_confirmed:
        if not capability.confirmed_temporary_hold_supported:
            raise BookingAssistError(
                f"Confirmed player preselection is not supported for {provider_key}."
            )
        safe_parts = urlsplit(safe_url)
        if not safe_parts.path.lower().endswith("viewpublictimesheet.msp"):
            raise BookingAssistError(
                "MiClub temporary-hold assist requires an exact public timesheet page."
            )
        safe_params = {key.lower(): value for key, value in parse_qsl(safe_parts.query)}
        required_params = {"bookingresourceid", "selecteddate", "feegroupid"}
        if not required_params.issubset(safe_params):
            raise BookingAssistError(
                "MiClub temporary-hold assist requires resource, date, and product identifiers."
            )
        hold_script = _build_miclub_temporary_hold_script(normal_time, player_count)
        rollback_script = _build_miclub_rollback_script()
        rollback_guidance = (
            "Use Release holds before closing the provider page if you do not continue.",
            "Wait at least 1.5 seconds after release so MiClub can process its asynchronous unlock request.",
            "Never use the release action after you have continued the booking yourself.",
        )
        automatic_actions = (
            "open_public_booking_page",
            "run_user_confirmed_temporary_hold_script",
            "open_player_details_only",
        )

    if provider_key == "miclub" and temporary_hold_confirmed:
        instructions = (
            f"GolfHub will target {normal_time} and exactly {player_count} available player spot(s).",
            "Each selected spot becomes a temporary MiClub hold; no booking is submitted.",
            "GolfHub opens only the player-details window and stops before Confirm Booking.",
            "Use Release holds before closing if you do not continue, and handle any CAPTCHA yourself.",
        )
    elif provider_key == "miclub":
        instructions = (
            f"On the exact timesheet, find {normal_time}.",
            f"Select {player_count} available player spot(s). MiClub may temporarily lock each selected spot.",
            "Review the player-details window and continue yourself only when ready.",
            "GolfHub stops before Confirm Booking and never handles a CAPTCHA.",
        )
    elif provider_key == "quick18":
        instructions = (
            f"On the provider search page, find {normal_time}.",
            f"Choose {player_count} player(s) using the provider's controls.",
            "GolfHub stops before any reservation, checkout, login, payment, or CAPTCHA.",
        )
    else:
        instructions = (
            f"Use the official course page to find {normal_time} for {player_count} player(s).",
            "This provider does not have a verified GolfHub player-count hand-off.",
            "GolfHub stops before any reservation, checkout, login, payment, or CAPTCHA.",
        )

    return BookingAssistPlan(
        provider=provider_key,
        capability=capability,
        course_name=str(course_name or "").strip(),
        open_url=safe_url,
        tee_time=normal_time,
        requested_players=player_count,
        available_spots=spot_count,
        automatic_actions=automatic_actions,
        user_instructions=instructions,
        stop_before="Confirm Booking",
        stripped_query_parameters=stripped,
        temporary_hold_confirmed=bool(temporary_hold_confirmed),
        temporary_hold_script=hold_script,
        rollback_script=rollback_script,
        rollback_guidance=rollback_guidance,
    )


class _MiClubTimesheetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._row: dict | None = None
        self._div_depth = 0
        self._in_h3 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: (value or "") for key, value in attrs}
        classes = set(attr.get("class", "").split())

        if tag == "div" and self._row is None and "row-time" in classes:
            self._row = {
                "row_id": attr.get("data-value") or attr.get("id", "").removeprefix("row-"),
                "time_parts": [],
                "available": [],
                "selected": [],
            }
            self._div_depth = 1
            return

        if self._row is None:
            return

        if tag == "div":
            self._div_depth += 1
            cell_id = attr.get("id", "")
            if "cell" in classes and cell_id:
                if "cell-available" in classes:
                    self._row["available"].append(cell_id)
                elif "cell-selected" in classes:
                    self._row["selected"].append(cell_id)
        elif tag == "h3":
            self._in_h3 = True

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if tag == "h3":
            self._in_h3 = False
        if tag == "div":
            self._div_depth -= 1
            if self._div_depth == 0:
                self.rows.append(self._row)
                self._row = None

    def handle_data(self, data: str) -> None:
        if self._row is not None and self._in_h3:
            self._row["time_parts"].append(data)


def _minimum_booking_limits(html: str) -> dict[str, int]:
    match = re.search(
        r"minimumBookingLimitJson\s*=\s*JSON\.parse\(\s*'([^']*)'\s*\)",
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}

    limits: dict[str, int] = {}
    for key, value in parsed.items():
        try:
            limits[str(key)] = max(1, int(value))
        except (TypeError, ValueError):
            continue
    return limits


def inspect_miclub_row(
    html: str,
    *,
    tee_time: str,
    players: int,
) -> MiClubRowTarget | None:
    """Inspect a MiClub row without selecting, locking, or submitting it."""

    player_count, _ = _validate_players(players, None)
    wanted_time = _normalise_time(tee_time)
    parser = _MiClubTimesheetParser()
    parser.feed(str(html or ""))
    limits = _minimum_booking_limits(str(html or ""))

    for row in parser.rows:
        try:
            row_time = _normalise_time(" ".join(row["time_parts"]))
        except BookingAssistError:
            continue
        if row_time != wanted_time:
            continue

        row_id = str(row["row_id"])
        available = tuple(str(cell_id) for cell_id in row["available"])
        selected = tuple(str(cell_id) for cell_id in row["selected"])
        minimum = limits.get(row_id, 1)
        enough = len(available) >= player_count
        meets_minimum = player_count >= minimum
        return MiClubRowTarget(
            row_id=row_id,
            tee_time=row_time,
            requested_players=player_count,
            available_cell_ids=available,
            selected_cell_ids=selected,
            minimum_booking_limit=minimum,
            enough_available_spots=enough,
            meets_minimum_booking_limit=meets_minimum,
            technically_selectable=enough and meets_minimum,
            automatic_preselection_safe=False,
            side_effect_endpoint="/guests/Ajax?doAction=lockCell&rowXIndex=<cell-id>",
            stop_control="Confirm Booking",
        )
    return None


__all__ = [
    "AssistMode",
    "BookingAssistError",
    "BookingAssistPlan",
    "MAX_PLAYERS",
    "MIN_PLAYERS",
    "MiClubRowTarget",
    "PreselectionPolicy",
    "PROVIDER_CAPABILITIES",
    "ProviderCapability",
    "build_booking_assist_plan",
    "inspect_miclub_row",
    "sanitise_booking_url",
]

