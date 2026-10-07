"""Read Wembley's public, browser-rendered timesheets with strict traffic limits.

The official page performs its own normal navigation. This module never reads
CAPTCHA responses, exports a navigated URL, interacts with challenges, or clicks
a timesheet booking cell. Any challenge/failure stops browser work for this
process; callers retain their calendar-only fallback.
"""
from __future__ import annotations

from datetime import date
from html import escape
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit


TOTAL_TIMEOUT_SECONDS = 45
CLEANUP_TIMEOUT_SECONDS = 2
NAVIGATION_TIMEOUT_SECONDS = 15
MAX_PRODUCTS = 2
MAX_ROWS_PER_PRODUCT = 256
_LOCK = threading.Lock()
_STOP_REASON: str | None = None
_REASONS = {
    "browser_disabled", "unsupported_platform", "invalid_request",
    "browser_unavailable", "browser_error", "timeout", "interactive_challenge",
    "access_denied", "login_required", "unrecognized_page",
}
_HOSTS = {"www.wembleygolf.com.au", "wembleygolf.com.au"}
_COURSES = {"102184": "Old", "102211": "Old", "102193": "Tuart", "102202": "Tuart"}
_HOLES = {"102184": "18", "102193": "18", "102211": "9", "102202": "9"}


def _result(reason: str | None = None) -> dict:
    return {"rows": [], "completed_products": [], "stop_reason": reason}


def reset_browser_collection_state() -> None:
    """Begin a new cache shard, retaining the per-process serialization lock."""
    global _STOP_REASON
    with _LOCK:
        _STOP_REASON = None


def _safe_url(url: str, date_str: str, resource: str, fee: str | None = None) -> bool:
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if (
            parsed.scheme != "https" or parsed.netloc not in _HOSTS
            or parsed.fragment or parsed.username or parsed.password
            or set(query) - {"bookingResourceId", "selectedDate", "feeGroupId", "mobile"}
            or query.get("bookingResourceId") != [resource]
            or query.get("selectedDate") != [date_str]
            or ("mobile" in query and query["mobile"] != ["true"])
        ):
            return False
        if parsed.path == "/guests/bookings/ViewPublicCalendar.msp":
            return "feeGroupId" not in query
        return (
            fee is not None
            and parsed.path == "/guests/bookings/ViewPublicTimesheet.msp"
            and query.get("feeGroupId") == [fee]
        )
    except (TypeError, ValueError):
        return False


def _valid_request(calendar_url: str, date_str: str, resource: str, products: dict) -> bool:
    try:
        return (
            date.fromisoformat(date_str).isoformat() == date_str
            and re.fullmatch(r"\d+", resource) is not None
            and isinstance(products, dict) and 0 < len(products) <= MAX_PRODUCTS
            and _safe_url(calendar_url, date_str, resource)
            and all(
                isinstance(fee, str) and re.fullmatch(r"\d+", fee)
                and isinstance(source, str) and _safe_url(source, date_str, resource, fee)
                for fee, source in products.items()
            )
        )
    except (TypeError, ValueError):
        return False


def _validated_result(candidate: dict, products: dict[str, str]) -> dict:
    """Only the fixed protocol fields and known clean row sources may escape."""
    try:
        completed = candidate["completed_products"]
        rows = candidate["rows"]
        reason = candidate["stop_reason"]
        if (
            not isinstance(completed, list) or not all(isinstance(fee, str) for fee in completed)
            or len(set(completed)) != len(completed) or not set(completed) <= set(products)
            or not isinstance(rows, list) or len(rows) > MAX_ROWS_PER_PRODUCT * len(completed)
            or reason not in _REASONS | {None}
        ):
            return _result("browser_error")
        allowed_sources = {products[fee] for fee in completed}
        clean_rows = []
        for row in rows:
            if (
                row["source_url"] not in allowed_sources
                or not re.fullmatch(r"(?:0?[1-9]|1[0-2]):[0-5]\d\s*[ap]m", row["time"], re.I)
                or not isinstance(row["course_raw"], str) or not 0 < len(row["course_raw"]) <= 160
                or type(row["spots"]) is not int or not 1 <= row["spots"] <= 4
            ):
                return _result("browser_error")
            clean_rows.append({key: row[key] for key in ("time", "course_raw", "spots", "source_url")})
        return {"rows": clean_rows, "completed_products": completed, "stop_reason": reason}
    except (KeyError, TypeError, ValueError):
        return _result("browser_error")


