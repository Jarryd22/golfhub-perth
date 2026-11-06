# Empty-result link guidance — 6 November 2026, Perth

A successful search containing only integrated courses could show no matching tee times and no booking actions, yet tell golfers that official course links were available below. The repair includes that sentence only when selected direct-course cards will actually be displayed. Existing filter/refresh advice, cards, destinations and search behavior are preserved.

Branch `fix/desktop-empty-link-guidance-20261106` starts from unchanged draft [#25](https://github.com/Jarryd22/golfhub-perth/pull/25), `0d09ee3dbbb16b8a2a53851b532e6e59b7c16269`. This is remote desktop v5.0 source, not the installed Windows/Android release candidate.

## Inspection and reproduction

The [context audit](context-audit.json) inspected 29 remote branches, all 23 drafts #3–25, prior reports/checklist/backlog, repair tasks and both update repositories before implementation. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`; public metadata remains Windows 5.1.17 / Android 0.1.19. All 27 immutable source refs and the preserved loose checkout have the unconditional sentence. Existing cache/error/multi-date-link/recovery repairs address different paths. No applicable AGENTS.md or checkout skills were found. Original dirty work and previous worktrees remain preserved.

The [unchanged baseline probe](before/probe.json) submits real configured Araluen/Altone selections through source controls and the actual cache-completion renderer, using synthetic successful observations. Provider/network/weather/browser/save calls and worker construction are blocked. It is a Linux offscreen reproduction, not a live-provider observation.

| Scenario | Exact PR25 | Repair |
|---|---|---|
| Araluen 09:00, two spaces; submitted four players | Zero rows/cards/actions, but promises official links below | Zero actions; existing filter/refresh advice without the false sentence |
| Araluen successful empty response | Same false promise with no action | Same truthful recovery guidance |
| Araluen excluded plus selected Altone | One official action and link sentence | Both retained |
| Araluen with one player | One matching row and booking actions, no empty state | Unchanged |

[After probe](after/probe.json), [before image](before/integrated_group_exclusion.png), [after image](after/integrated_group_exclusion.png). Four cases were rerun once using the identical probe script. Compact 980×640 images were inspected. Mixed-selection direct cards remain below the initial viewport and require scrolling; that existing layout is unchanged. No native-device or broad layout claim follows from these images.

## Change and verification

Only `GolfHub.render_results` changes at the function-AST level: a conditional suffix uses `direct_results`, the same collection that immediately governs official-card construction. The desktop test workflow adds the new module to both path filters and its existing isolated-process list. [Independent review](review.md), [reviewed hashes](golfhub-20261106-review-metadata.json) and [journey scope](journey-scope.md) found no blocking issue. Providers, cache, booking, workers, lifecycle tests, production workflows and alert archive/manifest are unchanged.

Local execution used Linux, Python 3.12.14 / Qt 6.11.2, offscreen scale 1 and isolated writable directories. Pre-commit records distinguish parent HEAD from tested changed-file hashes.

| Evidence class | Actual result |
|---|---|
| **Failed final baseline** | Identical final seven-method test file on exact PR25: **3 passed / 4 failed methods**, **5 assertion records** because group/time subcases both fail; zero errors/skips. [Metadata](regression/baseline.json), [log](regression/baseline.log). |
| **Passed focused regression** | **7/7**, zero failures/errors/skips. Covers group/time exclusion, checked-empty, mixed/direct-only, unselected direct records, replacing mixed results, positive/error cards and intercepted configured URL handoff. [Metadata](regression/after.json), [log](regression/after.log). |
| **Passed final aggregate** | **304/304 = 176 desktop CI-selected + 91 cache/integrity + 37 additional booking/rendering**, 27 fresh module processes; zero failures/errors/skips. [Summary](validation/summary.json), [runner](run-focused.py). |
| **Separate final diagnostics** | **4/4** configured rendering cases, **50/50** filter combinations, **5/5** startup/fallback decisions; zero callback exceptions. [Diagnostic summary](diagnostic-summary.json). These are not added to unit-test totals. |
| **Earlier diagnostic** | **9/9** secondary mouse-input checks on unchanged PR25; no uncovered input bug. [Evidence](secondary-input/probe.json). Not final-code regression counts. |
| **Static/source review** | Compile, CRLF-aware whitespace and retained pinned actionlint 1.7.12 pass. [Static record](static-checks.json). One changed function; no new request/timer/retry mechanism or benchmark claim. |
| **Not performed** | Installed/native Windows or Android UI, real provider/outage recovery, live booking/holds, touch/screen reader/DPI/resume, updater/signatures, alert runtime or notification delivery. |

Final application SHA-256: `f6e948cfe9460e861365e8bca23d48102843bd30c12bb513e2c725370bdb39e6`. New regression SHA-256: `ee804b56a7fe4dd2e193b54652bd90455bd4b0858d735f2bb547b60b85d3463b`. Remote commit, all exact-head CI events/attempts and merge-tree equality are recorded on the draft after publication. Windows CI is offscreen source testing, not installed-client validation.

## Bounded published-data comparison

One [immutable sample](published-sample.json) pinned cache `5906a4f088f990e9808cfb668de784d86ff4fa98`. At **08:56:19 Perth**, its commit was **08:47:09**, age **9m10s**; sampled payloads were 9m31s–9m51s old. Main source declares UTC minutes 7/17/27/37/47/57 and does not guarantee execution cadence. One publication cannot establish actual successive cadence, pipeline latency or per-course observation freshness.

All 56 expected paths for November 6–December 3 were present; only **three bodies / 111 records** were inspected. They contain two known Wembley configured-product errors, zero sampled stale flags, 74 weather objects without an all-zero Clear signature and 37 null values. November 21/18 currently has populated weather in this sample; that does not establish the recurrent defect fixed or PR8 deployed. No whole-cache audit, exact bookability or notification conclusion is made. The parent's hourly watch was not repeated.

## Retained failures, blockers and decisions

- Two regression-fixture corrections preceded the final baseline: the first omitted an explicit date matching the synthetic payload, triggering blocked live fallback (**six failed methods / seven assertion records**); the second expected a bare domain rather than the existing HTTPS destination (**five failed methods / six assertion records**). [Initial log](regression/initial-baseline.log), [initial test](regression/initial-test.py), [date-corrected log](regression/date-corrected-baseline.log), [date-corrected test](regression/date-corrected-test.py). Both remain intact. After correcting fixture setup/expectation, the final baseline fails only on false link guidance. No production workaround or assertion relaxation was made.
- Initial executor source reads disconnected and one read-only session could not be recovered. The same authorized environment recovered before implementation; no uncertain write was retried. A diagnostic read before its pending process completed found no output file; the process completed once and its evidence was then read. Missing guessed source paths and absent instruction-directory reads were lookup errors, not test failures or access denials. No new unresolved executor blocker remains.
- **Historical Windows `cache_close` remains unresolved.** PR14's [failed push](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and timed out one child at 30 seconds. Later green checks and 40 Linux non-reproductions do not establish cause or repair. Exact-source Windows comparison and a failing-child stack remain pending/unavailable. [Authoritative report](../2026-10-21-midnight/ci-followup/REPORT.md). The unchanged eleven lifecycle tests ran once in today's standard aggregate; no paired Linux diagnosis or timeout change occurred.
- The previously **denied** production workflow-history lookup at `actions/workflows/refresh-cache-10min.yml/runs?per_page=5` remains restricted by the connector allow-list (HTTP400 INVALID_ARGUMENT). It was not repeated or routed around. Source schedule/publication checks completed; actual production run history remains unverified. This historical connector denial is separate from today's recovered transport interruption.
- Earlier Qt event-pump stalls, WebEngine sandbox-helper blocks, obsolete cron assertion, fixture-write denials and dated tooling failures remain in the cumulative reports. No sandbox or provider-access restriction was bypassed.
- Canonical-source/release-candidate reconciliation, freshness/subset integration and native validation remain pending. PR3 is Quick18-specific; Wembley #5/7 and weather #4→#6→#8 remain separate/unmerged. The 91 cache/integrity tests include inert alert-bundle checks and do not execute its runtime or prove delivery.

The supported improvement is truthful recovery guidance. No golfer feedback, speed gain or native accessibility result is invented. Broader onboarding, submitted-filter summaries, freshness presentation, redesign and monetization remain product/reconciliation decisions. No merge, deploy, release, production/manual dispatch, security/credential change, spending, outreach, live booking/hold or real notification occurred.
