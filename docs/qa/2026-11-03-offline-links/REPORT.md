# Official course links without cached dates — 3 November 2026, Perth

When every selected date lacked a shared or saved snapshot, Golf Hub showed its unavailable message but hid configured official course links. Loading just one empty snapshot made the same links appear. The all-missing multi-date state now retains selected static links once for the date range, using the existing course cards. It still says **SHARED CACHE UNAVAILABLE** and retains the same retry guidance; it makes no claim that availability was checked.

## Scope and prior inspection

Branch `fix/desktop-offline-course-links-20261103` starts from unchanged draft [#22](https://github.com/Jarryd22/golfhub-perth/pull/22), `bddf4ff537c4e2e5d6d18ab061fa6011cba5430d`. Before changing source, the [audit](context-audit.json) checked 26 branches, 20 drafts #3–22, 24 non-data source refs, no other open issues, both update repositories and cumulative reports/checklist/backlog. All source refs and the preserved loose checkout had the same all-missing branch; [scope verdict](candidate-scope-review.json). PR16 repairs missing-date wording within a rendered batch, while this outer branch previously bypassed the direct-link renderer entirely. This is also distinct from pending per-course freshness/subset-cache work.

Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`; update metadata remains Windows 5.1.17 / Android 0.1.19. The saved executor resumed after startup; no repository tests or changes ran while it was starting. Original dirty work and prior worktrees are preserved. No applicable AGENTS.md or checkout `.agents/skills` files were found. Local execution used Linux, Python 3.12.14, PySide6/Qt 6.11.2, host UTC, isolated writable data paths and offscreen scale 1. The source identifies as desktop v5.0; canonical desktop/mobile reconciliation remains pending.

The existing range-level link-rendering block is moved unchanged into a helper and reused by the all-missing branch. Static result construction uses submitted course/round context and no date, so it makes no weather/provider request. Replacement display state, one trailing stretch and the existing scroll reset remain consistent with the visible cards. Only `cache_finished`, the extracted block and its original call site change; [source comparison](source-scope.json). Single-date live fallback, loaded/saved rendering, provider/cache/booking logic and production workflows are unchanged. The new Qt module joins the existing test-only desktop workflow.

## Before and after

[Fresh exact-PR22 probe](before/offline-links-probe.json), [repaired probe](after/offline-links-probe.json), [reusable script](offline-links-probe.py). Five scenarios use actual configured courses, actual completion/rendering methods and a real empty temporary local cache. Shared snapshots are synthetic; network, weather and worker execution are blocked, browser handoffs intercepted. No live URL reachability or bookability is inferred.

| Journey | Exact PR22 | Repair |
|---|---|---|
| Altone Park only, three dates, all snapshots missing | Zero official links | One Altone Park link with the same unavailable message |
| Araluen + Altone Park + Boddington, all snapshots missing | Zero official links | Two selected static links, alphabetically ordered, once each |
| Integrated-only course, all snapshots missing | Unavailable state without static links | Unchanged |
| One empty snapshot loaded, direct-only/mixed selection | One/two direct links | Unchanged |
| Submitted nine-hole search, then pending course/round/date controls change | No recovery links | Original submitted eligible courses and nine-hole labels retained |
| Repeated completion or replacement of a previously loaded view | Links absent; stale internal display references can remain | Exactly the new direct cards, no old date sections/tee-time rows or duplicate layout items |

[Before screenshot](before/direct-only-all-missing.png) and [after screenshot](after/direct-only-all-missing.png) were inspected at 1280×800. The existing unavailable guidance remains above the restored official-course card. The [980×640 keyboard/scroll diagnostic](after/compact-links-probe.json) confirms Tab from Find Tee Times reaches the results scroll area, Altone and Boddington actions; Space hands off the two configured URLs to an intercepted browser. Both buttons are fully inside the viewport after scrolling. [Compact view](after/offline-links-980x640-scrolled.png). This is offscreen widget behavior, not native screen-reader or browser connectivity testing. The initial successful compact frame is preserved; a second diagnostic changes screenshot framing to show [full cards](after/offline-links-980x640-full-cards.png), without extra regression-test counts. [Probe assessment](probe-assessment.md).

## Verification

| Evidence class | Result |
|---|---|
| **Failed exact-baseline regressions** | Identical final new file on clean PR22: **10 methods, 3 pass / 7 fail**, eight assertion/subtest failure records, zero errors/skips. [Metadata](new-tests-baseline.json), [log](new-tests-baseline.log). |
| **Passed repaired regressions** | **10/10**: direct-only/mixed/integrated-only states, 28-date deduplication, submitted context, 9/18 eligibility, repeated/replacement rendering, course/round accessibility without an invented single date, saved-link metadata, and existing single-date fallback. [Metadata](new-tests-after.json), [log](new-tests-after.log). Saved-cache compatibility uses an explicitly written isolated fixture; recovery itself makes no cache write or weather request. |
| **Passed aggregate** | **276/276 = 148 desktop CI-selected + 91 cache/integrity + 37 additional booking/rendering**, zero failures/errors/skips, 24 fresh module processes with sockets/browser blocked. [Summary and hashes](validation/summary.json), [runner](run-focused.py). PR16–22 and earlier controls, keyboard/date/midnight, booking guards, malformed cache and provider errors revalidated. Standard 11-test lifecycle module ran once. |
| **Separate diagnostics** | **50/50 filter combinations**, 9/18 holes × Any/1–4 players × five presets ([JSON](journeys.json)); **5/5 startup/fallback decisions** ([JSON](startup-decisions.json)); five before/after configured-link scenarios plus the compact Tab/Space/scroll probe. No Qt callback errors. These are diagnostic scenarios, not additional unit-test counts. |
| **Static/source review** | Python compile, CRLF-aware whitespace, checksum-verified actionlint 1.7.12 and [independent review](review.md) pass. The shared block is AST-identical to the prior renderer. [Journey/design scope](journey-scope.md), [static checks](static-checks.json). |
| **Not performed** | Installed/native Windows or Android UI, touch/screen readers/DPI/resume, real provider/shared-network recovery, live booking/holds, installed updates/signatures, alert worker execution or notification delivery. |

Application SHA-256 `316ff3f3263828191298e63817e1e5d84cc2415dc45eeb9ea5e96b162b5af383`; new regression SHA-256 `abe56e19c09242cb2177ff20a41ef227e67914b44734a7179d89e130124f8f90`. Pre-commit metadata identifies the parent separately from changed-file hashes. Final remote head, all CI events/attempts and checkout/merge-tree equality are recorded on the draft after publication. Windows CI remains offscreen source testing, not an installed-client test.

## Limits and remaining decisions

- A final evidence checker initially stopped with `KeyError: 'sha256'` because it assumed the previous review-metadata schema; the shell then completed staging/whitespace checks, so its exit zero was not hash-validation evidence. The corrected checker uses `reviewed_file_sha256`, verifies all three reviewed files and resolves all local report links. [Both outcomes](final-evidence-check.json). No application/test change or rerun was needed.
- Today's intentional baseline failures are retained. Repaired tests passed on their first execution; no assertion or timeout was relaxed. Existing offscreen cursor/font-cache warnings did not produce callback errors. Earlier exploratory fixture/tooling failures remain in the dated reports, including November 2's missing-PySide6, duplicate-cell and unsettled-geometry attempts.
- **Historical Windows `cache_close` remains unresolved:** PR14 push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and timed out one child at the unchanged 30-second limit. Later green runs and 40 Linux non-reproductions do not prove its cause or repair. Exact-source Windows pairing and a failing-child stack remain **pending/unavailable** here, not denied. No repeated Linux diagnosis. [Authoritative follow-up](../2026-10-21-midnight/ci-followup/REPORT.md).
- Older Qt event-pump stalls, four WebEngine sandbox-helper blocks, obsolete cron assertion, fixture-write denials and interrupted work remain documented. No denial or sandbox was bypassed.
- Parent monitoring already reported November 18 false-zero weather recovery and the known Wembley calendar errors. This pass did not repeat the health watch or access providers. PR3 remains Quick18-specific; PR5/7 and #4→#6→#8 remain separate unmerged repairs. Static URLs and calendar product presence are not exact tee-time availability or freshness evidence.
- Canonical desktop/mobile/service source and existing freshness/subset integration remain pending. Alert coverage here includes 27 inert ZIP/manifest tests; zero-watch executions do not establish delivery. PR21's existing persisted blank-error records are not repaired retroactively.

This is a recovery-path usability improvement using existing cards, wording, accessible names and keyboard behavior. It adds no request, weather lookup, retry or eager date-section build. No benchmark, native speed improvement or invented user feedback is claimed. Broader onboarding/freshness clarity, submitted-filter summaries, redesign and monetization remain review decisions.

No merge, deploy, release, production/manual workflow dispatch, credential/security change, spending, third-party contact, live booking/hold or real notification occurred. No denied or uncertain write remains.
