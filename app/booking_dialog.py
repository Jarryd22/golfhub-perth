"""Embedded, safety-bounded hand-off to an official booking page.

The dialog owns an off-the-record Qt WebEngine profile so provider cookies and
temporary booking state are discarded with the dialog.  It can run the
reversible MiClub helper from :mod:`app.booking_assist`, but only when the plan
records explicit temporary-hold consent.  It never submits player details,
confirms a booking, enters checkout, or handles payment/CAPTCHA controls.

The small result interpreters are intentionally independent from Qt.  Besides
making the behavior easy to unit test, they ensure an unexpected JavaScript
result fails closed instead of being treated as a successful hold or release.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

from PySide6.QtCore import QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.booking_assist import (
    BookingAssistError,
    BookingAssistPlan,
    sanitise_booking_url,
)


DEFAULT_RELEASE_WAIT_MS = 1_500
MAX_RELEASE_WAIT_MS = 10_000
DETAILS_VERIFY_DELAY_MS = 700


@dataclass(frozen=True)
class ScriptOutcome:
    """Normalised result from one of the tightly scoped page helpers."""

    ok: bool
    code: str
    count: int
    wait_before_close_ms: int = 0
    available: int | None = None
    remaining: int | None = None


_HOLD_FAILURE_CODES = {
    "existing_selection",
    "tee_time_not_unique",
    "not_enough_spots",
    "details_modal_unavailable",
    "spot_changed",
    "selection_incomplete",
    "minimum_booking_limit_not_met",
    "assist_error",
}

_RELEASE_CODES = {
    "nothing_to_release",
    "release_requested",
    "release_incomplete",
    "release_error",
}


def _whole_number(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if not math.isfinite(float(value)) or float(value) != int(value):
        return default
    return max(0, int(value))


def _script_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    return value if isinstance(value, Mapping) else None


def _json_result_script(script: str) -> str:
    """Make Qt WebEngine return portable JSON instead of an opaque JS object."""

    return f"JSON.stringify({script})"


def interpret_hold_result(value: Any, expected_players: int) -> ScriptOutcome:
    """Validate a hold-script result, accepting only the exact success shape."""

    value = _script_mapping(value)
    if value is None:
        return ScriptOutcome(False, "invalid_hold_result", 0)

    raw_code = value.get("code")
    code = raw_code if isinstance(raw_code, str) else ""
    held = _whole_number(value.get("held"), 0)
    available = (
        _whole_number(value.get("available"), 0)
        if "available" in value
        else None
    )
    expected = _whole_number(expected_players, 0)

    if (
        value.get("ok") is True
        and code == "player_details_open"
        and expected > 0
        and held == expected
    ):
        return ScriptOutcome(True, code, held, available=available)

    # Known failures are useful to the user only when the script also reports
    # that it retained no spots.  Anything else is conservatively unknown.
    if value.get("ok") is False and code in _HOLD_FAILURE_CODES and held == 0:
        return ScriptOutcome(False, code, 0, available=available)
    return ScriptOutcome(False, "invalid_hold_result", 0, available=available)


def interpret_release_result(value: Any) -> ScriptOutcome:
    """Validate a rollback result and provide a bounded post-release wait."""

    value = _script_mapping(value)
    if value is None:
        return ScriptOutcome(
            False,
            "invalid_release_result",
            0,
            DEFAULT_RELEASE_WAIT_MS,
        )

    raw_wait = value.get("waitBeforeCloseMs", DEFAULT_RELEASE_WAIT_MS)
    wait_ms = _whole_number(raw_wait, DEFAULT_RELEASE_WAIT_MS)
    wait_ms = min(wait_ms, MAX_RELEASE_WAIT_MS)
    released = _whole_number(value.get("released"), 0)
    remaining = (
        _whole_number(value.get("remaining"), 0)
        if "remaining" in value
        else None
    )
    raw_code = value.get("code")
    code = raw_code if isinstance(raw_code, str) else ""

    valid_success = (
        value.get("ok") is True
        and code in {"nothing_to_release", "release_requested"}
        and (remaining in {None, 0})
    )
    if valid_success:
        return ScriptOutcome(True, code, released, wait_ms, remaining=remaining)
    if value.get("ok") is False and code in _RELEASE_CODES:
        return ScriptOutcome(False, code, released, wait_ms, remaining=remaining)
    return ScriptOutcome(
        False,
        "invalid_release_result",
        released,
        wait_ms,
        remaining=remaining,
    )


def is_checkout_url(value: str | QUrl) -> bool:
    """Return whether navigation has reached a provider checkout path."""

    raw = value.toString() if isinstance(value, QUrl) else str(value or "")
    path = urlsplit(raw).path.lower().rstrip("/")
    return path.endswith("/checkout.msp") or "/checkout/" in f"{path}/"


def plan_allows_temporary_hold(plan: BookingAssistPlan) -> bool:
    """Require every independent consent/capability guard before page script use."""

    return bool(
        plan.provider == "miclub"
        and plan.temporary_hold_confirmed is True
        and plan.automatic_preselection_allowed
        and plan.capability.confirmed_temporary_hold_supported
        and plan.temporary_hold_script
        and plan.rollback_script
    )


def _same_expected_timesheet(current_url: str, planned_url: str) -> bool:
    """Prevent a hold script from running after a redirect to another page."""

    current = urlsplit(current_url)
    planned = urlsplit(planned_url)
    return bool(
        current.scheme.lower() in {"http", "https"}
        and current.hostname
        and current.hostname.lower() == (planned.hostname or "").lower()
        and current.path.lower().rstrip("/")
        == planned.path.lower().rstrip("/")
        and current.path.lower().rstrip("/").endswith("viewpublictimesheet.msp")
    )


def _hold_message(outcome: ScriptOutcome, players: int) -> str:
    if outcome.ok:
        noun = "spot" if players == 1 else "spots"
        return (
            f"{players} {noun} temporarily held. Review the official player-details "
            "window. GolfHub stops before Confirm Booking."
        )
    messages = {
        "existing_selection": "A player selection already exists, so GolfHub made no changes.",
        "tee_time_not_unique": "The exact tee-time row could not be identified safely.",
        "not_enough_spots": "The requested number of spots is no longer available.",
        "details_modal_unavailable": "The official player-details window is not available.",
        "spot_changed": "Availability changed while the spots were being checked.",
        "selection_incomplete": "The full player count could not be selected safely.",
        "minimum_booking_limit_not_met": "This tee time has a different minimum booking size.",
        "assist_error": "The official page changed while GolfHub was preparing the hand-off.",
        "invalid_hold_result": "The official page returned an unexpected result.",
    }
    return messages.get(outcome.code, "GolfHub could not prepare this booking safely.")


class BookingAssistDialog(QDialog):
    """Show an official booking page and manage a confirmed reversible hold.

    Public integration surface:

    ``BookingAssistDialog(plan, parent=None, auto_load=True)``
        ``plan`` must be a :class:`BookingAssistPlan`.  Passing ``auto_load=False``
        is intended for isolated tests that call ``web_view.setHtml``.
    ``start()``
        Load ``plan.open_url`` exactly once.
    ``request_close()`` / ``release_holds_and_close()``
        Release any GolfHub-created temporary hold, wait for the provider's
        requested delay (1.5 seconds by default), then close.

    Read-only state is exposed through ``hold_active``,
    ``continued_to_checkout``, ``release_in_progress``, ``status_code``, and
    ``status_message``.  The ``web_view``, ``web_page``, and ``web_profile``
    attributes are available for normal Qt ownership/integration and local
    fixture tests.
    """

    status_changed = Signal(str, str)
    assist_finished = Signal(bool, str, int)
    release_finished = Signal(bool, str, int)
    checkout_reached = Signal(str)

    def __init__(
        self,
        plan: BookingAssistPlan,
        parent: QWidget | None = None,
        *,
        auto_load: bool = True,
    ) -> None:
        if not isinstance(plan, BookingAssistPlan):
            raise TypeError("plan must be a BookingAssistPlan")

        safe_url, stripped = sanitise_booking_url(plan.open_url)
        if stripped or safe_url != plan.open_url:
            raise BookingAssistError("Booking plan contains an unsafe navigation URL.")

        super().__init__(parent)
        self.plan = plan
        self._started = False
        self._hold_script_started = False
        self._hold_active = False
        self._release_required = False
        self._release_in_progress = False
        self._close_after_release = False
        self._automatic_cleanup = False
        self._allow_close = False
        self._continued_to_checkout = False
        self._status_code = "ready"
        self._status_message = "Ready to open the official booking page."
        self._details_verify_timer = QTimer(self)
        self._details_verify_timer.setSingleShot(True)
        self._details_verify_timer.timeout.connect(self._verify_player_details)

        self.setWindowTitle(
            f"Complete booking â€” {plan.course_name or 'official course'}"
        )
        self.resize(1180, 760)
        self.setMinimumSize(860, 600)
        self.setModal(False)

        self.web_profile = QWebEngineProfile(self)
        if not self.web_profile.isOffTheRecord():
            raise RuntimeError("BookingAssistDialog requires an off-the-record profile.")
        self.web_view = QWebEngineView(self)
        self.web_page = QWebEnginePage(self.web_profile, self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_view.urlChanged.connect(self._handle_url_changed)
        self.web_view.loadFinished.connect(self._handle_load_finished)

        self._build_ui()
        self._apply_style()
        self._update_buttons()
        if auto_load:
            QTimer.singleShot(0, self.start)

    @property
    def hold_active(self) -> bool:
        return self._hold_active

    @property
    def continued_to_checkout(self) -> bool:
        return self._continued_to_checkout

    @property
    def release_in_progress(self) -> bool:
        return self._release_in_progress

    @property
    def status_code(self) -> str:
        return self._status_code

    @property
    def status_message(self) -> str:
        return self._status_message

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        heading = QLabel(
            f"{self.plan.course_name or 'Official course'} Â· {self.plan.tee_time} Â· "
            f"{self.plan.requested_players} player(s)"
        )
        heading.setObjectName("bookingHeading")
        layout.addWidget(heading)

        notice = QLabel(
            "You are on the course's official booking page. GolfHub can prepare "
            "the selected spots only after your confirmation; it never presses "
            "Confirm Booking or enters checkout/payment for you."
        )
        notice.setObjectName("bookingNotice")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        self.status_label = QLabel(self._status_message)
        self.status_label.setObjectName("bookingStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        layout.addWidget(self.progress)

        layout.addWidget(self.web_view, 1)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.safety_label = QLabel("Nothing is booked until you confirm on the official page.")
        self.safety_label.setObjectName("bookingSafety")
        self.safety_label.setWordWrap(True)
        controls.addWidget(self.safety_label, 1)

        self.release_button = QPushButton("RELEASE HOLDS & CLOSE")
        self.release_button.setObjectName("releaseButton")
        self.release_button.clicked.connect(self.release_holds_and_close)
        controls.addWidget(self.release_button)

        self.close_button = QPushButton("CLOSE")
        self.close_button.clicked.connect(self.request_close)
        controls.addWidget(self.close_button)
        layout.addLayout(controls)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #090909; color: #F6F6F6; }
            QLabel#bookingHeading { font-size: 20px; font-weight: 800; }
            QLabel#bookingNotice { color: #C8C8C8; }
            QLabel#bookingStatus {
                background: #171717; border: 1px solid #3B3B3B;
                border-left: 4px solid #F59E0B; border-radius: 7px;
                padding: 10px 12px; color: #F6F6F6;
            }
            QLabel#bookingSafety { color: #B8B8B8; }
            QProgressBar { border: 0; background: #242424; }
            QProgressBar::chunk { background: #F59E0B; }
            QWebEngineView { background: white; border: 1px solid #303030; }
            QPushButton {
                min-height: 40px; padding: 0 18px; border-radius: 8px;
                border: 1px solid #454545; background: #171717;
                color: #F6F6F6; font-weight: 800;
            }
            QPushButton:hover { border-color: #F59E0B; }
            QPushButton#releaseButton {
                background: #F59E0B; color: #090909; border-color: #F59E0B;
            }
            QPushButton:disabled { color: #777; background: #202020; border-color: #303030; }
            """
        )

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)

    def _set_status(self, code: str, message: str) -> None:
        self._status_code = code
        self._status_message = message
        self.status_label.setText(message)
        self.status_changed.emit(code, message)

    def _update_buttons(self) -> None:
        needs_release = self._hold_active or self._release_required
        self.release_button.setVisible(needs_release and not self._continued_to_checkout)
        self.release_button.setEnabled(not self._release_in_progress)
        self.close_button.setVisible(not needs_release or self._continued_to_checkout)
        self.close_button.setEnabled(not self._release_in_progress)

    @Slot()
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._set_busy(True)
        self._set_status("loading", "Opening the official booking pageâ€¦")
        self.web_view.load(QUrl(self.plan.open_url))

    @Slot(bool)
    def _handle_load_finished(self, ok: bool) -> None:
        if self._continued_to_checkout:
            self._set_busy(False)
            return
        if not ok:
            self._set_busy(False)
            self._set_status(
                "load_failed",
                "The official booking page did not load. No spots were selected.",
            )
            return

        if not plan_allows_temporary_hold(self.plan):
            self._set_busy(False)
            self._set_status(
                "manual_only",
                "The official page is ready. Choose players and continue manually.",
            )
            return

        if self._hold_script_started:
            return
        current_url = self.web_view.url().toString()
        if not _same_expected_timesheet(current_url, self.plan.open_url):
            self._set_busy(False)
            self._set_status(
                "unexpected_page",
                "The provider redirected to a different page, so GolfHub did not select any spots.",
            )
            return

        self._hold_script_started = True
        # Once the script begins, rollback is required until its result is
        # known and any provider-side asynchronous locks have been released.
        self._release_required = True
        self._update_buttons()
        self._set_busy(True)
        self._set_status(
            "preparing_hold",
            f"Preparing {self.plan.requested_players} temporary player spot(s)â€¦",
        )
        self.web_page.runJavaScript(
            _json_result_script(self.plan.temporary_hold_script or ""),
            self._handle_hold_result,
        )

    def _handle_hold_result(self, value: Any) -> None:
        if self._continued_to_checkout:
            # The user has taken control and continued the provider workflow.
            # Never issue rollback calls after this navigation is observed.
            self._hold_active = False
            self._release_required = False
            self._set_busy(False)
            self._update_buttons()
            return

        outcome = interpret_hold_result(value, self.plan.requested_players)
        self._hold_active = outcome.ok
        self._release_required = True
        self._update_buttons()

        if outcome.ok:
            self._set_status(
                "opening_player_details",
                "Selected the requested spots. Opening the official player-details windowâ€¦",
            )
            self._details_verify_timer.start(DETAILS_VERIFY_DELAY_MS)
            return

        self._set_busy(False)
        self._set_status(outcome.code, _hold_message(outcome, self.plan.requested_players))
        self.assist_finished.emit(False, outcome.code, outcome.count)

        # Even an unexpected/failed result may have clicked a cell before the
        # page changed. Roll back immediately and keep the page open.
        self._automatic_cleanup = True
        self._begin_release(close_after=False)

    @Slot()
    def _verify_player_details(self) -> None:
        if self._continued_to_checkout or self._release_in_progress:
            return
        expected = int(self.plan.requested_players)
        script = f"""JSON.stringify((() => {{
          const modal = document.getElementById("detailsModal");
          const selected = document.querySelectorAll(".cell-selected").length;
          const opened = Boolean(modal && (
            modal.classList.contains("in") ||
            modal.classList.contains("show") ||
            globalThis.getComputedStyle(modal).display !== "none"
          ));
          return {{
            ok: opened && selected === {expected},
            code: opened ? (selected === {expected} ? "player_details_open" : "selection_incomplete") : "details_modal_unavailable",
            held: selected
          }};
        }})())"""
        self.web_page.runJavaScript(script, self._handle_details_verification)

    def _handle_details_verification(self, value: Any) -> None:
        if self._continued_to_checkout or self._release_in_progress:
            return
        result = _script_mapping(value)
        expected = int(self.plan.requested_players)
        held = _whole_number(result.get("held"), 0) if result else 0
        code = result.get("code") if result and isinstance(result.get("code"), str) else "invalid_hold_result"
        verified = bool(
            result
            and result.get("ok") is True
            and code == "player_details_open"
            and held == expected
        )
        self._set_busy(False)
        self._hold_active = held > 0
        self._release_required = True
        if verified:
            outcome = ScriptOutcome(True, "player_details_open", held)
            self._set_status(outcome.code, _hold_message(outcome, expected))
            self.assist_finished.emit(True, outcome.code, outcome.count)
            self._update_buttons()
            return

        safe_code = code if code in _HOLD_FAILURE_CODES else "invalid_hold_result"
        outcome = ScriptOutcome(False, safe_code, 0)
        self._set_status(safe_code, _hold_message(outcome, expected))
        self.assist_finished.emit(False, safe_code, held)
        self._update_buttons()
        self._automatic_cleanup = True
        self._begin_release(close_after=False)

    @Slot(QUrl)
    def _handle_url_changed(self, url: QUrl) -> None:
        if not is_checkout_url(url):
            return
        self._details_verify_timer.stop()
        self._continued_to_checkout = True
        self._hold_active = False
        self._release_required = False
        self._set_busy(False)
        self._set_status(
            "checkout_reached",
            "You continued on the official site. GolfHub will not change or release this booking state.",
        )
        self._update_buttons()
        self.checkout_reached.emit(url.toString())

    def _begin_release(self, *, close_after: bool) -> None:
        self._details_verify_timer.stop()
        if self._continued_to_checkout:
            if close_after:
                self._finish_close()
            return
        if self._release_in_progress:
            self._close_after_release = self._close_after_release or close_after
            return
        if not self.plan.rollback_script:
            self._set_status(
                "release_unavailable",
                "GolfHub could not verify a release action. Keep this page open and deselect any spots manually.",
            )
            return

        self._release_in_progress = True
        self._close_after_release = close_after
        self._set_busy(True)
        self._set_status("releasing", "Releasing GolfHub's temporary player holdsâ€¦")
        self._update_buttons()
        self.web_page.runJavaScript(
            _json_result_script(self.plan.rollback_script),
            self._handle_release_result,
        )

    def _handle_release_result(self, value: Any) -> None:
        outcome = interpret_release_result(value)
        self._release_in_progress = False
        if outcome.ok:
            self._hold_active = False
            self._release_required = False
            message = (
                "No GolfHub-created spots remain selected."
                if outcome.code == "nothing_to_release"
                else "Release requested. Waiting for the official site to finish unlocking the spotsâ€¦"
            )
        else:
            # Keep the state conservative.  The close request still completes
            # after the provider wait, but the visible status never claims the
            # hold was released when the page did not confirm it.
            self._release_required = True
            message = (
                "The official page could not confirm every release. Any remaining hold will expire under the course's rules."
            )
        self._set_status(outcome.code, message)
        self.release_finished.emit(outcome.ok, outcome.code, outcome.count)
        self._update_buttons()

        close_after = self._close_after_release and outcome.ok
        automatic_cleanup = self._automatic_cleanup
        self._close_after_release = False
        self._automatic_cleanup = False

        def after_wait() -> None:
            self._set_busy(False)
            if close_after:
                self._finish_close()
            elif not outcome.ok:
                self._set_status(
                    "release_not_verified",
                    "Release was not verified. Keep this page open and deselect any selected spots manually before closing.",
                )
                self._update_buttons()
            elif automatic_cleanup and outcome.ok:
                self._set_status(
                    "assist_failed_released",
                    "GolfHub made no booking and released any partial selection. You can continue manually.",
                )
                self._update_buttons()

        QTimer.singleShot(outcome.wait_before_close_ms, after_wait)

    @Slot()
    def release_holds_and_close(self) -> None:
        """Release the recorded temporary cells, wait, then close the dialog."""

        if self._continued_to_checkout:
            self._finish_close()
        elif self._release_required or self._hold_active:
            self._begin_release(close_after=True)
        else:
            self._finish_close()

    @Slot()
    def request_close(self) -> None:
        """Close safely; an active or uncertain hold always takes rollback first."""

        self.release_holds_and_close()

    def _finish_close(self) -> None:
        self._allow_close = True
        super().reject()

    def reject(self) -> None:
        # QDialog maps Escape to reject(), so it must follow the same cleanup
        # path as the window close control.
        if self._allow_close:
            super().reject()
        else:
            self.request_close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return
        if self._continued_to_checkout or not (
            self._hold_active or self._release_required or self._release_in_progress
        ):
            self._allow_close = True
            event.accept()
            return
        event.ignore()
        self.request_close()


__all__ = [
    "BookingAssistDialog",
    "DEFAULT_RELEASE_WAIT_MS",
    "MAX_RELEASE_WAIT_MS",
    "ScriptOutcome",
    "interpret_hold_result",
    "interpret_release_result",
    "is_checkout_url",
    "plan_allows_temporary_hold",
]

