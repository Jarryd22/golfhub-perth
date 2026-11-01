# Provider exceptions — 1 November 2026, Perth

A provider exception without a message was recorded as `error: ""`. Existing consumers treat that as success: the desktop showed **0 matching times**, omitted the failed course's booking link, and cache processing could count a failed request as fresh or recovered. A shared error-message helper now retains informative messages exactly and uses the exception class name for empty/whitespace-only messages. The six existing exception catch points use it, including page aggregation before the original exception type is lost.

## Scope and prior work

Branch `fix/desktop-provider-exception-20261101` is stacked on unchanged draft [#20](https://github.com/Jarryd22/golfhub-perth/pull/20), `63c910556c4f4dc210e41c3e6db665845436a8f0`. The [audit](context-audit.json) checked 24 branches, 18 drafts #3–20, 22 non-data source refs, no other open issues, and both update repositories before selection. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`; public update metadata remains Windows 5.1.17 / Android 0.1.19. Existing provider/weather repairs and PR18's rendering of nonempty errors do not fix these empty producer strings. The original dirty October 22 checkout and all completed worktrees are preserved. No AGENTS.md or checkout `.agents/skills` instructions were found.

This pass used the saved authorized Linux executor, Python 3.12.14 and PySide6/Qt 6.11.2, host UTC, isolated temporary data and offscreen scale 1. The source identifies as desktop v5.0; canonical reconciliation with the newer desktop/mobile candidate remains pending. This is a synthetic reproduction of reachable exception paths, not evidence that today's published cache contained this defect.

Runtime changes are one six-line helper, six serialization substitutions and two imports in core, desktop worker and cache shard. The new Qt module joins the existing test-only desktop workflow; the new cache module is selected by its existing glob. Retry classification, delays, budgets, health thresholds, stale-reuse rules, successful-empty/partial-page behavior, rendering, worker ownership and production workflows are unchanged. Class-name fallbacks do not broaden the transport retry allowlist. Existing saved `error: ""` records remain ambiguous and are not migrated or reclassified.

## Before and after

[Before JSON](before/empty-error-probe.json), [after JSON](after/empty-error-probe.json), [probe](empty-error-probe.py), [before screenshot](before/araluen-no-message-timeout.png), [after screenshot](after/araluen-no-message-timeout.png). These call the actual core and synchronous worker methods with mocked fetch exceptions and blocked network/browser access. Cache regressions execute the shard function with completed local futures, mocked sites/fetches/weather and temporary files only; no production command or workflow is invoked.

| Case | Exact PR20 | Repair |
|---|---|---|
| Araluen or Wembley fetch raises `TimeoutError()` | Empty error string; 0 matching times; no failed-course card | `TimeoutError`; Availability incomplete; failed-course card and official booking action |
| Exception escapes a desktop worker fetch | Same false zero | Same incomplete state; worker completion contract retained |
| Three of three cache fetches throw empty exceptions | All three counted fresh; output written | Health gate rejects 0/3; no payload written |
| One failed cache fetch alongside two successes | 3/3 fresh; prior usable result ignored | 2/3 fresh; failed result remains unknown or prior good data is reused with stale reason |
| Delayed retry throws an empty exception | Counts one recovery | Counts zero recoveries; failure remains visible |
| Direct-result construction throws an empty exception | Failure can slip through publication guard | Existing guard rejects it |
| Informative errors, successful empty responses, successful second-page rows | Existing behavior | Preserved; partial-page compatibility is not a claim of complete coverage |

## Verification

| Evidence class | Result |
|---|---|
| **Failed exact-baseline regressions** | **20 methods: 6 pass / 14 fail**, 22 assertion/subtest failure records, zero errors/skips. UI: 4 pass / 5 fail ([metadata](new-tests-baseline.json), [log](new-tests-baseline.log)); cache: 2 pass / 9 fail ([metadata](cache-baseline.json), [log](cache-baseline.log)). Identical final test files ran against preserved exact PR20. Raw logs are retained compressed; [provenance](baseline-log-provenance.json) records whitespace-only display normalization. |
| **Passed repaired regressions and aggregate** | **258/258 = 130 desktop CI-selected + 91 cache/integrity + 37 additional booking/rendering**, including all 20 new methods. Zero failures/errors/skips, 22 fresh module processes, sockets/browser blocked. [Summary and source/test hashes](validation/summary.json), [runner](run-focused.py), [nine-test after metadata](new-tests-after.json). PR16–20 and earlier dates, keyboard, filters, booking guards, startup/cache validation and inert alert-bundle integrity are revalidated. The standard 11-test lifecycle module ran once. |
| **Passed separate diagnostics** | **50 filter scenarios**, 9/18 holes × Any/1–4 players × five presets, with worker launch intercepted ([JSON](journeys.json)); **five startup/fallback decisions** with scheduled/live work intercepted ([JSON](startup-decisions.json)); **153 configured booking-link checks** with synthetic row/plan data and no browser/provider access ([evidence](before/booking-links/NOTE.md)). These are separate diagnostics, not additional unit-test counts or live URL reachability checks. |
| **Offscreen inspection** | Before/after 1280×800 error views and today's [980×640 recovery view](compact-980x640.png) inspected. The failed course and recovery action are visible without overlap in the inspected frames. [Visual assessment](visual-assessment.md). |
| **Static/source review** | Python compile, CRLF-aware whitespace, checksum-verified actionlint 1.7.12 and independent review pass. [Review](review.md), [journey/design scope](journey-scope.md). Remote source/release inspection does not validate installed apps. |
| **Not performed** | Native/installed Windows or Android UI, real provider/shared-network recovery, live booking/holds, screen readers/DPI/resume, updater/signature checks, alert runtime execution or notification delivery. |

Local evidence records the checked-out parent separately from changed-file hashes. Final remote head, all workflow events/attempts, terminal results and checkout/merge-tree equality are recorded on the draft after publication. Test-only Windows CI remains source/offscreen verification, not an installed Windows app test.

## Clarity, accessibility, speed and remaining limits

The fix lets PR18's existing scoped warning and official booking action appear for an actual failed observation. Existing keyboard names, compact wrapping, lazy rendering, retained booking context and date/filter behavior remain intact. It adds no request, retry, delay or eager UI build; no native performance improvement or user-feedback claim is made. Submitted-filter summary, onboarding/freshness clarity and broader layout proposals remain review decisions; no redesign or product-direction change was implemented.

- Today's intentional baseline failures are retained; repaired tests have no failed execution or relaxed assertion. Diagnostic stderr included existing offscreen cursor/font-cache warnings, with zero callback errors and successful exits. No fixture correction or manual CI rerun was needed.
- **Historical Windows `cache_close` remains unresolved:** PR14 push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and timed out one child at the unchanged 30-second limit. Later green CI and 40 Linux non-reproductions do not establish a cause or fix. Same-platform exact-source pairing and a failing-child stack are **pending/unavailable** here, not denied. No repeated Linux diagnosis. [Authoritative follow-up](../2026-10-21-midnight/ci-followup/REPORT.md).
- Older Qt event-pump stalls, four WebEngine sandbox-helper blocks, obsolete cron assertion, prior fixture-write denials, October 22 interruption and later fixture/tooling failures remain in their dated reports. No access denial or sandbox was bypassed.
- Parent monitoring already covered November 16 false-zero weather and known Wembley issues. This pass did not repeat the health watch or access providers. PR3 remains Quick18-specific; PR5/7 and #4→#6→#8 remain existing unmerged work. Passing CI does not establish live availability or valid forecasts.
- Canonical desktop/mobile/service source and existing freshness/subset changes remain pending. Alert checks here inspect inert archive/manifest bytes; zero-watch executions do not establish delivery. Public releases are unchanged.

No merge, deploy, release, production/manual workflow dispatch, credential/security change, spending, third-party contact, live booking/hold or real notification occurred. No denied or uncertain write remains.
