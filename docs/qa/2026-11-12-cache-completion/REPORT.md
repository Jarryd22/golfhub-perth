# Shared-cache worker completion — 12 November 2026 (Perth)

On exact PR28, an exception while constructing, entering or submitting the
cache executor, iterating completions or leaving the executor bypasses
`CacheWorker.finished`. The UI's recovery and thread-quit connections depend on
that signal. Controlled failures reproduce a search left on “Checking shared
cache”; no production occurrence or failure frequency is established.

The repair catches ordinary executor-orchestration exceptions, retains snapshots
already collected, and emits the existing completion signal once. Missing dates
then follow the existing saved-cache, single-date live-fallback or multi-date
unavailable-state paths. No provider retry, new failure UI, ownership or timeout
change is introduced. Hung work that never returns remains outside this fix.

## Provenance and duplication check

- Baseline: PR28 `4616694b65bf50d481dfd985b94e0fc213c38f0a`.
  Branch: `fix/desktop-cache-completion-20261112`, stacked on unchanged
  `fix/desktop-course-count-20261108` in a separate worktree.
- [Fresh repository audit](context-audit.json): 32 branches, 26 drafts #3–28,
  zero non-PR issues; main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`.
  The parent supplied fresh connector observations for both update repositories:
  README-only main trees and unchanged Windows 5.1.17 / Android 0.1.19 releases.
  These are metadata observations, not installed-update tests.
- [Method comparison](cacheworker-duplicate-audit.json): identical worker logic
  across 30 source refs and 17 preserved local sources. No competing repair
  found. The earlier lifecycle, missing-cache, provider-error, grid and count
  repairs are preserved. No applicable AGENTS.md or .agents/skills was found.
- The parent reported the previous attempt stopped at a usage limit. This pass
  resumed the same executor normally after startup; no alternate route or
  environment was used, and no November 9 repair artifact was found.
- [Workflow inspection](workflow-trigger-audit.json): all five workflows
  unchanged. Normal repair push/PR events select desktop/cache tests, with no
  production chain. Existing CI already selects `test_multiday_ui.py`.

## Before and after

Eight regression methods were added to the existing multi-day module. The
identical final file on exact PR28 runs 20 methods: **14 pass, six new methods
fail, nine assertion records including constructor/enter/submission subcases**;
zero errors/skips. The repaired source passes **20/20** on its first execution.

| Controlled trigger | Exact PR28 | Repaired contract |
| --- | --- | --- |
| Constructor, context entry, first/later submission failure | Exception escapes; no completion | One completion with no collected snapshots |
| Completion iteration fails after one result | Exception escapes; collected result not delivered | One completion with the already collected snapshot |
| Executor exit raises after collection | Exception escapes; no completion | One completion with collected snapshots |
| One fetch future raises | Other snapshots survive; failed date is None | Unchanged |
| Successful single-date string / empty input | One keyed result / empty dictionary | Unchanged |

UI callback regressions verify saved-cache reuse for submitted context,
single-date live fallback with the exact submitted context, and multi-date
unavailable wording with configured official links. Live work and persistence
are intercepted. Completed futures not yet collected are not promised salvage
when submission or completion iteration fails.

Evidence: [baseline result](regression/baseline.json),
[readable baseline failure log](regression/baseline.log),
[byte-exact original log](regression/baseline.log.original.gz),
[after result](regression/after.json), [after log](regression/after.log),
[reproduction runner](regression/run-regression.py). Independent diagnostic
scope and real-thread observations are recorded separately in
[journey evidence](journey-scope.md); those observations are not unit-test counts.

The eight-case inert-worker probe reproduces five missing-completion failures
on PR28; all eight cases emit once after repair. Its normal/per-future-error/
all-future-error controls are unchanged. In three separate real-QThread
scenarios, PR28 records an escaped injected error, no completion and a retained
thread reference. The probe explicitly quits/joins the otherwise idle baseline
thread for safe cleanup. On final source all three pass without manual cleanup:
setup failure reaches unavailable recovery and then a successful retry; partial
iteration delivers the first collected date; failure of an old queued request
starts only the newest submitted dates and player filter. These are controlled
source-thread observations, not an installed-device or natural-outage test.

## Final validation

**324/324 tests pass = 196 desktop CI-selected + 91 cache/integrity + 37
additional**, in 28 isolated module processes; zero failures/errors/skips.
This includes prior count/grid/calendar/date, submitted-filter/booking-context,
empty/error/offline and live-recovery repairs, plus safe alert-bundle integrity.
The unchanged 11-method lifecycle module ran once today without paired Linux
timeout diagnosis or test relaxation. The aggregate passed on its first run.

Separate final diagnostics pass: **50 filter combinations, five startup
decisions, 14 course-count states with six compatibility journeys/seven search
decisions, and four grid/show-all/intercepted-booking controls**. They reverify
PR27/28 and earlier repairs without adding overlapping observations to unit
counts. Compact before/after views were inspected: the stuck progress state
becomes explicit cache-unavailable guidance, or truthful partial-date coverage.
Existing date-punctuation corruption remains tracked for canonical integration.

Final aggregate and static evidence are in [validation/summary.json](validation/summary.json),
[run-focused.py](run-focused.py) and [static-checks.json](static-checks.json).
The final source hash is
`09b17e1a6a89a164d96ed6fc82413d0fa9f64d37244736b225a1150a12736ca1`;
the final multi-day test hash is
`a96fb70c52423e64ac89bf76076fc729f7b980c17f0eefa17f0cfea2b760289c`.
Precommit logs identify baseline HEAD plus these modified-file hashes. The
published draft records the resulting commit, remote verification, merge-tree
comparison and all exact-head workflow events/attempts through terminal results.

Compile, CRLF-aware whitespace and actionlint 1.7.12 pass. Independent source
review confirms the signal remains outside the exception guard, ordinary
per-future failure handling is unchanged, and no existing test/fixture,
workflow or lifecycle behavior was edited. See [review](review.md) and
[review metadata](review-metadata.json).

## Bounded published-data observation

At **08:52:26 Perth**, the [one-payload sample](published-sample.json) was pinned
to cache `4f911bb95c45626e0ddce07132310005345439b7`. Commit/index generation time
was 08:47:19; Nov12/18 payload generation was 08:46:19 (6m07 old). The sampled
body contains 37 course records and 159 cached rows, zero truthy errors, stale
flags or defined false-zero weather signatures. The index declares 56 payloads
for Nov12–Dec9; no other payload bodies or all-file presence were audited.

Source cron offers nominal ten-minute opportunities at UTC minutes
7/17/27/37/47/57. This observation does not prove successive publication cadence,
trigger origin, provider-observation age, full-range health, weather accuracy
or exact tee-time bookability. Existing weather/Wembley drafts remain unmerged;
the hourly health watch was not repeated.

## Failed history and unperformed checks

Expected baseline failures remain preserved. The candidate focused and aggregate
tests passed first attempt, with no regression-fixture correction. Initial
diagnostic processes also exited successfully, but visual inspection found the
real-QThread queued-success screenshot was captured before Qt completed layout.
The original evidence remains intact; a separate capture-only settling replay
addresses that observation without changing product code or test assertions.
This is diagnostic timing, not a newly claimed product defect.
One trailing space in a unittest subtest header was removed from the readable
baseline log for whitespace checks; the byte-exact original is retained in gzip
with [hashes and formatting details](regression/log-formatting.json). No test
result was changed or rerun for formatting. Earlier [PR27 initial sparse-grid failures](../2026-11-07-responsive-grid/REPORT.md)
and prior fixture/failed executions remain in their dated reports. The
[historical Windows cache_close failure](../2026-10-21-midnight/ci-followup/REPORT.md)
had 76 passes and one 30-second timeout; later green checks and 40 Linux
non-reproductions did not establish its cause or a fix. Today's deterministic
exception guard does not diagnose or resolve that historical timeout, native
shutdown hangs or the separate Qt manual-pump stall. Existing lifecycle tests
retain their original assertions and limits.

This is source/offscreen Qt testing in the authorized Linux executor. A hosted
Windows source-test run is also distinct from installed Windows UI. No native
Windows/Android app, real provider outage, live booking/hold, screen reader,
touch/DPI/resume, updater/signature or notification runtime/delivery was tested.
Offline alert-bundle integrity does not execute the worker. Canonical desktop/
mobile/runtime source reconciliation and release-candidate integration remain
open; this draft is not a shipped fix. No redesign or product direction changed.

The prior production-history read of
`actions/workflows/refresh-cache-10min.yml/runs?per_page=5` remains **denied** by
the connector allow-list (HTTP 400 INVALID_ARGUMENT). It was not retried or
routed around. Source schedule and bounded publication reads completed
independently. No merge, deployment, release, production dispatch, credential/
security change, spend, outreach, real booking or notification occurred.
