# Independent source review — 20 November 2026

Status: complete for the reviewed local source and saved execution evidence, with no blocking findings. The final aggregate, focused baseline/repair, modal records, failure history and report counts reconcile. This is independent verification of stored results, not test execution by the reviewer. The initial static-warning review is preserved in `pre-visual-review.md`; remote publication/CI verification remains the task owner's separate step.

## Reviewed snapshot and scope

- Base: PR32, `66eaf00f76e748cf6f76ef6a758574a3d996360c`.
- Worktree: `/workspace/golfhub-20261120`.
- Application SHA256: `bbf50a775cfbfbe8e126fac8b0fd958545d7455567fc76d72e9aac5ff0cc7403`.
- Frozen test SHA256 (`tests/test_booking_context.py`): `e0aa2858de8a0e5ab940d9003f78c8e23e4c3816cc6df71ab83f3a5ef63f7e2c`.
- Reviewed the complete application/test diff, all eight browser handoff paths, original and new test classes, and workflow byte comparisons. The reviewer ran read-only Git/Python AST and hashing checks, not application tests, browser probes or CI.

## Correctness and scope findings

The helper attempts the existing URL once. A truthy browser result returns without new feedback; a false result or `OSError`/`webbrowser.Error` produces one warning with the original URL. The exception handler is limited to those two exception types and does not swallow unrelated programming errors. It neither retries nor changes the booking target.

Each initiating card passes itself as the warning parent; the five controller paths pass the existing window. Existing missing-link, delegated booking-handler, cancel and confirmed-hold routes are preserved. Booking plan construction, submitted/displayed context, player choices and hold confirmation are unchanged. A warning describes failure to hand off to the browser; it does not claim provider unavailability. Conversely, a true browser result is not proof that the page loaded or a booking succeeded.

An AST comparison restored the eight helper calls to their previous `webbrowser.open` calls and removed the new helper. The resulting application AST matched exact PR32. This establishes that the reviewed runtime change is confined to the helper and eight substitutions.

The revised helper constructs a parented warning `QMessageBox` with an explicit OK action. `Qt.PlainText` preserves the literal address, including ampersands or markup-like characters. Its stylesheet string is identical to the existing invalid-time-range dialog in `GolfHub.params`, including light text and a gold OK button. Mouse and keyboard text-selection flags are applied after the stylesheet and before `exec()`; the intermediate reverse order reset keyboard selection under Qt and failed the unchanged tests. The source now corrects that order without loosening assertions or introducing focus manipulation.

The AST restoration proof was repeated on this final helper. No additional regression case is required by this source review for the narrowed handoff scope. Actual painted readability, copy interaction and native focus behavior require their separately identified evidence; dialog-property assertions alone do not establish them.

## Regression-test review

The entire original `BookingContextTests` class, including its eight methods and helpers, is AST-identical to PR32. Eleven new methods extend the existing CI-selected module:

- Eight routes each cover true, false, `OSError` and `webbrowser.Error`: 32 route/outcome subscenarios. Assertions check the exact URL, one handoff, warning parent/title, plain text, both selection flags, preserved prior information/warnings, and absence of escaped Qt callback errors.
- Remaining methods preserve missing-link guards, cancellation and confirmed-hold dialog handoff. The hold dialog is mocked; these tests do not create a hold.
- New fixtures block socket/DNS calls, provider/weather work, cache persistence and worker execution. Startup callbacks are suppressed and owned timers stopped. Browser calls and booking dialogs are mocked; the actual message object is constructed with its `exec()` intercepted to inspect configured properties. Widget cleanup occurs while isolation patches remain active.

The frozen test hash is identical between the intermediate selection-order failure and the current correction. The whole original eight-test class remains AST-identical to PR32.

## Workflow preservation

All five workflow files are byte-identical to PR32. The existing `test_booking_context.py` module remains selected; no workflow, production trigger, dispatch, release or deployment change is present. Prior static trigger analysis applies; no workflow was executed or queried by this reviewer.

