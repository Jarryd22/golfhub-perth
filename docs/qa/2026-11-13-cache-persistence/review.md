# Independent source review — 13 November 2026, Perth

No blocking correctness or scope finding in the reviewed cache-persistence repair against exact PR29 `8dff803ebc6e61b1a309d7c17c5277909392f5d2`. Reviewed hashes and comparisons are recorded in `review-metadata.json`; this review does not certify later edits or remote CI.

The original `fetch_shared_snapshot` combines download, validation and local persistence under one outer error handler. A local `OSError` therefore returns `None` even after obtaining usable, validated shared data. The narrow inner handler now treats failure to save that local copy separately and returns the payload already validated for the requested date/round. The outer download/parsing/validation handlers and their ordering remain unchanged. The inner handler covers only `save_local_snapshot` and catches only `OSError`; it does not accept malformed data or broadly suppress other programming errors.

## Persistence and UI semantics

The save helper is unchanged: it creates the directory, writes the temporary file and replaces the destination. The injected directory/write/replace tests confirm that an existing saved `.json` remains byte-identical where present, while the caller receives the fresh payload. This is preservation of the old saved data, not proof that the fresh payload became durable. Fresh data may remain available only for the current request; a later offline start can still use the older file or have no saved data. Failed replacement can leave a `.tmp` file under the existing helper's behavior; its cleanup, concurrent-write behavior and physical-storage guarantees are outside this patch.

The UI tests exercise actual fetch/validation and existing cache completion callbacks with local I/O failures injected. A fresh four-player row takes precedence over an older two-player saved row, with and without a saved file. Multi-date results remain loaded rather than becoming missing-cache states. The header remains `SHARED CACHE`, so the repaired path does not relabel unsaved shared data as `SAVED CACHE`. Live fallback is intercepted and is not called when shared data was usable. No worker, booking, filtering, retry or save-mechanism rewrite is introduced.

## Regression evidence and unchanged scope

Four added cache tests cover directory creation, temporary-write and replacement failure, preservation of existing bytes and later successful persistence. Two UI methods cover single-date saved/missing cases and multi-date rendering. They use isolated real files and injected `OSError`/`PermissionError`, with mocked HTTP responses; this does not reproduce an actual full disk or native permission configuration. Existing validation/invalid-payload/local-roundtrip tests remain unchanged and protect the earlier malformed-cache repair.

The identical final cache module on exact PR29 reports **10 passing / four failing methods**; the UI module reports **five passing / two failing methods**, with three UI assertion records across subcases. Both have zero errors/skips. Candidate results are **14/14 cache and 7/7 UI**, zero failures/errors/skips. These are inspected parent-run logs, not tests executed by this reviewer. All original test and fixture function ASTs are unchanged; no assertion was relaxed.

Only `fetch_shared_snapshot` changes at runtime function-AST level; nine other shared-cache function ASTs are unchanged, including validation, load and save helpers. The desktop UI (including PR29 worker completion), provider/core/shard code, course configuration, lifecycle tests, all five workflows and alert archive/manifest are byte-identical to PR29. Existing workflow selections already cover both expanded test modules. No applicable ancestor/checkout AGENTS.md or .agents/skills directory was found.

The supplied duplicate audit finds the original combined handler across 31 source refs and 16 readable known local sources. PR19 validates payload shape, PR29 contains executor orchestration failures, and pending canonical freshness/subset work changes other semantics; none supplies this persistence separation. This reviewer did not repeat that repository audit or revisit the unrelated denied `/tmp/codex-daemon-1000` search. No permission/security setting was changed.

## Limits and remaining verification

This reviewer performed source, AST and saved-evidence inspection only. No runtime experiment, lifecycle diagnosis, native/device check, provider call, booking/hold, notification, denied-route retry, production-history lookup, remote mutation or external action occurred. No production occurrence or frequency of these injected failures is established. Historical Windows `cache_close`, canonical desktop/mobile/runtime reconciliation, release-candidate integration and native/device/delivery limits remain unresolved or unperformed.

The parent owns final aggregate tests, remote commit and every exact-head CI event/attempt, including failed/cancelled outcomes. No outstanding review blocker remains for the recorded hashes.
