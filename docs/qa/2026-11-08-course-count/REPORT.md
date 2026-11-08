# Course-selection count visibility — 8 November 2026 (Perth)

Closing the course panel hides both selection-count displays on exact PR27: its
button becomes `CHOOSE COURSES` and the separate count label is hidden. The
button now retains the existing `COURSES N OF 41` wording. This is a small P3
information-visibility repair: selection data and search decisions were already
correct. No new count format, layout, booking action or filtering rule is added.

## Baseline, scope and provenance

- Exact baseline: PR27 `405cbec95ed5b9fc84e23dba9fb64a7df98a29bf` on
  `fix/desktop-responsive-grid-20261107`.
- Repair branch: `fix/desktop-course-count-20261108`, stacked on that unchanged
  base in an isolated worktree. Earlier dirty work and repair worktrees remain
  preserved.
- [Repository audit](context-audit.json): 31 branches, 25 open drafts (#3–27),
  zero non-PR issues, 29 source refs plus loose source, and both update
  repositories inspected. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`;
  public Android 0.1.19 and Windows 5.1.17 metadata are unchanged. Update source
  trees are README-only. No applicable AGENTS.md or checkout .agents/skills was
  found. Candidate methods match across those source refs; this does not
  duplicate PR11's separate selection-signal repair.
- [Workflow trigger audit](workflow-trigger-audit.json): all five workflows
  inspected. Normal repair push/PR events select desktop/cache tests only;
  production refresh/news require other eligible events, and alerts are manual.
  All workflow files remain byte-identical to PR27. No manual dispatch is used.
- Final app SHA256:
  `cc56759453ab2b4f1793d44571f1e5d62b69fc251a9efa75d01911dcc7d13339`.
  Final course-control test SHA256:
  `6198a2434f3121d26b89e2ba0dd30177f2834504f940826460316a4cb4bbd6de`.
  Precommit evidence records the baseline HEAD plus these changed-file hashes;
  the published draft records the resulting commit, remote verification and CI.

## Reproduction and focused change

The identical actual-input probe records 14 states before and after. Seven
closures lose their count on PR27, including many, zero and one selected course,
selected courses hidden by a name query, a query with no visible matches, and
9/18-hole selections. Those seven closures now retain their count: **missing
count states 7 → 0**. Initial collapsed state and round changes while collapsed
already showed counts and remain correct. Opening still says `HIDE COURSES`.

| Example after closing | Exact PR27 | Repair |
| --- | --- | --- |
| Zero selected | CHOOSE COURSES | COURSES 0 OF 41 |
| One selected | CHOOSE COURSES | COURSES 1 OF 41 |
| Two selected, one hidden by search | CHOOSE COURSES | COURSES 2 OF 41 |

Only `GolfHub.toggle_courses` changes: its closing branch calls the existing
`update_selected_count`. The other 107 function ASTs, existing eight test
methods/fixtures, course configuration, core/cache/booking code, lifecycle
tests, workflows and alert ZIP/manifest remain unchanged. The four added test
methods cover mouse/Space close and reopen, hidden selections and actual Qt
accessible Name, eligible counts across round changes, and submitted sites/
zero-selection guard. The existing workflow already selects this test module.

[Before JSON](before/probe.json), [after JSON](after/probe.json),
[before zero image](before/zero-closed.png), [after zero image](after/zero-closed.png),
[before one image](before/one-closed.png), [after one image](after/one-closed.png).
Compact screenshots were visually inspected. They show the restored count
without geometry changes. Existing date-punctuation corruption is separately
tracked in the cumulative backlog; it is not a new fix here.

Six compatibility journeys and seven intercepted search decisions are unchanged
on both sources: six nonempty submissions and one no-course guard. Hidden
selected courses remain submitted; 9/18 eligibility remains correct. This
evidence does not establish booking success or a speed improvement.

## Validation and execution history

| Coverage | Result |
| --- | --- |
| Identical final 12-method course module on exact PR27 | **Expected failure:** eight existing methods pass, four new methods fail; seven assertion records including subcases; zero errors/skips |
| Same module on final source | **12/12 pass**, zero failures/errors/skips |
| Final aggregate | **316/316 pass = 188 desktop CI-selected + 91 cache/integrity + 37 additional**, 28 isolated module processes; zero failures/errors/skips |
| Separate final diagnostics | **50/50** filter combinations, **5/5** startup decisions, **4/4** prior grid controls; 683px narrowed grid remains 337/336/0 |
| Compile, CRLF-aware whitespace, actionlint 1.7.12 | Pass |
| Independent source/evidence review | No blockers; only intended method changes |

Evidence: [baseline regression](regression/baseline.json) and
[failure log](regression/baseline.log), [final regression](regression/after.json),
[aggregate and per-module logs](validation/summary.json),
[runner](run-focused.py), [static checks](static-checks.json),
[independent review](review.md), [review hashes](review-metadata.json),
[journey scope](journey-scope.md), [diagnostic summary](diagnostic-summary.json).
Diagnostic observations are not added to the unit-test total. Aggregate modules
recheck prior calendar/date, filter/count, cache/empty/error/offline, recovery,
booking-context, responsive-grid and safe offline bundle-integrity repairs.
The unchanged 11-method lifecycle module ran once today; no paired Linux
reinvestigation or timeout/assertion relaxation occurred.

Today's candidate regression and aggregate passed on their first executions;
there was no intermediate candidate regression or fixture correction. Original
baseline failures remain intact. A guessed test filename lookup missed before
file discovery found the correct module; absent instruction searches also
returned no matches. These were read-only lookup results, not runtime failures
or access denials.

Earlier failures remain material: the [7 November initial candidate](../2026-11-07-responsive-grid/REPORT.md)
passed six/310 tests before independent review exposed two failing sparse-grid
methods (three assertion records); the final PR27 correction and its broader
tests are retained. Earlier fixture corrections and failed executions remain in
their dated reports. The historical [Windows cache_close timeout](../2026-10-21-midnight/ci-followup/REPORT.md)
had 76 passing tests and one 30-second timeout. Later green checks and 40 Linux
non-reproductions did not establish a cause or fix. Same-source Windows evidence
and failing-child stack diagnosis remain pending.

## Bounded publication observation

The [single-payload sample](published-sample.json) was pinned to cache commit
`a29b423a9b7de436f3b1244c227eedbcbefed4d1`, observed at **08:50:26 Perth**.
Commit/index timestamps were 08:46:58/08:46:57; the Nov8/18 payload was generated
08:46:17 (4m09 old). Its 37 course records contain 67 cached rows, no truthy
errors, no stale flags and no defined false-zero weather signatures. The index
declares 56 payloads for Nov8–Dec5; only one payload body was sampled.

Source cron offers nominal ten-minute opportunities at UTC minutes
7/17/27/37/47/57. This sample does not prove actual cadence, trigger origin,
per-course observation age, full-range health, weather accuracy or live booking
availability. Existing weather/Wembley repairs remain unmerged. The hourly
watch was not repeated.

## Unperformed checks, decisions and access limits

Local execution is Linux Python 3.12.14 / Qt 6.11.2 offscreen source-widget
testing, with isolated temporary paths, blocked external calls and intercepted
browser/worker actions in diagnostics. Qt accessible Name inspection is not a
native screen-reader announcement test. CI source tests on a Windows runner
also do not establish installed-app behavior.

No installed/native Windows or Android, real provider/outage behavior, live
booking/holds, notification runtime/delivery, native screen readers, touch/DPI/
resume, updater or signature tests were performed. Offline alert-bundle
integrity checks never execute the worker. Canonical desktop/mobile/runtime
source reconciliation and release-candidate integration remain pending; the
draft stack is not a shipped fix. Substantial product/release decisions remain
with the user.

The previously denied production-history read of
`actions/workflows/refresh-cache-10min.yml/runs?per_page=5` remains unavailable:
connector HTTP 400 INVALID_ARGUMENT, endpoint outside its allow-list. It was
not retried or routed around. Source schedule inspection and the bounded
published-cache sample completed independently. No new denied, uncertain or
pending write occurred during local work. Repair publication/CI status is
recorded on the draft after verifying the remote head and every exact-head
workflow event/attempt. No merge, deployment, release, production dispatch,
security/credential change, spend, third-party outreach or live booking occurred.
