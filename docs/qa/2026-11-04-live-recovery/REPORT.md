# Live-refresh recovery states — 4 November 2026, Perth

A cold live refresh could fail with no results on screen, yet claim that cached results were preserved and leave **Checking courses live...** visible. Stopping before the first result also claimed a preserved cache. Removing an earlier results view left its metadata behind, allowing the same false retained-results decision later. The repair distinguishes results actually retained on screen from a search with none, replaces the unfinished checking message with recovery guidance, and clears metadata when its cards are removed.

## Scope and baseline

Branch `fix/desktop-live-recovery-20261104` starts from unchanged draft [#23](https://github.com/Jarryd22/golfhub-perth/pull/23), `50ae64a00b4372d1f8c33dd787c2d5406510da2e`. The [context audit](context-audit.json) inspected 27 branches, 21 drafts #3–23, all 25 non-data source refs, existing reports/checklist/backlog and both update repositories before implementation. All 25 refs and the preserved loose checkout had identical target methods and no metadata reset. This is the worker-wide failed/stop path; PR18's per-course error cards, PR21's exception serialization and PR23's missing multi-date links remain separate repairs.

Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`; public release metadata remains Windows 5.1.17 / Android 0.1.19. The saved Linux executor resumed after startup; no tests or changes ran while it was starting. No applicable AGENTS.md or checkout skills were found. Original dirty source and all prior worktrees are preserved. Canonical newer desktop/mobile/service source remains unresolved.

Only three existing application methods change: `scan_failed`, the cancelled branch of `scan_finished`, and `clear_results`. Clearing assigns new empty lists; it does not mutate caller-owned result lists. Normal successful save/rendering, captured booking context, worker ownership, request/retry policy, provider logic and production workflows are unchanged. Existing lifecycle assertions now distinguish their cold fixture from retained results and add absence/recovery assertions; their 30-second timeout and thread checks are unchanged.

## Reproduction and resulting behavior

The exact-PR23 diagnostic follows real `cache_finished({})` → `search_live`, then runs the actual `ScanWorker.run` synchronously with an injected executor-setup exception. Its real failed signal reaches the UI. Native QThread startup/move, browser/dialogs and persistence are intercepted; sockets, DNS and provider calls are blocked. The cache is a real empty temporary directory. This proves the response to a worker-wide failure, not its frequency in production or a native lifecycle diagnosis.

| State | Exact PR23 | Repair |
|---|---|---|
| Cold failure, no results | Body remains “Checking courses live...”; status, header and modal claim cached results were kept | Header says “LIVE REFRESH FAILED”; body explains that results could not load and offers Find Tee Times / Refresh Live |
| Stop before first result | Header says “CACHE PRESERVED” despite no results | Header says “REFRESH STOPPED”; body explains that no results were available and offers retry actions |
| Previous view removed for a new cache search | Invisible old results remain in metadata | Removed results and date sections no longer count as retained |
| Genuine retained results during failure/stop | Cards remain, but wording assumes they were cached | Same cards and submitted booking/lazy context remain; wording says previous results were kept |
| Successful retry/replacement | Existing successful save/render path | Unchanged; current results become the displayed state |

The change uses existing controls, layout and styling. It adds no request, eager date rendering or automatic retry. No native speed improvement, benchmark or user feedback is claimed. Broader onboarding, freshness clarity, redesign and monetization remain review decisions.

## Verification

Local execution used Linux, Python 3.12.14 and PySide6/Qt 6.11.2, offscreen scale 1, fixed Perth date 2 January 2033, isolated writable data paths and blocked/intercepted network/browser/worker boundaries. The source identifies as desktop v5.0, distinct from public release versions.

| Evidence class | Result |
|---|---|
| **Failed exact-baseline regressions** | Final identical 11-method file on clean PR23: **2 pass / 9 fail**, ten assertion/subtest failure records, zero errors/skips. [Metadata](new-tests-baseline.json), [log](new-tests-baseline.log). |
| **Passed repaired regressions** | **11/11**: cold first-launch failure, cold stop, old multi-date view cleared before either outcome, actual saved-card/file/context retention, lazy dates, PR23 static link, cancelled partial results, successful retry, repeated failure, aliased rendering input and closing guard. [Metadata](new-tests-after.json), [log](new-tests-after.log), [method and fixture details](EVIDENCE_NOTE.md). |
| **Passed aggregate** | **287/287 = 159 desktop CI-selected + 91 cache/integrity + 37 additional booking/rendering**, zero failures/errors/skips, 25 fresh module processes. [Summary/hashes](validation/summary.json), [runner](run-focused.py). PR16–23 and earlier calendar/filter/booking guards revalidated; the standard 11-test lifecycle module ran once. |
| **Separate diagnostics** | **50/50 filter combinations**, **5/5 startup decisions**, zero callbacks; [journey review](journey-scope.md). Cold worker-failure probes before/after and compact recovery geometry are separate diagnostic executions, not additional unit-test counts. |
| **Static/source review** | Python compile, CRLF-aware whitespace and checksum-verified actionlint 1.7.12 pass; [static checks](static-checks.json). [Independent review](review.md) and [source scope](journey-source-scope.json) verify three changed methods and unchanged provider/cache/booking/production behavior. |
| **Not performed** | Installed/native Windows/Android UI; live providers, bookings/holds, updater/signatures or notification delivery; touch/screen readers/DPI/resume. |

[Before](before/cold-failure-probe.json) and [after](after/cold-failure-probe.json) capture the actual failed signal and zero callback errors. The [before image](before/cold-failure.png) and [after image](after/cold-failure.png) were visually inspected at 1280×800. A separate [980×640 cold-failure diagnostic](after-compact/cold-failure-probe.json) confirms the recovery note is visible and both enabled retry controls are inside the window; [compact image](after-compact/cold-failure.png) was inspected. The existing missing-date compact image belongs to the filter diagnostics, not this cold-failure probe.

Application SHA-256 `fc61c95941605ba2bb79608fdf619d988ca9e3037f595377b353c10be3bfbfc3`; regression SHA-256 `f443f88c94d698488af3ce9cef8c1a899a2aee10c41d936a002662afb60d74ae`. Pre-commit metadata names PR23 as parent and records the tested changed-file hashes separately. Final remote head, all CI events/attempts and checkout/merge-tree equality are recorded on the draft after publication; Windows CI is offscreen source testing, not an installed-client test.

## Bounded published-data check

One [immutable publication sample](published-sample.json) checked cache `2448716441db82515d8f24f762d1c1b950baf50d`. Commit/index time was **08:46:56 Perth**, four minutes old at the initial 08:50:56 check. All 56 expected date/round paths for November 4–December 1 were present. Only **three payload bodies / 111 records** were inspected: two known Wembley configured-product errors (November 19/18 holes and December 1/9 holes), zero sampled stale rows, 74 weather objects without an all-zero Clear signature and 37 null weather values. This is not a whole-cache health assertion, verified tee-time bookability or evidence that PR8 is fixed.

The workflow source declares ten-minute cadence at UTC minutes 7/17/27/37/47/57 and explicitly does not guarantee that cadence. Sample payloads were roughly four minutes old; one fresh publication does not prove successive delivery, run latency or per-course observation freshness. No production dispatch or provider access occurred.

## Failures, limits and blockers

- The initial test helper was named `fail`, shadowing `unittest.TestCase.fail`; the [initial baseline execution](new-tests-baseline-initial.json) therefore recorded four failure records and six fixture errors. Its [test file](initial-fixture/test_live_recovery_states.py) and logs are retained. Renaming the helper and isolating failure/stop subtest cleanup produced the final identical-file baseline above. The initial repaired execution passed 11/11; the corrected final file also passes 11/11. No application change or assertion relaxation was needed for this correction. These execution counts are not added to the aggregate total.
- The initial setup command fetched PR23 into `FETCH_HEAD`, then failed to resolve a nonexistent named remote-tracking ref. Its chained worktree creation did not execute. After verifying the fetched SHA, the separate worktree was created from that exact commit. [Setup evidence](setup-evidence.json). No uncertain write remains.
- The optional read of `https://api.github.com/repos/Jarryd22/golfhub-perth/actions/workflows/refresh-cache-10min.yml/runs?per_page=5` was **denied by the connector endpoint allow-list** (`HTTP400 INVALID_ARGUMENT`), known unexecuted. No retry or alternate route was used. Source schedule, immutable publication/index timestamps, repository inventory and sample payload reads completed; production run timing remains unverified. This was a connector restriction, not an automatic approval-review rejection.
- **Historical Windows `cache_close` remains unresolved.** PR14's push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and timed out one child at the unchanged 30-second limit. Later green checks and 40 Linux non-reproductions do not establish cause or repair. Exact-source Windows pairing and a failing-child stack remain **pending/unavailable**, not denied. [Authoritative follow-up](../2026-10-21-midnight/ci-followup/REPORT.md). No repeated Linux diagnosis or timeout relaxation in this pass.
- Earlier Qt event-pump stalls, WebEngine sandbox-helper blocks, obsolete cron assertion, fixture-write denials, interrupted work and dated fixture/tooling failures remain recorded. No sandbox or denial was bypassed. November 3's corrected metadata-checker failure remains in its report.
- **Not performed:** installed/native Windows or Android UI, touch, screen readers, DPI/resume, live provider/network recovery, real URL navigation or booking/holds, updater/signature validation, alert worker execution or notification delivery. Source accessibility and intercepted actions are not device evidence. Alert coverage remains inert bundle integrity; zero-watch runs are not delivery proof.
- Canonical-source, per-course freshness/subset integration and deployed alert-runtime reconciliation remain pending. PR3 is Quick18-specific; PR5/7 and weather #4→#6→#8 remain unmerged. Today's recovery wording does not change persisted data or provider behavior.

No merge, deploy, release, production/manual workflow trigger, credential/security change, spending, third-party contact, live booking/hold or real notification occurred.
