# Independent review of the omitted Windows lifecycle failure

The exact #14 head `9ed31ad` reportedly has a failed push desktop run (`39524383636`, job `118975503438`): the `cache_close` child exceeded its unchanged 30-second timeout. Later PR checks passed. These are distinct observations; the later passing run does not erase the failure or establish a cause.

## Source attribution

Read-only comparison against exact #13 `8b01866f3783d9ef021e114c81c139dede1facc1`:

- `tests/test_thread_lifecycle.py` is byte-identical (SHA-256 `1d85f1aa6e7002a7005aacdb479004d2650c115f949966235d3a7c966c903602`). The shared Qt teardown helper is also byte-identical.
- CacheWorker.run, GolfHub._start_cache_search, cache_finished, cache_thread_done, search_cache, search_live, closeEvent, _finish_pending_close and scan_thread_done are AST-identical. Machine-readable evidence: `lifecycle-review-comparison.json`.
- The scenario calls `_stop_deferred_timers()` before showing the window or starting its first worker. On #14 this stops the new 30-second Perth-date timer; it therefore does not run during cache_close.
- The scenario calls `_start_cache_search(old)` directly. Its queued searches patch `params()`, so the new pre-submission date refresh does not run there.
- A new activation handler may run when the window is shown; with the same day and no popup this checks the date without mutating selection. Once close starts, `_closing` suppresses date refresh on activation. No popup is opened in this scenario.
- This rules out direct periodic midnight refresh as the expected active operation in this scenario. It does **not** rule out timing or allocation sensitivity introduced by the extra timer/handler, nor any unchanged native worker defect.

## Relationship to the older stall

The retained #13 limitation is a Linux Qt 6.11.1 asynchronous journey hanging during a different manual event-pump loop. Its controlled diagnostic abort stack identifies `journey-smoke.py` line 136 (QTest.qWait) during a multi-date search, not a close-specific failure. The new incident is a Windows lifecycle-test `cache_close` timeout. No captured failing Windows thread stack has yet been provided to this reviewer. Shared use of `QTest.qWait` is a useful lead, not proof of a common cause. Do not label the Windows failure a known baseline issue solely from this evidence.

## Targeted diagnostic plan

1. Keep the original failed run/log alongside every subsequent pass. Use a predetermined paired exact-#13/#14 execution with the identical unchanged scenario, Python/Qt build, OS and isolated runtime. Keep the original 30-second limit. A Linux pass cannot resolve a Windows-only observation; one paired pass cannot estimate an intermittent failure rate.
2. If an instrumented run is necessary, retain the original harness separately and add a diagnostic wrapper with an all-thread `faulthandler.dump_traceback_later(10, repeat=False)`. Timestamp phases immediately before and after each event-pump call, `window.close()`, native-completion observation, and final disposal. Do not hold extra worker/thread wrappers; retention can hide the original lifetime issue. A recorded stack plus last completed phase can distinguish waiting in qWait/processEvents, in a Python callback, or after all worker assertions during disposal.
3. A separate timer-driven QApplication.exec counterpart can test whether ordinary application event delivery also stalls with the same gated close sequence and destruction assertions. It is supplemental evidence, not a replacement pass for the failed manual-pump scenario. Preserve unchanged timeout and all original assertions.
4. If paired source runs remain clean, report failure reproduced in CI only, source attribution unresolved, and no justified production fix. Do not relax timeouts, remove assertions, pin dependencies, or rerun until green.

Confidence is high in the byte/AST and scenario call-path analysis. Confidence in causal attribution is currently insufficient. This follow-up made no application or test edits and performed no workflow dispatch, release, network/provider action or sandbox change.
