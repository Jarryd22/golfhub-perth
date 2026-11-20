# Independent source review — 20 November 2026

Status: no blocking source or regression-test finding in the reviewed diff. Execution and visual validation are not final: the parent reported a passing focused run, an aggregate still in progress, and two modal-focus assertions requiring follow-up. This review must be reconciled with the final evidence before publication.

## Reviewed snapshot and scope

- Base: PR32, `66eaf00f76e748cf6f76ef6a758574a3d996360c`.
- Worktree: `/workspace/golfhub-20261120`.
- Application SHA256: `f6692c7c46bff54027cf12012cc78e045d2381d9fa6f10f64c3f75ffaa05212e`.
- Test SHA256 (`tests/test_booking_context.py`): `c254663d82f33195ab6593b692f44a9252815e54e76d445240205a933f883a90`.
- Reviewed the complete application/test diff, all eight browser handoff paths, original and new test classes, and workflow byte comparisons. The reviewer ran read-only Git/Python AST and hashing checks, not application tests, browser probes or CI.

## Correctness and scope findings

The helper attempts the existing URL once. A truthy browser result returns without new feedback; a false result or `OSError`/`webbrowser.Error` produces one warning with the original URL. The exception handler is limited to those two exception types and does not swallow unrelated programming errors. It neither retries nor changes the booking target.

Each initiating card passes itself as the warning parent; the five controller paths pass the existing window. Existing missing-link, delegated booking-handler, cancel and confirmed-hold routes are preserved. Booking plan construction, submitted/displayed context, player choices and hold confirmation are unchanged. A warning describes failure to hand off to the browser; it does not claim provider unavailability. Conversely, a true browser result is not proof that the page loaded or a booking succeeded.

An AST comparison restored the eight helper calls to their previous `webbrowser.open` calls and removed the new helper. The resulting application AST matched exact PR32. This establishes that the reviewed runtime change is confined to the helper and eight substitutions.

No additional regression case is required by this source review for the narrowed return/exception-feedback scope. Actual dialog focus, readability and native-platform behavior require their separately identified evidence and must not be inferred from mocked message boxes.

## Regression-test review

The entire original `BookingContextTests` class, including its eight methods and helpers, is AST-identical to PR32. Eleven new methods extend the existing CI-selected module:

- Eight routes each cover true, false, `OSError` and `webbrowser.Error`: 32 route/outcome subscenarios. Assertions check the exact URL, one handoff, warning parent, preserved prior information/warnings, and absence of escaped Qt callback errors.
- Remaining methods preserve missing-link guards, cancellation and confirmed-hold dialog handoff. The hold dialog is mocked; these tests do not create a hold.
- New fixtures block socket/DNS calls, provider/weather work, cache persistence and worker execution. Startup callbacks are suppressed and owned timers stopped. Browser calls, message boxes and booking dialogs are mocked. Widget cleanup occurs while isolation patches remain active.

## Workflow preservation

All five workflow files are byte-identical to PR32. The existing `test_booking_context.py` module remains selected; no workflow, production trigger, dispatch, release or deployment change is present. Prior static trigger analysis applies; no workflow was executed or queried by this reviewer.

| Workflow | SHA256 |
| --- | --- |
| `check-alerts.yml` | `7506c924a7dff57b658c5fce283d7f1e797f6828dc406ebf2089887a21c1fe38` |
| `course-news.yml` | `ac88359f6171de02b663706008ea7949efc35675996d69a98e7e36c40ee06a26` |
| `refresh-cache-10min.yml` | `0882c7a48c22b5eb6199a85694c7abd209eff63abab2dd6d145cf41614594391` |
| `test-cache.yml` | `319ff262f3859505efa88d7b9ddbcdf76f5fcef921de18c92d2b26ca6346eb7d` |
| `test-desktop.yml` | `249034d9961e423cd1f9d5945c1972e3163a3b67da67ca9e53b60fdd2f7505ad` |

## Execution evidence pending final review

The following status was supplied by the parent and was not independently executed by this reviewer:

- Focused repair run: 19/19 methods passed.
- Aggregate: 27 of 28 modules passed; cache module pending at this review checkpoint.
- Initial baseline: eight true-result subscenarios passed and 24 failure-result subscenarios failed. Three missing-card guard checks initially had a fixture-owner error; the corrected final-file baseline was still being finalized.
- Real modal probes at two sizes show the warning fitting, but two focus assertions failed. Comparison with an unmodified Qt reference is under investigation. These failures remain unresolved at this checkpoint and must not be omitted or labelled passing.

No installed Windows/Android, real external-browser success/failure, live booking, hold, provider or notification-delivery verification is claimed. Historical Windows `cache_close` diagnosis and canonical desktop/mobile integration remain unresolved. Prior denied routes were not retried; this review made no remote calls or application/test edits.
