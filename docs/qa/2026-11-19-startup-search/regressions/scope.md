# Startup scheduling regressions

The final identical `tests/test_startup_cache.py` was executed against exact PR31 and the repair. It contains the seven original methods plus eight new startup-scheduling methods. The original `CachedStartupTests` class and module cleanup function are AST-identical to PR31; imports and the separate new class are the only test changes.

- **Baseline:** 15 run, ten passed and five failed, zero errors/skips. All seven original methods passed. [Result](baseline/result.json), [complete log](baseline/test.log).
- **Repair:** 15/15 passed, zero failures/errors/skips. [Result](repaired/result.json), [complete log](repaired/test.log).
- Final test SHA256: `f8d044df7d70854962b97ffab8039e85f0e9a921dfc030939699ca6d0b337d3a`.
- Baseline Qt SHA256: `e739043b8c4e60556cee1b713fe28464d2dc72242b39b02df4c99d8ffca94927`; repaired Qt SHA256: `531055544bc6cab4707d29a1293d4356e2852cb1426eb7955029b97c15d1cd35`.

The five baseline failures establish incorrect save date/round in two accepted-live orderings, unsubmitted edits becoming queued searches in two accepted-Find orderings, and a valid explicit queue being replaced by delayed startup. The repair checks the saved envelope and results, submitted player/date/round context, BOOK accessible date, absence of an extra cache request, queued request precedence and one start per intended worker. Normal saved startup still renders saved data and starts one shared-cache search. Invalid input, unsupported multi-date live requests, existing live ownership and closing guards leave scheduling unchanged; actual close before startup prevents work. Perth-date and pending scroll behavior remain checked.

These are real QObject workers/signals with inert thread mocks; worker bodies, sockets/DNS, browser/provider/weather/booking actions are blocked. Persistence is intercepted except for an isolated synthetic saved file, whose bytes must remain unchanged. Buttons use programmatic `click()` and controls use setters. The original 0ms initial and 100ms automatic timers execute through Qt event processing; this does not establish natural user timing, native worker behavior, live booking or notification delivery.

Final commands (each executed in a separate bounded subprocess with stdout/stderr retained as `test.log`):

```sh
/workspace/golfhub-perth/.venv/bin/python -X faulthandler /workspace/scratch/golfhub-20261119-regressions/run-startup-tests.py --root /workspace/golfhub-20261117-repair --test-file /workspace/golfhub-20261119-repair/tests/test_startup_cache.py --output /workspace/scratch/golfhub-20261119-regressions/baseline
/workspace/golfhub-perth/.venv/bin/python -X faulthandler /workspace/scratch/golfhub-20261119-regressions/run-startup-tests.py --root /workspace/golfhub-20261119-repair --test-file /workspace/golfhub-20261119-repair/tests/test_startup_cache.py --output /workspace/scratch/golfhub-20261119-regressions/repaired
```

The baseline test subprocess returned 1 for its five expected failures; the repaired subprocess returned 0. The outer evidence-collection command completed after recording these statuses. The subprocess bound remained 60 seconds. [Copied runner](run-startup-tests.py) and [byte-copy provenance](provenance.json) identify the original scratch paths; copying was not another test execution. Candidate records correctly retain HEAD PR31 plus the changed source hash because testing preceded the final commit.

## Preserved review-stage results and tool failures

The first test file used a fixed 180ms event-processing wait and produced the same ten-pass/five-fail baseline and 15/15 repaired result. Review identified a portability risk: slow initial layout could consume that fixed margin before starting the 100ms timer. The final helper waits for both owned startup timers to fire or be cancelled, with a one-second convergence bound using `QElapsedTimer` and short `QTest.qWait` calls. It then checks pending events and callback errors. Production timer intervals, all original tests and historical native-thread timeouts remain unchanged. The former file/results, [review note](pre-review-fixed-wait/review-note.json) and lossless compressed diff remain under `pre-review-fixed-wait/`; these are not extra unique test methods.

A read-only API inspection found `QTest.qWaitFor` absent in installed PySide6 6.11.2. Attempting its docstring raised `AttributeError` and the inspection exited 1. [Recorded output](capability-inspection.txt) explicitly identifies this as an introspection failure, not an application or unittest failure. No invocation of that unavailable method was attempted in a test.

The first evidence-copy command had a shell heredoc delimiter collision and failed before Python executed. [Copy note](copy-command-note.txt) preserves the tool-output transcription; the corrected copy used a distinct delimiter and verified every file byte-for-byte. No test or source was affected. Existing Qt stylesheet/offscreen warnings remain in the test logs. There were no fixture exceptions or callback errors in either final regression run.