def _process_identity(pid: int) -> tuple[int, int] | None:
    """Return Linux parent PID/start ticks without command lines or URLs."""
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[1]), int(fields[19])
    except (OSError, ValueError, IndexError):
        return None


class _WorkerTree:
    """Track the owned worker using pidfds, including detached descendants.

    Playwright launches Chromium in a separate session. Killing only the Python
    worker's process group therefore cannot enforce the browser deadline.
    """
    def __init__(self, pid: int):
        # Acquire before communicate can reap the worker: this fd cannot signal
        # a later unrelated process if Linux reuses the numerical PID.
        self.root_pid = pid
        root_fd = os.pidfd_open(pid)
        self.processes = {pid: (root_fd, _process_identity(pid))}

    @staticmethod
    def _signal(fd: int, number: int) -> None:
        try:
            signal.pidfd_send_signal(fd, number)
        except OSError:
            pass

    def terminate(self, *, include_root: bool = True) -> None:
        deadline = time.monotonic() + CLEANUP_TIMEOUT_SECONDS
        try:
            if include_root:
                self._signal(self.processes[self.root_pid][0], signal.SIGSTOP)
            while time.monotonic() < deadline:
                # Freeze parents before rescanning: any child forked immediately
                # before SIGSTOP is included on the following scan. PID/start
                # pairs keep a reaped/reused ancestor out of the owned tree.
                owned = {pid for pid, (_fd, identity) in self.processes.items()
                         if identity is not None and _process_identity(pid) == identity}
                added = False
                for entry in Path("/proc").iterdir():
                    if time.monotonic() >= deadline:
                        break
                    if not entry.name.isdigit():
                        continue
                    pid = int(entry.name)
                    identity = _process_identity(pid)
                    if pid in self.processes or identity is None or identity[0] not in owned:
                        continue
                    try:
                        fd = os.pidfd_open(pid)
                    except OSError:
                        continue
                    # Revalidate the candidate and its parent after pidfd_open.
                    # No signal is sent based solely on a stale /proc snapshot.
                    parent = identity[0]
                    if (
                        _process_identity(pid) != identity
                        or _process_identity(parent) != self.processes[parent][1]
                    ):
                        os.close(fd)
                        added = True  # Re-scan descendants whose parent changed.
                        continue
                    self.processes[pid] = (fd, identity)
                    self._signal(fd, signal.SIGSTOP)
                    added = True
                if not added:
                    break
        except OSError:
            pass
        finally:
            # Always unconditionally kill every frozen owned process, including
            # on discovery failure; never leave a stopped browser behind.
            for pid, (fd, _identity) in reversed(list(self.processes.items())):
                if include_root or pid != self.root_pid:
                    self._signal(fd, signal.SIGKILL)
                os.close(fd)


def collect_wembley_rows(
    calendar_url: str,
    date_str: str,
    booking_resource_id: str,
    products: dict[str, str],
    *,
    executable_path: str | None = None,
) -> dict:
    """Return safe rows, completed fee IDs, and a fixed stop-reason enum.

    Disabled unless explicitly enabled for the Linux cache job. At most two
    calendar loads and two calendar availability clicks occur per invocation.
    There are no request retries. Timeout cleanup includes Chromium's detached
    descendants. ``executable_path`` supports local, routed browser tests.
    """
    global _STOP_REASON
    if os.environ.get("GOLFHUB_WEMBLEY_BROWSER") != "1":
        return _result("browser_disabled")
    if (
        not sys.platform.startswith("linux")
        or not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal")
    ):
        return _result("unsupported_platform")
    with _LOCK:
        if _STOP_REASON:
            return _result(_STOP_REASON)
        if not _valid_request(calendar_url, date_str, booking_resource_id, products):
            _STOP_REASON = "invalid_request"
            return _result(_STOP_REASON)
        payload = {
            "calendar_url": calendar_url, "date_str": date_str,
            "booking_resource_id": booking_resource_id, "products": products,
            "executable_path": executable_path,
        }
        # Do not inherit Playwright debugging options that can log navigated URLs.
        child_env = {key: value for key, value in os.environ.items()
                     if key not in {"DEBUG", "DEBUG_FILE", "PWDEBUG"}}
        process = None
        worker_tree = None
        result = _result("browser_error")
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "app.wembley_browser", "--worker"],
                cwd=Path(__file__).resolve().parents[1], env=child_env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, start_new_session=True,
            )
            worker_tree = _WorkerTree(process.pid)
            # Reserve time inside the 45-second budget for detached descendants.
            cleanup_budget = min(CLEANUP_TIMEOUT_SECONDS, TOTAL_TIMEOUT_SECONDS / 5)
            output, _ = process.communicate(json.dumps(payload), timeout=TOTAL_TIMEOUT_SECONDS - cleanup_budget)
            if process.returncode == 0:
                result = _validated_result(json.loads(output), products)
        except subprocess.TimeoutExpired:
            result = _result("timeout")
        except (OSError, TypeError, ValueError):
            result = _result("browser_error")
        finally:
            if process is not None:
                if worker_tree is not None:
                    worker_tree.terminate()
                elif process.returncode is None:
                    process.kill()
                process.wait()
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()
        if result["stop_reason"]:
            _STOP_REASON = result["stop_reason"]
        return result


