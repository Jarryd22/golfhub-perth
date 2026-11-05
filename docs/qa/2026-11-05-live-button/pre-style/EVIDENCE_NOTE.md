*Archived state-only stage. Relative links below were adjusted for this archive location; recorded results and conclusions are unchanged.*

# Refresh Live control-state evidence

Exact PR24 `53cbfd463af717b3e1e7670af1911e0cd11c4714` reproduces the mismatch:
start a single-date live request, edit the pending dates to two dates, and then
finish, fail or cancel the request. Refresh Live becomes enabled and stays
enabled after cleanup despite its multi-day tooltip. Clicking it starts no
request and replaces the result status with a single-date restriction.

There is a second phase of the same control-state mismatch: the button is
enabled while the old `scan_thread` is retained, although `search_live` rejects
new work until that reference is cleared. A simulated cleanup interval with
`isRunning=False` and `wait(0)=False`, followed by actual date-control changes,
reproduces an enabled button whose click is silently ignored. This is a source
controller probe with inert thread objects, not a native shutdown diagnosis.

- [Six-case before JSON](../before/six-cases/probe.json) and [log](../before/six-cases.log)
- [Six-case after JSON](after/probe.json) and [log](after-probe.log)
- [Reusable six-case probe](../live-button-probe.py)
- [Closing before](../before/closing-probe.json), [closing after](after/closing-probe.json)
  and [reusable closing probe](../closing-probe.py)
- [Source overlap](../before/source-overlap.json): preserved loose source has the
  same eligibility/cleanup methods and the same unconditional terminal enable;
  the newer recovery wording differs but does not repair this control state.

The initial three-case script, JSON, logs and screenshots are retained in
`before/`, alongside the expanded six-case evidence. They are diagnostic
iterations, not additional unique regression tests.

## State comparison

All six synthetic scenarios have zero callback errors. Each outcome is checked
with pending multiple dates and with controls returned to one date.

| Phase | Exact PR24 | Repair |
| --- | --- | --- |
| Terminal signal, old request object retained | Enabled in 6/6 cases; click ignored | Disabled in 6/6 cases |
| Simulated cleanup held; date changes delivered | Enabled in 6/6 cases | Disabled in 6/6 cases |
| Cleanup completed, pending multiple dates | Enabled in 3/3 cases; click rejected with restriction | Disabled in 3/3 cases; status retained |
| Cleanup completed, pending single date | Enabled; actual click creates a new inert worker | Same successful retry behavior in 3/3 cases |
| Actual closeEvent waiting for work, then cancelled signal | Re-enabled despite closing; click ignored | Remains disabled |

Before/after success screenshots and the after single-date failure screenshot
were inspected at 1280×800. Existing result/recovery content and action positions
remain intact. The current OutlineButton stylesheet renders enabled and disabled
states nearly identically; screenshots alone do not establish eligibility. The
JSON `isEnabled()` observations and actual intercepted button clicks establish
the functional result. No styling or product-design change is included.

## Identical-file tests

Final `tests/test_live_button_state.py` SHA256:
`5c6aa871fdf7a9996ee91dd8201b398d1f46cc979bd3ab6d7faaf53fa71ddb6c`.

| Source | Methods | Outcome | Evidence |
| --- | ---: | --- | --- |
| Exact PR24; Qt source `fc61c95941605ba2bb79608fdf619d988ca9e3037f595377b353c10be3bfbfc3` | 9 | 1 passed, 8 assertion failures, 0 errors/skips | [JSON](new-tests-baseline.json), [log](new-tests-baseline.log) |
| Repair working tree; Qt source `4b28a598d1e8b2bb1b88f8a95195e8fca2b620b4a00ea75d428d44de5f35055b` | 9 | 9 passed, 0 failures/errors/skips | [JSON](new-tests-after.json), [log](new-tests-after.log) |

The repair metadata records the checked-out parent commit and the changed file
hash actually tested. Final commit and aggregate checks are recorded by the
integration pass. The cache-request overlap guard passes on both versions;
the other eight methods expose the control-state mismatch. No test fixture
errors or assertion relaxations occurred in these new-test executions.

Coverage includes success/failure/cancellation with pending multiple dates;
single-date retry after cleanup; date edits during simulated unfinished cleanup;
returning from multiple dates to one; an actual new cache request while old live
cleanup completes; preservation of submitted result/save context despite pending
date/player/time changes; and disabled actions while the window closes.

The separate [keyboard diagnostic](../unchanged-keyboard/probe.json) passes 4/4
on unchanged PR24: popup Apply/Cancel restore focus and selection, custom time
controls enter the Tab order, and hidden controls leave it. It found no additional
justified defect and is not counted in the nine regressions.

## Limits

All activity is Linux Qt offscreen with isolated temporary runtime/cache paths.
Worker objects, signals, controls and callbacks are real source components;
thread objects are inert mocks, no executor/provider work runs, and socket/DNS,
weather, browser and booking-assist access are blocked or intercepted. The
successful-save test observes a mock save. Native Windows/Android, actual worker
timing, screen readers, live availability/bookings and notification delivery
remain untested. Historical Windows `cache_close` and canonical integration
remain unresolved; no native lifecycle retry, timeout change or production
action was performed.
