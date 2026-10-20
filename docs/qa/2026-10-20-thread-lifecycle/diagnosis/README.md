# Independent lifecycle diagnosis and duplicate-work audit

Read-only repository inspection plus standalone offline QtCore subprocesses. No application, workflow, PR or dependency changes were made by this audit.

## Duplicate-work verdict

After a fresh remote fetch, no existing exact cache/scan lifecycle repair was found. In `app/qt_golfhub_app.py`, function text (including decorators) for `_start_cache_search`, `cache_thread_done`, `search_live`, `scan_thread_done`, `_finish_pending_close`, and `closeEvent` is identical to main `25de15b65af6f9dcad4a4d13788fb87ab976df31` on all 13 code repair/agent refs examined. This includes PR #10 `99057788e335fa8d50e0e353c2ca5613917bf600`, #11 `6d60354a90d7a32807a3f7867cb9180d449433ce`, and #12 `93d4763451358be608bff06fd0013936af36764c`.

`remote-duplicate-scan.json` records every ref/head/function digest. PR #10's final cleanup commit changes only fixture cleanup, test hooks, the test workflow and documentation; it does not change application callbacks or QThread ownership. `pr10-cleanup-diff.json` shows `cleanup_qt_widgets()` and a representative test hook. Existing search-race tests use fake threads and invoke the done method directly, so they cannot cover native worker destruction.

## Standalone reproduction

`minimal-ownership.py` uses only QCoreApplication, QThread and a small QObject worker. It mirrors the real signal wiring, releases both Python references in the controller callback, and immediately launches the next queued iteration. There is no GolfHub UI, WebEngine, networking or file-backed application state. `--loop events` explicitly flushes DeferredDelete events; `--loop exec` runs the real Qt event loop. Completed workers and destroyed threads/workers are counted separately.

| Experiment | Observed result |
|---|---|
| Original immediate release, Qt 6.12.0, parentless / QThread(controller), events / exec | All four subprocesses SIGSEGV. Parentless stack points at clearing the thread reference; parented can point at clearing the worker reference or the next worker move. Parenting the QThread alone is insufficient. |
| Original immediate release, Qt 6.11.1, parentless, events / exec | Both subprocesses SIGSEGV. These observations do not support a Qt-6.12-only diagnosis or a dependency pin. |
| Retain both wrappers until all cycles end, Qt 6.12 | Four cases pass 200 cycles each. Diagnostic only: keeping all old wrappers is not the proposed repair. |
| Wait before release but leave automatic QThread deletion connected | Real exec cases pass, but events cases fail because the QThread C++ object can already be deleted before the callback calls wait. The controller must own deletion order for a polling repair. |
| Remove automatic QThread deletion; wait(0), retry with a 1ms single-shot timer until true, then deleteLater/clear references | Four Qt 6.12 cases pass 200 cycles each; two parentless Qt 6.11 cases pass 200 each. Both event-loop modes are covered. No callback affinity failures. Multiple runs exercised actual retries. |
| Keep existing deletion connections; move completion callback from finished to destroyed | Same minimal four Qt 6.12 / two Qt 6.11 cases pass 200 cycles each. However, the separate actual-app audit reports a second-search stall in the existing processEvents-only harness. Do not present minimal success as app validation. |
| Delay worker native destruction by 15ms, Qt 6.12, parentless | Poll and destroyed alternatives each pass 30 cycles in each event-loop mode. Poll required 442/416 retries, confirming its wait-false path without a blocking wait. |

Evidence: `minimal-ownership-results.json`, `minimal-release-results.json`, `minimal-poll-results.json`, `minimal-destroyed-results.json`, `minimal-compatibility-delay-results.json`, plus individual logs. Earlier experiment logs refer to earlier line positions in the evolving standalone script; the final script includes every mode and can reproduce the experiments. These are stress iterations, not unique app regression tests or native-device validation.

## Supported interpretation and implementation review

The observations support a lifetime overlap between releasing Python wrappers and native thread/worker cleanup. They do not identify the precise C++ instruction causing the segfault. Recorded callbacks run on the controller/GUI thread, so a wrong-receiver-thread explanation is not established. An explicit `@Slot()` remains appropriate documentation, but is not sufficient evidence of a repair.

For the polling candidate, retain `thread.finished -> worker.deleteLater`, remove `thread.finished -> thread.deleteLater`, and make the GUI completion path own thread deletion. Capture the current thread, return harmlessly if absent, call `wait(0)`, and on false retain both references and retry through one owned single-shot timer. Do not update context, launch the queued search or close the window until wait returns true. On success stop the timer, request thread.deleteLater while a local reference remains, clear the active references, then continue queued/UI/close behavior.

Review both cache and scan paths. `search_cache` already queues while any cache-thread reference exists; `search_live` must not replace a stopped-but-not-cleaned-up scan thread. Close and pending-close guards must use outstanding references, not only `isRunning()`. Cleanup timers must remain active during close, unlike startup/search/scroll timers. Ensure no pending retry can release a newly started thread; stop the single timer on success and test queued restart exactly once. If explicit stale finished callbacks are supported in tests, reject a QThread sender that differs from the current thread.

Recommended regressions: actual asynchronous cache and scan execution; wait-false/true cleanup; next queued search once; changed filters preserving latest request; cancellation/no queued restart; close during native cleanup; and destruction counts returning to zero without retaining all historical wrappers. Preserve the original baseline crash logs and validate the final candidate with the original app harness and a real Qt event loop.

## Qt documentation consulted

- [QThread finished and completion state](https://doc.qt.io/qt-6/qthread.html#finished): finished is emitted before final cleanup; isFinished/isRunning do not synchronize all cleanup effects, while successful wait does.
- [QObject deleteLater](https://doc.qt.io/qt-6/qobject.html#deleteLater): finished-to-worker-deleteLater is the documented cleanup pattern. Deferred deletion needs event-loop handling; processEvents-only loops require explicit attention to deferred deletes.
- [Qt for Python slots and affinity](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html#thread-affinity): QObject slots and Auto/Queued connections target receiver affinity. Measure actual callbacks before blaming absent decorators.
- [Threads and QObjects](https://doc.qt.io/qt-6/threads-qobject.html#signals-and-slots-across-threads): the QThread object belongs to its creating thread; it is distinct from the native thread executing the worker.
