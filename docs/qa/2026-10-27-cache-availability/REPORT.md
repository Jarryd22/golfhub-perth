# Missing-date cache states — 27 October 2026

A partially loaded multi-day search labelled a date with no snapshot **No matching live times**, and its expanded body claimed that no times matched. The summary also counted the unavailable date among searched days. The repair labels that date **Availability not checked**, explains how to retry or select one date for Refresh Live, and scopes match totals to loaded days.

## Recovery and scope

This completes the unpublished October 22 work after its usage-limit interruption. The original dirty `/workspace/golfhub-perth` checkout remains preserved on `fix/desktop-search-filter-20261022`; the recovered artifacts are retained under [recovered-2026-10-22](recovered-2026-10-22/README.md). The new branch is `fix/desktop-missing-cache-20261027`, based on unchanged draft #15, `4ce2be23255edc9d7579d8529ef2f7e366c304ca`. Its alert-runtime validator remains unchanged and is included in the aggregate tests, not reimplemented.

The [current context audit](context-audit.json) confirms 13 existing open drafts #3–15, unchanged main `25de15b`, and unchanged update repositories. The [17-source-ref audit](source-ref-audit.json) found no duplicate missing-date fix. No applicable AGENTS.md or checkout `.agents/skills` was present. The newer dirty desktop/mobile candidate is unavailable here and untouched; canonical-source reconciliation still gates integration. This tests the remote v5.0 source line, not an installed release.

Only existing `available` metadata is consumed. Cache fetch/save/freshness, provider behavior, worker lifecycle, booking and notification code are unchanged. Lazy day builders capture their own availability and date; legacy direct callers without the field retain loaded behavior. Saved-device fallback counts as loaded. Loaded empty results, provider-error/unreleased-calendar cards and deduplicated official links retain their existing behavior. Fully missing multi-date cache keeps its existing actionable unavailable state.

## Reproduction and verification

The identical [probe](probe.py) renders three synthetic dates, two loaded and one absent, against exact #15 and the repaired source. Sockets/browser paths are blocked and no workers run. [Before JSON](before/probe.json), [after JSON](after/probe.json), [before image](before/empty.png), [after image](after/empty.png).

| Observable | Exact #15 | Repair |
|---|---|---|
| Missing-date heading | No matching live times | Availability not checked |
| Expanded missing-date body | No times matched these filters | Availability could not be checked; retry/single-date live guidance |
| Empty partial summary/status | 0 matches across 3 days | 0 matches across 2 loaded days |
| Partial search with one matching row | 1 match across 3 days | 1 match across 2 loaded days |
| Actual cached rows and loaded-empty wording | Preserved | Preserved |

| Evidence class | Result |
|---|---|
| **Failed baseline automated tests** | Identical ten new regressions: **3 pass, 7 fail**, zero errors/skips on exact #15. [Log](new-tests-baseline.log), [metadata](new-tests-baseline.json). |
| **Passed focused regressions** | **10/10 pass** on repaired source, zero errors/skips. [Log](new-tests-after.log), [metadata](new-tests-after.json). |
| **Passed aggregate automated checks** | **157/157: 87 desktop + 70 cache/integrity**, fresh process per module, sockets/browser blocked. Includes inherited dates/midnight, keyboard, course selection and 18→9→18, booking context, custom time ranges, search races, standard lifecycle regressions and #15 integrity tests. [Summary and hashes](validation/summary.json), [runner](run-focused.py). |
| **Passed source-widget journey probe** | **50 combinations** of 18/9 holes × Any/1–4 players × five time presets. Actual search-button input, submitted dates/round and visible row counts agree with independent fixture expectations; partial coverage remains explicit. Worker launch is intercepted; this does not test worker completion or live availability. [Results](journeys.json), [runner](journeys.py), [log](journeys.log). These are diagnostic scenarios, not 50 additional unit tests. |
| **Offscreen visual inspection** | Current 1280×800 before/after images and [980×640 compact view](compact-980x640.png) inspected. Recovery text fits, scroll reaches it, custom labels remain visible. Default scale 1; Linux Qt rendering only. Existing date punctuation issue remains in the reconciliation backlog. |
| **Passed static/review checks** | Python compile, CRLF-aware whitespace, actionlint v1.7.12 and [independent diff review](review.md). Checksum-verified actionlint metadata is in [review-metadata.json](review-metadata.json). |
| **Source/metadata inspection only** | Branch/PR duplication, production-trigger exclusion and Windows 5.1.17 / Android 0.1.19 release asset metadata. No current signature verification or installed updater check. |
| **Not performed** | Native Windows/Android interaction, screen reader/DPI/device resume, installed updater, live provider/booking/hold and notification delivery. No hourly production audit repeated. |

Local runtime: Linux, Python 3.12.14, PySide6/Qt 6.11.2, `QT_QPA_PLATFORM=offscreen`, host UTC and isolated temporary app/cache directories. Local pre-commit metadata names the checked-out #15 parent and separately records modified source/test hashes; it does not claim that an uncreated commit was tested. Source SHA-256 `66ea8e273a7071d469fa2b88d15ff1c8b07627339f79ef362fc79aaab10aeba4`; new test SHA-256 `85be195451c0463b71a3805d11c22741e37c6ec64b820d0137cedfe184f668c7`. Exact remote-head CI is recorded on the draft after publication, enumerating all events and attempts.

## Retained failures and limits

- The initial October 27 journey fixture incorrectly converted 6:30 pm to 1170 minutes (19:30), so its Afternoon expectation failed. The correct value is 1110. [Initial script](journeys-initial.py) and [failed log](journeys-initial.log) are retained; correcting the fixture produces all 50 passes without an app change. The original shell wrapper returned the trailing log-display status; the Python assertion itself failed and is not counted as a pass.
- October 22 stopped at the usage limit before tests/report/PR completion. Its CLI API calls returned Forbidden; connected GitHub access worked. One after-probe invocation failed before execution because its log directory did not yet exist; creating that directory resolved it. These were tool/execution issues, not product fixes or approval denials.
- Historical #14 Windows push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) remains **76 pass / 1 failed `cache_close` timeout**. Later green runs and 40 Linux non-reproductions do not resolve it. The [prior investigation](../2026-10-21-midnight/ci-followup/REPORT.md) remains authoritative. This pass runs the unchanged standard lifecycle module once in the aggregate; it does not repeat the paired Linux investigation or relax tests. No causal/runtime repair is claimed.
- The older Qt 6.11 manual-pump stall, four WebEngine sandbox-helper blocks and obsolete cron assertion remain known limits outside this focused suite. #15's earlier Windows sandbox fixture-write failures remain disclosed in its report. No blocked target was retried or sandbox bypassed here.
- November 11 false-zero weather is supplied monitoring context, already covered by unmerged #4→#6→#8. Those changes were not duplicated, merged or deployed. Cache observation freshness, subset preservation and canonical source provenance remain separate backlog work. Zero-watch alert runs do not prove delivery.

The only workflow change adds the new module to existing desktop test filters/list. Production workflows remain unchanged and do not select this repair push/PR. No production dispatch, manual CI rerun, merge, deployment, release, credential/security change, spending, third-party message, booking/hold or real notification occurred.
