# Independent midnight-rollover review — 21 October 2026

Reviewed the application and test-only workflow diff against PR #13 head `8b01866f3783d9ef021e114c81c139dede1facc1`, plus the new `tests/test_midnight_rollover.py` suite. Final reviewed application SHA-256: `214cf0e3cff96f5014c75d70178abf8ca1470c0d271bad64a0c5734677a6ba50`; test SHA-256: `4c783f5aebdd05ae60111a5d7572fed086d4894624f630d982cd58c14a07c73f`.

## Finding corrected during review

The initial `_accept_dates()` implementation emitted `datesChanged` twice when a previously committed date expired but the open picker had a valid future draft selection. An independent fake-clock probe selected Dec 31 in the button, Jan 5 only in the popup, advanced to Jan 1, and clicked Apply. Initial emissions were Jan 1 then Jan 5. The corrected implementation silently rebases bounds and accepts the draft, then emits once if the final selection differs from the original. The identical probe now emits only Jan 5. The new regression suite covers this case and fallback acceptance.

No blocking defect remains in the reviewed diff.

## Independent validation

- Offline, offscreen PySide6/Qt 6.11.2, Python from the saved environment; no dependency changes.
- New midnight suite: **15/15 pass**.
- Existing Perth-date, keyboard-calendar and multi-day suites: **6 + 8 + 12 = 26/26 pass**, in separate processes. These are a repeated subset of the overall run, not additional unique cases.
- Separate real-widget edge probes pass: extending Jan 31 to Feb 1 enables the next-month control while retaining the Jan 20 keyboard cursor/page; a generic non-rolling date button retains its explicitly supplied July 2026 bounds; closing with an outstanding mocked cache thread stops the rollover timer and ignores subsequent activation/refresh.
- Submitted context dictionaries are not edited by this repair. New user searches refresh through `params()`, while an explicitly passed cache-to-live fallback retains its submitted date. This is intentional, not an assertion that prior-day availability remains useful.
- Active-popup pending selections are independently rebased and do not apply on Cancel. Relative labels refresh without selection signals when Tomorrow becomes Today. Expired selection removal emits once and updates day mode.
- Application-owned timer is stopped with deferred UI timers during close; existing native-worker cleanup timers remain separate. Activation events safely check for an initialized date control and the refresh method observes `_closing`.
- Only the test-desktop workflow gains path/module entries; no production workflow or permission modification is present.

## Evidence and limits

Independent probe/log files are under `/tmp/golfhub-midnight-review/`: `probe.py`, `result.json` (untouched-base reproduction), `emission-probe.py`, `edge-probe.py`, `edge-results.json`, `rollover-tests.log`, `perth-tests.log`, `keyboard-tests.log`, and `multiday-tests.log`.

Tests intercept network and browser paths. Fake live/cache workers in the new suite test request construction and context, not worker lifecycle or provider execution; existing lifecycle regressions are separately run by the main agent. This review does not verify installed Windows/Android, native assistive technology, device delivery, production availability, or WebEngine. No Chromium sandbox setting was changed.
