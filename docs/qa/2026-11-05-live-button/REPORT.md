# Refresh Live availability and disabled styling — 5 November 2026, Perth

Changing from one date to several dates during a live request correctly disabled Refresh Live, but success, failure or cancellation re-enabled it even though multi-date live refresh is unsupported. It also became enabled while the old worker was still owned or the window was closing, when clicks were ignored. The repair keeps the action consistent with pending dates and request ownership, then restores single-date retry after cleanup. A related one-selector correction restores the app's existing disabled text color, which the OutlineButton style had overridden.

## Inspection and scope

Branch `fix/desktop-live-button-state-20261105` starts from unchanged draft [#24](https://github.com/Jarryd22/golfhub-perth/pull/24), `53cbfd463af717b3e1e7670af1911e0cd11c4714`. Before implementation, the [audit](context-audit.json) inspected 28 branches, 22 drafts #3–24, 26 non-data source refs, existing repair tasks/reports/checklist/backlog and both update repositories. All source refs and the preserved loose source had the button mismatch; PR24 repairs recovery wording, not action eligibility. The [style duplicate audit](style-duplicate-audit.json) also found no explicit disabled OutlineButton selector in those 26 refs or the loose checkout. No applicable AGENTS.md or checkout skills were found. The saved executor resumed successfully; original dirty work and prior worktrees are preserved.

Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`. Update repository metadata remains Windows 5.1.17 / Android 0.1.19. This candidate is remote desktop v5.0 source; canonical desktop/mobile/service reconciliation remains pending.

Five existing methods change: `update_day_mode`, `scan_finished`, `scan_failed`, `scan_thread_done` and `styles`. The live-button predicate now requires one date, no owned scan/cache request and a window that is not closing. Completion handlers recompute this state, and cleanup recomputes it after releasing references. The existing disabled rule also explicitly targets OutlineButton, retaining all its existing palette values. [Source comparison](journey-source-scope.json) confirms identical workers, unchanged cleanup mechanics apart from the UI update call, and unchanged provider/cache/booking/production code. No new request, retry, timer or ownership mechanism is introduced.

## Before and after

[Detailed evidence](EVIDENCE_NOTE.md), [baseline six cases](before/six-cases/probe.json), [final six cases](after/probe.json). Real source controls, QObject signals and callbacks are exercised with inert thread stand-ins; network, providers, weather, booking and persistence are blocked or intercepted. These are controller-state reproductions, not native worker-timing investigations.

| State | Exact PR24 | Repair |
|---|---|---|
| Success/failure/cancel, pending multi-date selection after cleanup | Enabled in 3/3 cases; click overwrites status with a restriction | Disabled in 3/3; status remains intact |
| Terminal signal while old worker is retained | Enabled in 6/6 cases; click silently ignored | Disabled in 6/6 |
| Simulated unfinished cleanup, followed by date edits | Enabled in 6/6 despite retained ownership | Disabled in 6/6 |
| Cleanup complete with one pending date | New click starts the current selection | Same usable retry in 3/3 |
| Closing window receives cancelled completion | Live action is re-enabled but ignored | Remains disabled |
| Disabled OutlineButton appearance | Text remains enabled color `#f6f6f6` | Existing disabled color `#7d7d7d`; enabled text still `#f6f6f6` |

The palette issue was confirmed through actual Qt palette values and a plain disabled-button reference, then reproduced on exact PR24 with the final test file. [Palette before](before/palette/palette-probe.json), [palette after](after/palette/palette-probe.json). Before/after 1280×800 state images and [980×640 disabled appearance](after/palette/compact-disabled.png) were inspected. The compact button stays fully inside the window at the same position/size; no new layout or colors were introduced. Screenshots alone did not prove eligibility before the selector correction, so state assertions and intercepted clicks remain the functional evidence.

## Verification

Local execution: Linux, Python 3.12.14, PySide6/Qt 6.11.2, offscreen scale 1, isolated writable paths, fixed Perth date 2 January 2033. Pre-commit records identify the parent separately from the tested changed-file hashes.

| Evidence class | Result |
|---|---|
| **Failed exact-baseline regressions** | Identical final ten-method file on clean PR24: **1 passed / 9 failed**, zero errors/skips. [Metadata](new-tests-baseline.json), [log](new-tests-baseline.log). |
| **Passed final regressions** | **10/10**: all completion outcomes, single-date retry, retained cleanup ownership, date changes, overlapping cache request, submitted save/display context, closing and actual disabled palette/restoration. [Metadata](new-tests-after.json), [log](new-tests-after.log). |
| **Passed final aggregate** | **297/297 = 169 desktop CI-selected + 91 cache/integrity + 37 additional booking/rendering**, zero failures/errors/skips, 26 fresh module processes. [Summary/hashes](validation/summary.json), [runner](run-focused.py). PR16–24 and prior date/filter/booking guards revalidated. |
| **Separate diagnostics** | **50/50 filters**, **5/5 startup decisions**, six state scenarios, closing and palette probes, zero callbacks. [Journey review](journey-scope.md). Four earlier keyboard scenarios passed on unchanged PR24 and found no new defect; they are not final-code regression counts. |
| **Static and independent review** | Compile, CRLF-aware whitespace and pinned/checksum-verified actionlint 1.7.12 pass; [static checks](static-checks.json). [Independent review](review.md) confirms the focused scope and retained safeguards. |
| **Not performed** | Installed/native Windows or Android UI; real provider/network recovery; live bookings/holds; touch, screen readers, DPI/resume; updater/signatures; alert worker execution or notification delivery. |

Final app SHA-256: `addf599e372aa821069385621f73e85d1e681de4760298634ebacf634d9263db`. New test SHA-256: `295ba855ed1d0f63df2752993a9be179506a6be09aa0957b77b97d8e89aac16a`. Final remote head, all CI events/attempts and checkout/merge-tree equality are recorded on the draft after publication. Windows CI is offscreen source testing, not installed-client validation.

## Bounded publication sample

One [immutable publication sample](published-sample.json) pinned cache `22ea07d7909a916bd81da7de40db1f69ad4f23ce`. At **08:09:26 Perth**, commit/index time **07:56:57** was **12m29s old**; sampled payloads were 12m50s–13m10s old. This exceeded the nominal ten-minute interval at that observation. Source schedule declares UTC minutes 7/17/27/37/47/57 and explicitly does not guarantee cadence. One publication does not establish the actual interval, pipeline latency or a workflow failure; no workflow-success inference is used.

All **56 expected paths**, November 5–December 2, were present; only **three bodies / 111 records** were inspected. They contained two known Wembley configured-product errors (November 20/18 holes and December 2/9 holes), no sampled stale flags, 74 weather objects without an all-zero Clear signature and 37 null weather values. This is not a full-cache audit, per-course freshness proof, verified bookability or a claim that draft PR8 is fixed. The hourly watch was not repeated.

## Retained executions, limits and decisions

- The initial state-only stage passed nine regressions and [296 aggregate tests](pre-style/validation/summary.json). Visual review then reproduced the separate selector-specificity defect. The original test/source/probe evidence remains under `pre-style`; final ten-test baseline/repair runs, aggregate and 50+5 diagnostics were run after the selector change. Earlier executions are not added to final totals. No repaired test failed, fixture correction or assertion relaxation was needed in this pass.
- PR24 recovery tests now assert disabled before cleanup and explicitly enabled afterward in both retry journeys. The lifecycle module and its 30-second timeout are byte-identical to PR24. The standard eleven lifecycle tests ran once per aggregate, twice total because the final source changed; there was no paired Linux timeout investigation or retry cohort.
- The staged whitespace check flagged a trailing blank line in the newly archived state-only source copy. That historical source is now stored as a deterministic gzip with its original bytes/hash verified; the final staged check passes. Runtime source and test expectations did not change.
- A reviewer-only metadata read initially assumed an object where the JSON held a list; the corrected read succeeded. It changed no source/test and was not a runtime test failure. Existing font-cache/cursor warnings remain distinct from callback errors.
- **Historical Windows `cache_close` remains unresolved:** PR14's [failed push](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and timed out one child. Later green checks and 40 Linux non-reproductions do not establish cause or repair. Exact-source Windows comparison and a failing-child stack remain **pending/unavailable**, not denied. [Authoritative report](../2026-10-21-midnight/ci-followup/REPORT.md).
- The previously denied production workflow-history request at `actions/workflows/refresh-cache-10min.yml/runs?per_page=5` was **not repeated or routed around**. Actual production run timing remains unverified. Permitted source schedule/publication inspection and repository audit completed. No new denied or uncertain action occurred.
- Earlier Qt event-pump stalls, WebEngine sandbox-helper blocks, obsolete cron assertion, fixture-write denials and dated fixture/tooling failures remain documented, including November 4's corrected helper-shadowing error. No sandbox, provider-access denial or test safeguard was bypassed.
- Canonical-source, per-course freshness/subset and alert-runtime reconciliation remain pending. PR3 is Quick18-specific; Wembley #5/7 and weather #4→#6→#8 remain separate/unmerged. The 91 cache/integrity tests include inert alert-bundle checks; no runtime or delivery is proven.

The supported usability improvement is consistent action availability and restoration of its intended visual state. No golfer feedback, native accessibility success or speed improvement is invented. Broader onboarding, submitted-filter summaries, freshness presentation, redesign and monetization remain review decisions.

No merge, deploy, release, production/manual workflow dispatch, credentials/security change, spending, outreach, live booking/hold or real notification occurred.
