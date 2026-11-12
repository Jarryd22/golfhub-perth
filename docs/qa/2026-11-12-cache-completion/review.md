# Independent source review — 12 November 2026, Perth

No blocking correctness or scope finding in the reviewed cache-worker completion repair against exact PR28 `4616694b65bf50d481dfd985b94e0fc213c38f0a`. Reviewed hashes and comparisons are recorded in `review-metadata.json`; this review does not certify later edits or remote CI.

`CacheWorker.run` previously caught exceptions from each future's `result()` only. Executor construction/entry, submission, completion iteration and context exit could escape the Qt slot before the terminal signal. That signal feeds both the existing result recovery handler and `QThread.quit`, so containing these ordinary exceptions addresses an uncovered completion path. The supplied duplicate audit records the unchanged original implementation across 30 source refs, preserved loose source, older worktrees and archived candidates; prior cleanup ownership, malformed-cache, provider-message and UI recovery repairs do not add this guard.

## Correctness and boundaries

The final change wraps only the existing executor block in `try/except Exception`. The block itself is AST-identical, including each-future failure mapping to `None`; snapshot initialization and the existing terminal `finished.emit(snapshots)` are also unchanged. The emit remains outside the guard, once per normally returning invocation. There is no second signal in the handler, no retry or `finally` emission, and no catch of `BaseException`.

The handler preserves snapshots already inserted in the mapping. An exception after submission but before collection may still discard work from futures that completed but were not read; the change must not be described as preserving every completed future. Missing keys and explicit `None` both follow the existing callback contract: look for saved data for that submitted date, fall back to the existing live path for a single uncached date, or show partial/all-missing multi-date recovery. Queued/closing guards, native cleanup ownership and worker signal wiring remain unchanged. The guard does not promise that a hung executor returns or that an executor whose shutdown raises has stopped all native work.

## Regression evidence and fixture realism

Eight methods were added to the existing multi-day module. They cover constructor/entry and first/later submission failures, a completion iterator failing after one collected date, executor exit after collected results, ordinary future failure alongside success, string/empty date inputs, saved-cache reuse, single-date live fallback and multi-date official-link recovery. Every ordinary completion case asserts one emitted payload; the partial iterator case also verifies the retained payload object identity. The unchanged workflow already selects this module.

The fixture uses standard completed `concurrent.futures.Future` objects and controlled executor/context-manager seams. Except for the explicitly interrupted iterator, it exercises the normal `as_completed` function. This is appropriate fault injection for the exception boundary and payload contract, but it is not actual executor resource exhaustion or native-thread timing evidence. Callback integration uses the real `cache_finished` method, with local loading/live launch intercepted. The separate QThread probe and final journey diagnostics belong to their executing agent's evidence.

The identical final 20-method module on exact PR28 reports **14 passing methods** (12 existing plus two new compatibility methods), **six failing new methods**, and **nine failure records** across subcases, with zero errors/skips. The reviewed candidate reports **20/20 passing**, zero failures/errors/skips, on its first recorded run. These are inspected parent-run logs; this reviewer did not rerun them. Existing test/fixture function ASTs are unchanged; no assertion was weakened.

Only `CacheWorker.run` changes at runtime function-AST level; 107 other function ASTs are unchanged. All five workflows, shared-cache/provider/core code, course configuration, the lifecycle module and alert archive/manifest are byte-identical to PR28. No applicable ancestor/checkout AGENTS.md or .agents/skills directory was found.

## Limits and remaining verification

This reviewer performed source, AST and saved-evidence inspection only. No runtime or historical Windows diagnosis was executed. There was no provider call, booking/hold, notification, denied-route retry, production-history lookup, remote mutation or external action. No failure UI, native wait/timeout, ownership, retry or production behavior was rewritten. Successful fault containment does not establish the cause or repair of historical Windows `cache_close`; canonical desktop/mobile/runtime integration and native Windows/Android/device/delivery checks remain pending.

The parent owns the final aggregate, remote commit and all exact-head CI events/attempts, including failures or cancellations. No outstanding review blocker remains for the recorded hashes.
