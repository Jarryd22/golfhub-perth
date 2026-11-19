# Explicit searches supersede startup refresh — 19 November 2026, Perth

A confirmed first-launch conflict can associate live results with the wrong date, round and group. After saved data appears, Golf Hub schedules an automatic shared-cache search for 100ms later. An accepted Refresh Live or Find request does not cancel that pending startup work. If controls change afterward, the automatic request reads those unsubmitted values and can replace the live context or overwrite an explicitly queued Find.

The focused repair stops only `_initial_cache_timer` and `_cache_search_timer` after a request is accepted. Four stop calls preserve invalid/refused requests, explicit queues, normal automatic startup, scrolling, Perth rollover and native worker ownership. Provider, weather, persistence and workflow code are unchanged. Branch `fix/desktop-startup-search-20261119` is based directly on [PR31](https://github.com/Jarryd22/golfhub-perth/pull/31), exact baseline `23defe0efec9cd98e31c65af3744d5730a1391d2`.

## Inspection and before/after evidence

The [repository audit](repository-audit.json) inspected current main, all branches/open drafts, repair issues, both update repositories and prior local evidence before selection. At 08:45:05 Perth there were 36 branches, 29 drafts #3–31 and no non-PR issues; main and all source repair heads were unchanged. Both README blobs and all five workflows were unchanged. Android's designated latest remains **0.1.19**; the first-listed **0.1.8** is older. Windows remains **5.1.17**. No release asset, restricted manifest, installed updater or device was tested. No relevant checkout/ancestor AGENTS or `.agents/skills` was found.

The [duplicate comparison](duplicate-audit.json) examined **34 immutable source refs and 24 preserved local/archive Qt files**, with no read/parse errors or competing cancellation fix. Their initial-cache method is identical; search paths do not stop the startup timers. Existing PR31 repairs the later cache-miss/live-owner handoff, which is a separate ordering. Yesterday's local verification and the original dirty checkout remain preserved; their documentation chain is not included in this repair branch.

The reproduction uses real `QApplication.exec()` and unchanged owned 0ms/100ms timers. A Qt mouse click is injected just after initial saved rendering. Native threads are inert, worker bodies are blocked, and persistence is intercepted. This establishes a reachable ordering, not natural production incidence.

| Case | Exact PR31 before | Repaired source after |
|---|---|---|
| Live search for January 3 / 18 holes / four players, followed by unsubmitted January 4 / nine holes / one player edits | Automatic cache request starts while live is owned; old live rows are passed to saving under January 4 / nine holes. BOOK's accessible date is January 4. | No extra cache worker; submitted context remains January 3 / 18 / four. Save envelope and BOOK date retain January 3. |
| Same live action without changing controls | Still starts an unnecessary second cache request; date/round happen to match. | One live worker; no deferred cache request. |
| Normal startup and closing before either deferred callback | Three controls pass, preserving normal latest-control startup and close cancellation. | All three controls remain passing. |

The two repaired live cases pass **14 named recovery checks**. The three controls pass **25 named assertions per source**, plus one separate normal-startup thread-start check per source. These are **five unique diagnostic cases**, not additional unittest methods. Original synthetic saved bytes remain unchanged; no incorrect save reaches an actual cache. [Journey scope, commands and preserved history](journey-scope.md), [provenance](journey-provenance.json).

Settled 1280×800 captures were inspected before and after. Pending controls deliberately differ from retained submitted results; the save-envelope and accessible-date correction is established by JSON/assertions, not a visible date change. Existing date-label encoding remains a prior canonical-source backlog item. No speculative visual redesign or user-feedback claim is made.

## Regression and aggregate results

The final identical external test file was run against exact PR31 and the repair:

- **Baseline: 10 passed, five failed; zero errors/skips.** All seven original methods pass. Failures cover accepted Live and Find before/after initial saved rendering, and an explicitly queued Find overwritten by the automatic request. [Baseline](regressions/baseline/result.json).
- **Repair: 15/15 passed**, zero failures/errors/skips. Eight methods are added; original seven methods and their helpers remain AST-identical. Save envelope, rendered booking date, submitted context, start counts, refusal guards and normal startup are asserted. [Repair](regressions/repaired/result.json), [regression provenance](regressions/provenance.json).
- **Final aggregate: 350 passed = 218 desktop CI-selected + 95 cache/integrity + 37 additional**, in 28 isolated module processes; zero failures/errors/skips. [Summary and logs](final-aggregate/summary.json).
- Python compilation, actionlint 1.7.12, whitespace/artifact checks and [independent source/evidence review](review.md) pass. Existing assertions, production timer intervals and module/lifecycle timeouts were not loosened.

An initial unchanged-source selection of 32 existing startup/cache-shape/recovery tests passed before the new reproduction. Those counts are preserved separately in [initial evidence](initial-targeted-tests/targeted-tests/summary.json), not added to the 350 aggregate. The original 11-method real Linux QThread suite ran once in that aggregate; no repeated Linux diagnosis of the historical Windows timeout was attempted. Other aggregate coverage includes dates, 9/18 holes, course/group/time filters, retained booking context, missing/error/offline states, earlier handoff fixes and data-only alert integrity. It does not execute delivery.

Commands, from `/workspace/golfhub-20261119-repair`:

```sh
/workspace/golfhub-perth/.venv/bin/python -X faulthandler docs/qa/2026-11-19-startup-search/regressions/run-startup-tests.py --root /workspace/golfhub-20261117-repair --test-file /workspace/golfhub-20261119-repair/tests/test_startup_cache.py --output docs/qa/2026-11-19-startup-search/regressions/baseline
/workspace/golfhub-perth/.venv/bin/python -X faulthandler docs/qa/2026-11-19-startup-search/regressions/run-startup-tests.py --root /workspace/golfhub-20261119-repair --test-file /workspace/golfhub-20261119-repair/tests/test_startup_cache.py --output docs/qa/2026-11-19-startup-search/regressions/repaired
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-19-startup-search/run-aggregate.py --root /workspace/golfhub-20261119-repair --output docs/qa/2026-11-19-startup-search/final-aggregate
/workspace/golfhub-perth/.venv/bin/python -m py_compile app/qt_golfhub_app.py tests/test_startup_cache.py
/workspace/scratch/actionlint-1.7.12/actionlint
```

Regression commands identify the same runner/arguments; original execution used its scratch path before byte-identical copying. See regression provenance for exact original locations. Declared desktop source `APP_VERSION = "5.0"`; Linux/Python 3.12.14/Qt 6.11.2, isolated writable runtime directories, offscreen, blocked network/browser/provider actions. This is not the installed Windows 5.1.17 package. New tests use a bounded elapsed-time predicate for timer completion/cancellation, with inert threads and real QObject signals. They do not claim real native scheduling.

- Baseline Qt SHA256: `e739043b8c4e60556cee1b713fe28464d2dc72242b39b02df4c99d8ffca94927`.
- Final Qt SHA256: `531055544bc6cab4707d29a1293d4356e2852cb1426eb7955029b97c15d1cd35`.
- Final test SHA256: `f8d044df7d70854962b97ffab8039e85f0e9a921dfc030939699ca6d0b337d3a`.

Local runs record their actual starting HEAD plus source/test hashes for uncommitted changes. The [evidence manifest](evidence.json) anchors final artifacts. Exact published commit/CI results are established after publication in the PR and task result; this committed report records local prepublication evidence.

## Retained failures and limits

Three early diagnostic executions timed out (15s, 15s, 12s) because the fixture called quit while inert worker owners still triggered Golf Hub's normal close guard. Phase/stack evidence, scripts, logs and images are retained. The fixture-only correction flushes observations and releases inert owners before quit; it changes no product code, action or startup interval and increases no bound. The corrected observations and separate capture-only replays complete cleanly. There are 12 completed diagnostic executions across five unique cases; repetitions are not extra tests.

Review replaced the new test helper's fixed 180ms wait with an asserted one-second predicate bound, so slow initial rendering does not consume the subsequent 100ms interval. The prior same-file baseline/repair runs and file are retained under `regressions/pre-review-fixed-wait/`. `QTest.qWaitFor` was unavailable in the installed binding (read-only capability lookup, exit 1, not a test execution), so the helper uses `QElapsedTimer` and short `QTest.qWait` steps. An audit-assembly quoting SyntaxError and an evidence-copy heredoc SyntaxError occurred before execution/writes; corrected attempts and notes are retained. No product test assertion was removed or weakened.

Historical Windows `cache_close` remains unresolved: [original failure and follow-up](../2026-10-21-midnight/ci-followup/REPORT.md). Later green checks or this deterministic startup repair do not diagnose it. Earlier fixture failures, manual-pump stalls, obsolete cron assertion and blocked WebEngine checks remain recorded in their original reports; this is the applicable isolated aggregate, not every legacy test.

Not performed: installed Windows/Android, natural incidence of this ordering, live provider/cache/weather monitoring, real bookings/holds, notification delivery, native screen readers/touch/DPI/resume, updater/signatures, performance benchmarking or canonical desktop/mobile integration. The new startup probes use real UI timers but mocked native workers; only the unchanged aggregate lifecycle module exercises real Linux threads. No native Windows diagnosis is inferred.

Only normal repair push/PR CI is authorized. Workflow triggers were inspected: this branch matches desktop test push and desktop/cache PR checks; production refresh/news require main-specific or schedule/manual/alert-completion triggers. No workflow is changed or manually dispatched. No denied documentation-only PR, production-history endpoint, restricted directory or manifest route is retried. No merge, deployment, release, credential/security change, spending, outreach or live transaction occurs.
