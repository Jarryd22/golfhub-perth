# Responsive card widths — 7 November 2026, Perth

Narrowing an existing results view could leave an unused grid column consuming space. In a configured Araluen reproduction, a 683-pixel grid retained 173 pixels of blank space and squeezed both cards to 250 pixels; creating the same narrow view fresh used 337/336-pixel cards. A two-line repair clears obsolete column stretch while preserving the existing active-column sizing, including sparse grids. This is a **P3 visual-consistency improvement**: booking actions remained usable, and no clipping, speed gain or native-device defect is claimed.

Branch `fix/desktop-responsive-grid-20261107` starts from unchanged draft [#26](https://github.com/Jarryd22/golfhub-perth/pull/26), `2fa359011391f5307aeb60c0f18ba9370190d77f`. It targets remote desktop v5.0 source. Canonical desktop/mobile/release-candidate integration remains pending.

## Inspection and publication scope

The [audit](context-audit.json) inspected 30 branches, all 24 drafts #3–26, existing repair tasks, prior reports/checklist/backlog and both update repositories. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`; public metadata remains Windows 5.1.17 / Android 0.1.19. The entire grid class is identical across 28 immutable source refs and the preserved loose checkout; no existing reset fix or grid-specific test was found. No applicable AGENTS.md or checkout skills were found. Original dirty work and previous worktrees are preserved.

Before publication, the [workflow audit](workflow-trigger-audit.json) checked the actual triggers: a `fix/desktop-*` push selects desktop test CI, and the app-changing draft PR selects desktop/cache test CI. Production cache/news push paths require main; alerts are manual-only; cache `workflow_run` listens to the main alert checker with dispatch-origin guards. Production workflows are unchanged. No workflow was dispatched manually or through another route.

## Before and after

[Baseline probe](pre-review/before/probe.json), [final probe](after/probe.json), [before image](pre-review/before/wide-then-narrow.png), [final image](after/wide-then-narrow.png). The actual source controls render 15 synthetic Araluen rows, expand and collapse them, intercept the fifteenth row's booking URL, then compare a wide→narrow view with a fresh narrow view. Linux Qt offscreen at 1100×800 with the course panel open; no real provider or booking action.

| Observation | Exact PR26 | Final repair |
|---|---|---|
| 683-pixel grid after narrowing, active two columns | Card widths 250/250; unused column 173 | Card widths 337/336; unused column 0 |
| Same view created fresh at narrow size | Card widths 337/336 | Same widths |
| First twelve → show all fifteen → intercepted fifteenth BOOK → collapse | Four checks pass | Four checks pass |
| Sparse one/two-card wide grids | Existing one-third-width sizing | Preserved after review correction |

The repair recovers the 173-pixel unused region (25.3% of this grid width). Images were visually inspected; time/space labels and BOOK actions were readable before and after. No layout redesign, new breakpoint, minimum card size, spacing, palette or interaction change is introduced. A labelled [probe-only reset experiment](pre-review/before/experiment/probe.json) established the cause before the source fix; it is separate from final-source verification.

## Verification and review correction

Only `ResponsiveCardGrid._relayout` changes at the function-AST level. It initializes all computed active columns and resets older inactive ones. The desktop workflow adds the new test module to both path filters and the existing isolated-process list. [Independent review](review.md), [reviewed hashes](review-metadata.json), [journey/source scope](journey-scope.md).

Local execution: Linux, Python 3.12.14 / Qt 6.11.2, offscreen scale 1, isolated writable paths. Pre-commit evidence identifies parent HEAD separately from tested file hashes.

| Evidence class | Actual result |
|---|---|
| **Failed exact baseline** | Identical final eight-method file: **3 pass / 5 fail methods**, ten assertion records including subcases; zero errors/skips. [Metadata](regression/baseline.json), [log](regression/baseline.log). |
| **Passed final regression** | **8/8**: 3→2 and 3→1 columns, tee-time/direct-card minimum sizes, widening, repeated transitions, first-twelve/all visibility, empty restoration and sparse-card sizing. [Metadata](regression/after.json), [log](regression/after.log). |
| **Passed final aggregate** | **312/312 = 184 desktop CI-selected + 91 cache/integrity + 37 additional booking/rendering**, 28 fresh module processes, zero failures/errors/skips. [Summary](validation/summary.json), [runner](run-focused.py). Earlier date/filter/error/offline/booking/lifecycle repairs remain covered. |
| **Separate final diagnostics** | Four configured show-all/booking controls and the resize comparison; 50 filter combinations and five startup/fallback decisions. Counts, source hashes and callback results are in [journey scope](journey-scope.md). Not added to unit-test totals. |
| **Static/source review** | Compile, CRLF-aware whitespace and retained pinned actionlint 1.7.12 pass. [Static record](static-checks.json). Provider/cache/booking/worker and production behavior remain unchanged. |
| **Not performed** | Installed/native Windows or Android, live provider/outage recovery, booking/holds, touch/screen readers/DPI/resume, updater/signatures, alert runtime or notification delivery. |

**The first patch had a real review-found regression and was corrected before publication.** Iterating only existing layout columns failed to initialize computed active columns in sparse grids: at width 1200, one card grew from 400 to 1200 pixels and two cards from 397/396 to 595/595. Its six original tests and [310-test aggregate](pre-review/validation/summary.json) passed because they missed sparse cases. The expanded identical eight-test file then [failed two methods / three assertion records](pre-review/expanded-tests.log) on that initial source. The final loop covers both computed and existing columns; two added regression methods pass on exact PR26 and the corrected source. No assertion was relaxed.

Initial [source/test hashes](pre-review/source-manifest.json), byte-exact compressed source, six-test logs, aggregate and dense-card diagnostics remain under `pre-review`. Archived scripts retain their original execution paths/depth assumptions; use the final dated runners for current reproduction. The final aggregate and diagnostics were rerun after correction, not inferred from initial passes. The reviewer also repeated the same [48-state geometry probe](review-evidence/final-edge.json) on corrected source, covering zero to three cards and one to three maximum columns. The standard unchanged eleven lifecycle tests ran once per aggregate, twice total because source changed; this was not a paired Linux investigation of the historical Windows timeout.

Final application SHA-256: `9b35080c55f9a987ae0ecc204e8be5e23bddf3cb85f9b78af9ba464ef1d1cc0b`. Final test SHA-256: `97f91e4fe215c1e90c5c05578526ea7b4396aeb833091910e9ff5a2249ca965c`. Final remote commit, all exact-head CI events/attempts and checkout/merge-tree equality are recorded on the draft after publication. Windows offscreen CI is source testing, not installed-client validation.

## Bounded publication sample and deferred work

At **08:27:02 Perth**, one [immutable current-date/18-hole sample](published-sample.json) pinned cache `1c68e440edec20e69027030f17ae0edb8f2e7080`. Commit/index time **08:16:55** was **10m07s old**; payload time **08:16:16** was **10m46s old**. Source configures UTC minutes 7/17/27/37/47/57, a nominal ten-minute target. One pinned observation cannot establish actual successive cadence, trigger origin, run latency or per-course observation freshness.

That one body contains **37 course records / 41 cached tee-time rows**, no truthy errors/stale flags and no defined false-zero weather signature. The index declares 56 payloads for November 7–December 4; all-file presence and other payload bodies were not checked. No exact bookability, whole-cache health or repair/deployment conclusion follows. Existing Wembley and weather #4→#6→#8 drafts remain unmerged; the hourly watch was not repeated.

A separate [five-state course-panel probe](pre-review/deferred-course-panel/probe.json) confirmed that closing the panel replaces the visible selected count with CHOOSE COURSES, including zero/one selections. Selection data remains correct. This smaller P3 consistency issue is recorded in the backlog and left unchanged. No fabricated golfer feedback or broad onboarding/product decision is introduced.

## Retained limitations and blockers

- **Historical Windows `cache_close` remains unresolved:** PR14's [failed push](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and timed out one child at 30 seconds. Later green checks and 40 Linux non-reproductions do not establish cause or repair. Exact-source Windows comparison and a failing-child stack remain pending/unavailable. [Authoritative report](../2026-10-21-midnight/ci-followup/REPORT.md). No timeout or lifecycle assertion was weakened.
- The previously **denied** production workflow-history lookup at `actions/workflows/refresh-cache-10min.yml/runs?per_page=5` remains restricted by the connector allow-list (HTTP400 INVALID_ARGUMENT). It was not retried or routed around. Source-trigger/publication checks completed; actual production run history remains unverified.
- Canonical-source/release-candidate, per-course freshness/subset and alert-runtime reconciliation remain pending. The 91 cache/integrity tests include inert ZIP/manifest checks, not worker execution or notification delivery. PR3 remains Quick18-specific, not a Whaleback repair.
- Previous Qt event-pump stalls, WebEngine sandbox-helper blocks, obsolete cron assertion, fixture-write denials, November 6 fixture/tooling failures and recovered executor interruptions remain in the cumulative reports. No restriction was bypassed. Today's lookup of a not-yet-written final diagnostic summary returned file-not-found; it was a read timing issue, not a runtime test failure. Current failed baseline and initial-candidate review regressions are preserved above. The staged whitespace check returned exit 2 for a trailing space in raw unittest subtest output; its [original bytes](pre-review/expanded-tests-original.log.gz) are preserved compressed and the readable log only normalizes trailing whitespace. [Formatting record](evidence-formatting.json); no source, assertion or test outcome changed.

Substantial onboarding, freshness presentation, redesign, monetization and canonical integration remain review decisions. No merge, deployment, release, production/manual dispatch, credentials/security change, spending, outreach, live booking/hold or real notification occurred.
