# Follow-up: omitted Windows push CI failure — 21 October 2026

**The original code head has mixed CI results, and the cause of its Windows cache-close timeout remains unresolved.** The initial daily PR/final summary consulted a helper that returns PR-event runs only and omitted the push run. That was an evidence-reporting error. The PR description, daily report, checklist and backlog now disclose all three executions. No application, regression-test or workflow code was changed in this follow-up.

## Exact original code-head CI record

Head `9ed31ad463e00637732162e0592442ae3f66668a`; source tree `461d10710ead5d79751e16062ca83de99452d7ec`. The [unfiltered API audit](original-ci-executions.json) returns exactly three runs, all attempt 1:

| Event / run | Result | Evidence |
|---|---|---|
| Windows desktop **push**, [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) | **FAIL: 76 pass, 1 fail** | `test_close_during_cache_work_does_not_launch_queued_search` / child `cache_close` exceeded the unchanged 30-second timeout. Failure logged at 00:58:42 UTC / 08:58:42 Perth. Python 3.12.10, PySide6/Qt 6.12.0. |
| Windows desktop **pull_request**, [39524443056](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524443056) | PASS: 77 tests | Same application/test tree via merge `d6c5e20ad85be8d467cbc9ee870067721bd51d20`. |
| Linux cache **pull_request**, [39524443135](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524443135) | PASS: 43 tests + actionlint | Same merge tree. |

All 15 midnight regressions passed in both Windows executions. The failed lifecycle module ran 11 methods: ten passed and `cache_close` failed; its total elapsed time was 35.849 seconds. The [complete failed-job log](failed-push-desktop.log) (readable whitespace-normalized copy; [original decoded tool text](failed-push-desktop.json)) captures the parent subprocess timeout but no child output/stack. `-X faulthandler` alone does not produce a timed stack for a hung child. Therefore the log does not identify whether it stalled in event pumping, a callback, native cleanup or final disposal. The later pass does not erase this failure. No CI rerun was requested.

## Comparison with untouched #13

Base `8b01866f3783d9ef021e114c81c139dede1facc1`; repair code head `9ed31ad…`.

The [read-only comparison](lifecycle-review-comparison.json) confirms the lifecycle harness and shared teardown helper are byte-identical. Nine relevant methods—including cache worker run, cache completion/cleanup, search entry points and close handling—have identical ASTs. In `cache_close`, the harness stops deferred timers before worker startup, so the new midnight timer is stopped. It calls `_start_cache_search` directly and patches `params` for queued searches. The new activation handler performs no rollover on the same day and is suppressed after closing starts. Extra object allocation and scheduling effects still cannot be excluded by source inspection.

The prior retained #13 incident was **Linux Qt 6.11.1**, in a different asynchronous journey harness, with a diagnostic-abort stack in `QTest.qWait` during a multi-date search. This new failure is **Windows Qt 6.12.0**, in `cache_close`, with no failing child stack. Shared event-pump use is a lead, not evidence of a common cause. [Independent review and diagnostic plan](lifecycle-followup-review.md).

## Safe reproduction results

Before running, each cohort declared ten paired rounds with alternating base/head order, a fresh isolated runtime for every invocation, the original 30-second limit, retention of every outcome, no retries, and a four-timeout safety cap. Neither cap was reached. The unchanged harness blocks socket/browser paths and uses actual QThreads with synthetic gated cache data.

| Linux source / runtime | Exact #13 | Exact #14 |
|---|---:|---:|
| Qt 6.11.2, Python 3.12.14: unchanged cache_close scenario | 10/10 pass | 10/10 pass |
| Qt 6.12.0, Python 3.12.14: unchanged cache_close scenario | 10/10 pass | 10/10 pass |
| Qt 6.12.0: one full unchanged lifecycle module per source | 11/11 pass | 11/11 pass |

Every cohort pass reports one worker and one thread destroyed, zero callback exceptions, and no extra queued fetch. **40 scenario invocations + 22 test-case executions across two full-module runs passed**, with no timeout, failure, retry or discarded result. These are repeated executions of existing regressions, not 62 new unique tests. The Qt-version cohorts overlapped in this shared Linux environment; timings are diagnostics, not a performance or failure-rate comparison. Both full modules ran sequentially. Qt 6.12.0 was installed only into an isolated temporary environment; repository dependencies and the saved environment were unchanged.

Evidence: [Qt 6.11.2 cohort, commands and hashes](qt6112/cohort.json), [runner](qt6112/run_cohort.py); [Qt 6.12 cohort](qt612/results.json), [runner](run-pairs.py); [full-module results](qt612-full/results.json), [base log](qt612-full/base.log), [head log](qt612-full/head.log). Every individual cohort stdout/stderr log is retained alongside its summary. Lifecycle harness SHA-256: `1d85f1aa6e7002a7005aacdb479004d2650c115f949966235d3a7c966c903602`; base application: `97b08fc865c67e7fea5f660f39a9191bf00f924820a3ad55917067622723091d`; repair application: `214cf0e3cff96f5014c75d70178abf8ca1470c0d271bad64a0c5734677a6ba50`.

## Finding and remaining limit

The Windows failure is confirmed in the retained CI execution and was not reproduced by these Linux comparisons. **Neither “introduced by #14” nor “the existing #13 intermittent issue” is established.** There is insufficient causal evidence for a runtime fix or a second lifecycle repair. Timeouts/assertions, application code and CI workflows remain unchanged; no test was relaxed or replaced.

The remaining diagnostic action is a paired exact-source run on Windows/Python 3.12.10/Qt 6.12.0, capturing a bounded all-thread child traceback and last completed phase if it stalls. **Pending/unavailable:** this selected environment provides Linux only, and the original failed job has no child stack. It is not an approval denial. Existing hosted logs were inspected; no production workflow or test rerun was dispatched. Although this correction changes documentation only, GitHub evaluates PR-event path filters against the complete PR diff, so the update automatically schedules fresh PR test checks. These are separate exact-head executions, not manually requested reruns; their results belong in the PR description alongside the retained original failure. No push-event test runs are expected for documentation-only paths. App/test hashes remain those of the tested original code head.

Canonical-source reconciliation, installed updater, native Windows/Android, screen readers/DPI, device notification delivery, the separate older Qt journey stall, obsolete cron assertion and prior WebEngine sandbox-helper block remain unresolved/unverified as previously recorded. No sandbox bypass, merge, deploy, release, credential/security change, spending, third-party contact, booking or notification occurred.
