# Independent review — live failure and stop recovery

No blocking findings in the final application, regression tests or desktop test workflow. The repair distinguishes an unsuccessful live refresh with retained displayed results from one with no results to retain, and makes the cold failure body actionable. This review covers the uncommitted repair on exact PR23 `50ae64a00b4372d1f8c33dd787c2d5406510da2e`; `review-metadata.json` records the four reviewed file hashes. The parent task must separately verify the eventual commit, remote branch and exact-head CI.

## Source and state review

Only `GolfHub.scan_failed`, `scan_finished` and `clear_results` change. Worker execution/cancellation, successful snapshot persistence, provider handling, filter logic and booking safeguards are unchanged. The existing local/ref overlap audit and cumulative backlog distinguish this failure-presentation defect from pending canonical per-course freshness and subset-cache work; the patch does not implement a competing cache policy.

`clear_results` now assigns fresh empty lists to `last_results` and `day_sections` when it removes their widgets. It does not mutate the old lists. A caller passing `window.last_results` to `render_results` therefore retains its input, and both single/multi renderers restore their new display metadata after clearing. `render_empty(clear=False)` does not clear those lists. This also prevents an earlier successful display, already removed by a new cache search, from falsely qualifying as retained results on a later live failure or stop.

When actual previous results remain, the failure/cancellation handlers do not clear or rebuild their widgets or metadata. Saved/live result rendering uses the same retained-state branch; captured booking context, lazy date context and static official-link actions stay intact. The new language describes visible previous results without claiming their disk-cache provenance. A retained static link still does not establish checked tee-time availability.

With no retained results, failure replaces the obsolete checking text with retry guidance and cancellation no longer claims cache preservation. Search controls are restored by the existing completion logic; partial cancellation results remain unsaved. The closing guard still suppresses the error dialog and body replacement. The worker's normal failure signal emits a traceback; its existing last-line diagnostic extraction is unchanged.

The provider/core, course-result, shared-cache, booking, cache publisher, alert runtime ZIP/manifest and production workflow files are byte-identical to PR23. Desktop CI adds only the new module to the PR/push path filters and isolated test list. Existing production trigger scopes and permissions are unchanged. No production action was executed by this review.

## Test and evidence review

The reviewer read all eleven final regression methods and saved execution records without duplicating runtime tests. The focused suite uses actual widget handlers and real synchronous `ScanWorker.run`/failed signals, while native QThread creation/moves are intercepted. It uses temporary real empty/saved local-cache files, mocked executor failure before requests, blocked network/provider/booking access and intercepted browser/dialog calls. It does not exercise a native background thread; the existing lifecycle suite supplies separate synthetic-worker lifecycle coverage.

Coverage includes first-launch cache absence followed by an actual failed signal, cold stop, prior multi-date results cleared by a new cache search before failure/stop, saved bytes/card identity and booking context, retained lazy rows/date, retained static action, cancelled partial results, successful retry, repeated failure, alias re-render and closing behavior. The alias and multi-date clear cases specifically cover the reset risks identified during review.

The identical final test file on exact PR23 yields **2 passed and 9 failing methods**, with **10 failed assertion/subtest records**, no errors and no skips. The repaired source yields **11/11 passing methods**. The final aggregate is **287/287 tests across 25 isolated module invocations**, with zero failures/errors/skips: 159 desktop, 91 cache and 37 additional checks. The standard eleven lifecycle tests ran once as part of that aggregate. Their edits only update cold-state expected headers and add absence/dialog assertions; the 30-second subprocess timeout, ownership gates, cleanup and no-retry behavior remain unchanged.

The initial baseline execution is retained and must not be hidden: a helper named `fail` shadowed `unittest.TestCase.fail`, producing **4 failure records and 6 errors**. The initial repaired run passed 11/11. The helper was renamed `emit_failure` and subtest cleanup isolated; the unchanged final module was then run against both source versions. Initial source/logs remain in `initial-fixture/` and `new-tests-*-initial.*`. The final baseline has zero errors and does not depend on that broken fixture. No application workaround or relaxed assertion was introduced for the fixture issue.

The reviewer visually inspected the 1280×800 baseline and repaired cold-failure screenshots. Before: the body still reads “Checking courses live...” while header/status claim cache preservation despite an empty `last_results`. After: the retry note is visible, the header says “LIVE REFRESH FAILED” and the status says no results are available. Both probe records have zero callback errors. The separately inspected 980×640 repaired screenshot shows the note and both retry controls within the window; its metadata records them visible and enabled. Dialog text is intercepted and asserted, not a native modal-dialog screenshot.

The separate journey report records 50 filter and five startup diagnostics; these are not extra unit-test counts. The reviewer read those records but did not rerun them. Static validation records show compilation, actionlint and whitespace checks pass; the reviewer independently verified the changed-method scope, byte comparisons, final hashes and CRLF-aware `git diff --check`.

## Limits

No native Windows/Android UI, real browser navigation, provider availability, live booking/hold, notification delivery, installed updater/signature, native screen-reader or DPI/device test was performed by this review. The historical Windows `cache_close` timeout remains unresolved: the standard aggregate's passing lifecycle suite does not establish a fix, and no extra Linux timeout investigation or test relaxation was performed. Canonical desktop/mobile source and existing freshness/subset integration remain pending. Source/offscreen evidence does not establish deployment behavior.

The reviewer changed only these review artifacts. No denied or uncertain reviewer action occurred. Remote branch and exact-head CI verification remain with the parent task.