| Workflow | SHA256 |
| --- | --- |
| `check-alerts.yml` | `7506c924a7dff57b658c5fce283d7f1e797f6828dc406ebf2089887a21c1fe38` |
| `course-news.yml` | `ac88359f6171de02b663706008ea7949efc35675996d69a98e7e36c40ee06a26` |
| `refresh-cache-10min.yml` | `0882c7a48c22b5eb6199a85694c7abd209eff63abab2dd6d145cf41614594391` |
| `test-cache.yml` | `319ff262f3859505efa88d7b9ddbcdf76f5fcef921de18c92d2b26ca6346eb7d` |
| `test-desktop.yml` | `249034d9961e423cd1f9d5945c1972e3163a3b67da67ca9e53b60fdd2f7505ad` |

## Verified saved results and preserved execution history

The following results were reconciled against saved JSON, logs and captures. They were not independently executed by this reviewer:

- Frozen final-file baseline on exact PR32: **19 methods, 11 passed / 8 failed**, 24 failing subrecords and zero errors. Three initial missing-card guard fixture-owner errors were corrected and retained separately.
- Initial static-warning helper: **361 aggregate passes**, preserved under `pre-visual-review-aggregate`. Actual modal inspection found a dark OK button on a dark background, so that passing aggregate applies to an earlier candidate.
- Intermediate styled helper, application hash `e109b3e6805b72352309b0c2231090e6d8294cae737a2595a6a124c995be3441`: **361 methods executed, eight failing methods / 24 selection-flag failure records**, preserved under `pre-selection-order-aggregate`. A plain Qt probe reproduced the stylesheet reset. Moving the selection-flags call after styling corrected the source ordering; the tests were unchanged.
- Current `bbf50a77…` candidate: **19/19 focused methods passed**, with the same frozen file that produced the baseline failures. All 32 matrix subscenarios and four missing-link subscenarios reconcile; cancel and confirmed-plan controls remain separate method checks.
- Final applicable aggregate: **361 tests passed = 229 desktop CI-selected + 95 cache/integrity + 37 additional**, in 28 isolated module processes, with zero failures/errors/skips and all recorded exits zero. Every module's `QA_RESULT` log entry matches the summary. All 34 recorded test-file hashes and four source hashes match the current files. This final run is distinct from both earlier aggregates.
- Final modal evidence: **four cases / 68 assertions passed**, with stable final source hashes, zero exceptions/callback errors and shown selection flags of `3`. The reviewer independently inspected the short- and long-address 980×640 captures: complete text and gold OK are visible without clipping. Their 1280×800 widget captures are byte-identical; recorded geometry is 353×125 and 525×155 respectively. This verifies these captures/properties, not clipboard use, native behavior or successful browser loading.
- Two initial automatic focus-restoration assertions failed and remain preserved. A plain Qt reference without GolfHub showed the same absent `focusWidget`/`activeWindow`; explicit reactivation restored the button for retry. Treat this as an offscreen focus limitation, not proven native restoration or an application fix. No focus workaround was added, and no Ctrl+A or clipboard operation is claimed.

A final-aggregate summary was visible for one read and unavailable on follow-up while evidence was being revised. No final total was inferred from that transient observation. This was a read-only missing-file result, not a permission denial or application/test execution. An initial attempt to replace this review was rejected as an invalid duplicate-target patch before any edit; this corrected update changes documentation only.

The report's independent keyboard-expansion evidence is correctly attributed to unchanged PR32: 84 named assertions, two viewports and four intercepted BOOK callbacks. It is not added to the 361 unittest count. The original static-warning, selection-order and focus failures remain separate and are not relabelled as final passes. A read-only evidence summarizer initially assumed the setter-order JSON was an object; its list format was then handled correctly, without changing any probe or result.

All report/scope local links were checked: 26 resolved, with the 27th pointing to the deliberately subsequent `evidence.json` manifest. The task owner will generate and verify that manifest after this review, including final review/provenance hashes. No other broken link or count/scope discrepancy was found. Compilation, actionlint and whitespace checks are task-owner checks; they were not rerun by this reviewer.

No installed Windows/Android, real external-browser success/failure, live booking, hold, provider or notification-delivery verification is claimed. Historical Windows `cache_close` diagnosis and canonical desktop/mobile integration remain unresolved. Prior denied routes were not retried; this review made no remote calls or application/test edits.