# Return only page identity booleans, fee heading, and fixed states. The site's navigated URL
# can contain its own ephemeral CAPTCHA parameter and must never leave the page.
_PAGE_STATE = r"""({date, fee, resource}) => {
    const visible = e => !!(e && e.getBoundingClientRect().width > 0 &&
        e.getBoundingClientRect().height > 0 &&
        getComputedStyle(e).visibility !== 'hidden' &&
        getComputedStyle(e).display !== 'none');
    for (const iframe of document.querySelectorAll('iframe')) {
        if (!visible(iframe)) continue;
        const bounds = iframe.getBoundingClientRect();
        if (bounds.bottom <= 0 || bounds.right <= 0 || bounds.top >= innerHeight || bounds.left >= innerWidth)
            continue;
        const src = iframe.getAttribute('src') || '';
        if (/recaptcha\/.*bframe/i.test(src) ||
            (/recaptcha\/.*anchor/i.test(src) && !/[?&]size=invisible(?:&|$)/i.test(src)) ||
            /hcaptcha.*(?:challenge|checkbox)|challenges\.cloudflare\.com/i.test(src))
            return {stop: 'interactive_challenge'};
    }
    if ([...document.querySelectorAll('input[type=password]')].some(visible))
        return {stop: 'login_required'};
    const text = document.body ? document.body.innerText : '';
    if (/access denied|request blocked|too many requests|\bforbidden\b|temporarily blocked/i.test(text))
        return {stop: 'access_denied'};
    if (/verify (?:that )?you are (?:a )?human|I.?m not a robot|complete (?:the|this) (?:captcha|security check)|solve (?:the|this) captcha/i.test(text))
        return {stop: 'interactive_challenge'};
    if (/log\s*in (?:is )?required|sign in to continue|log in to continue/i.test(text))
        return {stop: 'login_required'};
    const location = new URL(window.location.href);
    const one = (key, value) => {
        const values = location.searchParams.getAll(key);
        return values.length === 1 && values[0] === value;
    };
    const identity = ['www.wembleygolf.com.au', 'wembleygolf.com.au'].includes(location.hostname)
        && location.protocol === 'https:'
        && location.pathname === '/guests/bookings/ViewPublicTimesheet.msp'
        && one('selectedDate', date) && one('feeGroupId', fee)
        && one('bookingResourceId', resource);
    const rows = [...document.querySelectorAll('div.row-time')].filter(visible).length;
    const empty = [...document.querySelectorAll('#no-rows, .no-rows')].some(e =>
        visible(e) && /no rows|no tee times|timesheet full|no times available/i.test(e.innerText));
    const heading = document.querySelector('h1.feeName');
    const feeName = visible(heading) ? heading.innerText.trim() : '';
    return {identity, rows, empty, feeName};
}"""

_ROW_PROJECTIONS = r"""() => {
    const visible = e => !!(e && e.getClientRects().length &&
        getComputedStyle(e).visibility !== 'hidden' &&
        getComputedStyle(e).display !== 'none');
    const text = e => e ? e.innerText.trim() : '';
    const fee = text(document.querySelector('h1.feeName'));
    return [...document.querySelectorAll('div.row-time')].filter(visible).map(row => ({
        time: text(row.querySelector('h3')),
        course: text(row.querySelector('h4')) || fee,
        available: [...row.querySelectorAll('div.cell-available')].filter(visible).length,
        taken: [...row.querySelectorAll('div.cell-taken')].filter(visible).length,
    }));
}"""


