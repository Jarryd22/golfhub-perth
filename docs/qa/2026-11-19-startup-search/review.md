# Independent review — 19 November 2026

No substantive source, regression or evidence blocker was found. The confirmed startup ordering justifies the focused repair. Review was read-only apart from this review record: no application/test execution, remote action, provider access or runtime/test/workflow edit was performed by the reviewer.

## Reviewed revision and scope

The worktree began at exact PR31 `23defe0efec9cd98e31c65af3744d5730a1391d2`; the candidate was still uncommitted during review. These byte hashes identify the reviewed final files:

| File | SHA256 |
|---|---|
| Baseline `app/qt_golfhub_app.py` | `e739043b8c4e60556cee1b713fe28464d2dc72242b39b02df4c99d8ffca94927` |
| Candidate `app/qt_golfhub_app.py` | `531055544bc6cab4707d29a1293d4356e2852cb1426eb7955029b97c15d1cd35` |
| Final `tests/test_startup_cache.py` | `f8d044df7d70854962b97ffab8039e85f0e9a921dfc030939699ca6d0b337d3a` |
| Unchanged `.github/workflows/test-desktop.yml` | `249034d9961e423cd1f9d5945c1972e3163a3b67da67ca9e53b60fdd2f7505ad` |

The runtime diff adds four timer-stop calls and one comment. Both search paths cancel only the pending initial/cache startup timers after their existing acceptance guards. Invalid selections, unsupported multi-date Live, an owned live worker and closing requests retain their previous behavior. A valid queued Find also supersedes automatic startup while retaining its explicit context. The broader deferred-timer helper is deliberately not used, preserving Perth rollover and scroll work. Worker ownership, persistence, rendering, provider behavior, intervals and workflow triggers are unchanged.

The failure is separate from PR31's terminal-worker/cache-miss handoff: here a still-pending startup callback changes context or an explicit queue after an accepted search. The source audit records 34 immutable source refs and 24 known local/archive files with no competing cancellation repair. This review inspected that audit and the local exact-baseline diff; it did not repeat remote inventory queries.

## Regression review

AST comparison against exact PR31 confirms the whole original `CachedStartupTests` class and `tearDownModule` are unchanged. Eight methods are added in a separate class; the seven original tests remain. The final identical test file records 15 methods on each source: baseline **10 pass / 5 fail**, candidate **15 pass**, with zero errors/skips. The five failures cover accepted Find and Live in both startup phases and a valid explicit queue displaced by automatic startup. Normal startup, refusal guards and close cancellation are passing controls. Save envelope, result rows, submitted context, BOOK accessible date and worker start counts are asserted.

The original new helper's fixed 180ms wait passed locally but could expire before a slow initial render finished starting the 100ms refresh. Review requested a bounded completion/cancellation predicate. The final helper uses `QElapsedTimer` and short event-processing waits, asserts both owned startup timers become inactive within one second, and checks callback errors. This changes no original test, production interval or historical lifecycle timeout. The initial file and both initial results are preserved under [pre-review-fixed-wait](regressions/pre-review-fixed-wait/); the compressed diff and hashes match that history. The immediate pending-scroll assertion and Perth-timer checks guard against accidentally cancelling all deferred work.

Fixtures use real QObject terminal signals and owned Qt timers, with inert QThread mocks and blocked worker bodies/network/browser/provider actions. Save calls are intercepted; only an isolated synthetic saved file is actually read/written and its bytes must remain unchanged. Setup, teardown and callback-error guards are consistent with that scope. These tests do not establish native worker timing or natural production incidence.

## Evidence and aggregate cross-check

All 28 aggregate log files end in `OK`; their `QA_RESULT` records match [summary.json](final-aggregate/summary.json). Totals independently sum to **350 passed, zero failures/errors/skips**: **218** methods selected by the unchanged desktop workflow, **95** cache/integrity methods and **37** additional methods. All 34 selected test-file hashes match the recorded final aggregate. The unchanged 11-method real Linux QThread lifecycle module ran once within that aggregate; it is separate from the inert-thread startup fixtures and does not resolve the historical Windows timeout.

The diagnostic source, records, history and before/after settled screenshots support the narrower claims in [journey-scope.md](journey-scope.md). There are five unique cases, 14 named repaired-case checks and 25 named control assertions per source, plus a separate normal-startup mock start-once check per source. Three fixture timeouts and 12 completed executions are retained; replayed captures are not extra unique tests. Baseline exit-zero observations are correctly distinguished from passing recovery assertions.

Before repair, the intercepted save receives a January 4/nine-hole envelope for January 3/18-hole live rows after unsubmitted controls replace the context. After repair, the submitted January 3/18/four-player context and BOOK date remain intact, without an extra startup cache worker. No wrong save reaches a real cache. The two inspected settled 1280×800 images show pending nine-hole controls alongside retained 18-hole rows; JSON/assertions establish the save and accessible-date correction, not a visible screenshot date change.

All **59** journey artifact hashes match their manifest. All **12** regression copied artifacts match both their recorded hashes and original scratch bytes. The preserved initial test file matches its old result hash. Regression execution statuses, fixture quit-guard timeouts, capture-only changes, unavailable `QTest.qWaitFor` inspection and failed evidence-copy command remain distinguished from product failures. A reviewer-only JSON summarization initially treated an integer failure count as a list and raised `TypeError`; the corrected read verified the integer fields. No application or test execution was involved in that inspection error.

Review methods were local `git diff`/`git show`, bounded source/report reads, AST comparison, SHA256 comparisons, gzip inspection and JSON/log arithmetic. No tests were rerun. At this stage, the draft report's source/hash/count/history and device-limit statements agree with the evidence. The final manifest, cumulative-document updates and eventual remote head/CI are handled after this review; no publication or exact-head CI success is inferred here.

Historical Windows `cache_close`, canonical desktop/mobile/release integration and installed-device validation remain open. No live booking, provider freshness, delivery, native screen-reader/DPI/touch/resume or performance result is claimed. Existing access denials and publication restrictions were not retried or bypassed.

## Final prose follow-up

The completed report and November 19 cumulative checklist/backlog additions were reviewed against the evidence. Counts, baseline failures, five unique diagnostic cases, intercepted persistence, real Linux lifecycle coverage, historical limitations and local-only prior documentation are consistent. The report's regression command examples now include `-X faulthandler` and identify the original scratch execution locations through provenance. Final runtime/test hashes are unchanged. All report-relative links now resolve; the parent is assembling and validating the final evidence manifest. No material wording correction or additional application change is required. Remote publication/CI verification remains subsequent work and is not claimed by this review.
