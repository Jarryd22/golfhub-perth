# Validation of the final thread cleanup candidate

The final app SHA-256 is `97b08fc865c67e7fea5f660f39a9191bf00f924820a3ad55917067622723091d`; lifecycle tests SHA-256 is `1d85f1aa6e7002a7005aacdb479004d2650c115f949966235d3a7c966c903602`. Source hashes were checked before and after the uninstrumented smoke runs. No further app edits were made by this QA task.

The identical original asynchronous smoke harness (SHA-256 `e420a7930133b12c43454a426e11f4e271689b3cae353080674bdd2f3f2ee103`) passes all **18 checks in three fresh Qt 6.12 processes**, taking 1.089, 1.034 and 1.137 seconds. No synchronous-cache or retained-wrapper workaround is enabled. These include actual threaded cache searches, 25 player/time combinations, 28-day lazy expansion, offline/error states and layout checks.

On Qt 6.11.1, the first final-source run passes all 18 checks; the second **stalls in QTest.qWait** during the nonconsecutive-date search. It was terminated for a faulthandler traceback after the 25-second bound. The final attempts did not reproduce the earlier SIGSEGV, but the remaining stall is not a pass and its exact native cause remains unresolved. No repeated attempts were made to obtain a green Qt 6.11 result.

Four separate real `QApplication.exec()` probes pass: cache and live scan, each on Qt 6.12 and 6.11.1, **five completions per probe / 20 total**, with zero captured callback errors. This evidence is distinct from manual event pumping and from the deterministic native-finish regression suite maintained by the test agent.

A diagnostic copy with lifecycle tracing completes and captures **five real intervals where `wait(0)` is false although `isRunning()` is false and `isFinished()` is true**. Thread and worker references remain present until a later successful wait, then clear. This directly supports waiting for native completion rather than relying on `finished`/`isRunning`. The logging changes timing; its success does not explain away the uninstrumented Qt 6.11 stall.

Earlier hypothesis checks reject `@Slot()` or parenting alone as reliable fixes. The simpler destroyed-signal candidate also stalled in the real app. The rejected alternatives are summarized in [the diagnosis](../diagnosis/README.md); they are not included in final-candidate pass counts.

`stable-validation-summary.json` contains exact commands, source hashes, outcomes, tracebacks and artifact paths. Final logs are `stable-qt612-{1,2,3}/process.log` and `stable-qt611-{1,2}/process.log`. Real event-loop evidence is under `stable-loop-{cache,scan}-{qt612,qt611}/`. The successful traced diagnostic is [instrumented-qt611.log](instrumented-qt611.log).

All source tests use mocked cache/provider data, blocked sockets and intercepted browser opens. No native Windows/Android device, installed client, actual provider, booking or notification validation is claimed.