class _Stop(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def _milliseconds(deadline: float, limit: float = NAVIGATION_TIMEOUT_SECONDS) -> int:
    remaining = min(limit, deadline - time.monotonic())
    if remaining <= 0:
        raise _Stop("timeout")
    return max(1, int(remaining * 1000))


def _page_state(page, expected: dict, denied: list[bool]) -> dict:
    if denied[0]:
        raise _Stop("access_denied")
    state = page.evaluate(_PAGE_STATE, expected)
    if state.get("stop"):
        raise _Stop(state["stop"])
    if state.get("identity"):
        heading = state.get("feeName", "")
        courses = re.findall(r"\b(?:old|tuart)\b", heading, re.I)
        holes = re.findall(r"\b(9|18)\s*(?:h|holes?)\b", heading, re.I)
        expected_course = _COURSES.get(expected["fee"])
        expected_holes = _HOLES.get(expected["fee"])
        if (
            (expected_course and any(course.casefold() != expected_course.casefold() for course in courses))
            or (expected_holes and any(value != expected_holes for value in holes))
        ):
            raise _Stop("unrecognized_page")
    return state


def _calendar_cell(page, fee: str, date_str: str):
    groups = page.locator(f'.feeGroupRow[data-feeid="{fee}"]')
    if groups.count() != 1:
        raise _Stop("unrecognized_page")
    cells = groups.locator("div.cell[onclick]")
    pattern = re.compile(
        r"^\s*(?:return\s+)?redirectToTimesheet\(\s*(['\"])" + re.escape(fee)
        + r"\1\s*,\s*(['\"])" + re.escape(date_str) + r"\2\s*\)\s*;?\s*$"
    )
    matching = [cells.nth(index) for index in range(cells.count())
                if pattern.fullmatch(cells.nth(index).get_attribute("onclick") or "")
                and cells.nth(index).is_visible()]
    if len(matching) != 1:
        raise _Stop("unrecognized_page")
    return matching[0]


def _parse_projections(projections: list, source: str, fee: str | None = None) -> list[dict]:
    from app.golfhub_core import parse_wembley_timesheet

    if not 0 < len(projections) <= MAX_ROWS_PER_PRODUCT:
        raise _Stop("unrecognized_page")
    fragments = []
    expected_course = _COURSES.get(fee or (parse_qs(urlsplit(source).query).get("feeGroupId") or [""])[0])
    for index, row in enumerate(projections):
        if (
            not re.fullmatch(r"(?:0?[1-9]|1[0-2]):[0-5]\d\s*[ap]m", row["time"], re.I)
            or not row["course"] or len(row["course"]) > 160
            or (expected_course and not re.match(rf"^{expected_course}\b", row["course"], re.I))
            or not 0 <= row["available"] <= 4 or not 0 <= row["taken"] <= 4
            or not 0 < row["available"] + row["taken"] <= 4
        ):
            raise _Stop("unrecognized_page")
        # Reuse the established parser, but only with constructed, escaped row
        # data: never read full HTML or transfer scripts, inputs, IDs, or links.
        fragments.append(
            f'<div id="row-{index}" class="row-time"><h3>{escape(row["time"])}</h3>'
            f'<h4>{escape(row["course"])}</h4>'
            + '<div class="cell-available">Available</div>' * row["available"]
            + '<div class="cell-taken">Taken</div>' * row["taken"] + '</div>'
        )
    return [
        {"time": row["time"], "course_raw": row["course_raw"], "spots": row["spots"], "source_url": source}
        for row in parse_wembley_timesheet("".join(fragments))
    ]


def _collect_in_browser(payload: dict, *, route_handler=None) -> dict:
    """Worker implementation; route_handler permits wholly offline smoke tests."""
    result = _result()
    try:
        from playwright.sync_api import sync_playwright, Error, TimeoutError as BrowserTimeout
    except ImportError:
        return _result("browser_unavailable")
    deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
    try:
        with sync_playwright() as playwright:
            options = {"headless": True, "timeout": _milliseconds(deadline)}
            if payload.get("executable_path"):
                options["executable_path"] = payload["executable_path"]
            browser = playwright.chromium.launch(**options)
            try:
                context = browser.new_context()
                if route_handler is not None:
                    context.route("**/*", route_handler)
                page = context.new_page()
                denied = [False]
                page.on("response", lambda response: denied.__setitem__(0, True)
                        if response.status in {401, 403, 429} else None)
                for fee, source in payload["products"].items():
                    expected = {"date": payload["date_str"], "fee": fee,
                                "resource": payload["booking_resource_id"]}
                    page.goto(payload["calendar_url"], wait_until="domcontentloaded",
                              timeout=_milliseconds(deadline))
                    _page_state(page, expected, denied)
                    cell = _calendar_cell(page, fee, payload["date_str"])
                    _page_state(page, expected, denied)
                    cell.click(timeout=_milliseconds(deadline), no_wait_after=True)
                    page_deadline = min(deadline, time.monotonic() + NAVIGATION_TIMEOUT_SECONDS)
                    while True:
                        _milliseconds(page_deadline)
                        try:
                            state = _page_state(page, expected, denied)
                        except Error:
                            # Context destruction while normal navigation commits
                            # is expected. This polls state, without another request.
                            if page.is_closed():
                                raise _Stop("browser_error")
                            page.wait_for_timeout(min(100, _milliseconds(page_deadline)))
                            continue
                        if state.get("identity") and (state.get("rows") or state.get("empty")):
                            break
                        page.wait_for_timeout(min(100, _milliseconds(page_deadline)))
                    rows = _parse_projections(page.evaluate(_ROW_PROJECTIONS), source, fee) if state["rows"] else []
                    if not _page_state(page, expected, denied).get("identity"):
                        raise _Stop("unrecognized_page")
                    result["rows"].extend(rows)
                    result["completed_products"].append(fee)
            finally:
                browser.close()
    except _Stop as exc:
        result["stop_reason"] = exc.reason
    except BrowserTimeout:
        result["stop_reason"] = "timeout"
    except Error:
        result["stop_reason"] = "browser_error"
    except Exception:
        # Exceptions may embed token-bearing URLs: export a fixed enum only.
        result["stop_reason"] = "browser_error"
    return result


def _worker_main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not _valid_request(payload["calendar_url"], payload["date_str"],
                              payload["booking_resource_id"], payload["products"]):
            result = _result("invalid_request")
        else:
            result = _collect_in_browser(payload)
    except Exception:
        result = _result("browser_error")
    sys.stdout.write(json.dumps(result))
    return 0


def _enable_subreaper() -> bool:
    """Keep this guardian's orphaned descendants owned here until cleanup.

    PR_SET_CHILD_SUBREAPER is process-local child lifecycle management, without
    privileges, browser flags, sandbox changes, or credential changes.
    """
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        libc.prctl.restype = ctypes.c_int
        return libc.prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER
    except (AttributeError, OSError):
        return False


def _guardian_main(executor_command: list[str] | None = None) -> int:
    """Keep a guardian alive if Playwright's executor/driver exits abruptly.

    ``executor_command`` permits local process-lifecycle regression tests only;
    the command-line entry always starts our own browser worker.
    """
    result = _result("browser_error")
    executor = None
    owned_tree = None
    try:
        payload = json.load(sys.stdin)
        if not _valid_request(payload["calendar_url"], payload["date_str"],
                              payload["booking_resource_id"], payload["products"]):
            result = _result("invalid_request")
        elif not _enable_subreaper():
            result = _result("browser_unavailable")
        else:
            # This remains alive while orphaned Chromium/driver descendants
            # are adopted, discovered, stopped, and killed after executor exit.
            owned_tree = _WorkerTree(os.getpid())
            executor = subprocess.Popen(
                executor_command or [sys.executable, "-m", "app.wembley_browser", "--browser-worker"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True,
            )
            output, _ = executor.communicate(
                json.dumps(payload), timeout=TOTAL_TIMEOUT_SECONDS - 2 * CLEANUP_TIMEOUT_SECONDS,
            )
            if executor.returncode == 0:
                result = _validated_result(json.loads(output), payload["products"])
    except subprocess.TimeoutExpired:
        result = _result("timeout")
    except Exception:
        # Exception messages can include navigation URLs, so never export them.
        result = _result("browser_error")
    finally:
        if owned_tree is not None:
            owned_tree.terminate(include_root=False)
        if executor is not None:
            executor.wait()
            for stream in (executor.stdin, executor.stdout):
                if stream is not None:
                    stream.close()
        if owned_tree is not None:
            # Reap already-exited descendants adopted after executor failure.
            try:
                while os.waitpid(-1, os.WNOHANG)[0]:
                    pass
            except ChildProcessError:
                pass
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--worker"]:
        raise SystemExit(_guardian_main())
    if sys.argv[1:] == ["--browser-worker"]:
        raise SystemExit(_worker_main())
    raise SystemExit(2)
