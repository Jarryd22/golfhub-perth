# Desktop worker lifecycle follow-up — 20 October 2026 Perth

The desktop releases its cache and live-worker references before native thread cleanup is guaranteed to finish. The repair retains both objects until a zero-timeout `wait(0)` succeeds, then schedules thread deletion and continues the queued search or close. One owned timer per pipeline retries after 10 ms without blocking the GUI. Close waits for outstanding workers, and new searches cannot start during closing or replace a live worker still being cleaned up.

This is a separate repair stacked on unchanged PR #12 (`93d4763451358be608bff06fd0013936af36764c`), after #9–#11. It does not revise #12, merge anything, change dependencies, alter booking behavior, deploy or publish. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`.

## Evidence and diagnosis

- The [exact paired comparison](baseline-comparison/comparison.json) used clean #11 `6d60354a90d7a32807a3f7867cb9180d449433ce` and #12 `93d4763`, the identical committed asynchronous journey harness, identical phase/environment and reset runtime directories. Both spontaneously exited SIGSEGV on their first search: 0.640 seconds / 0.702 seconds. The main Python stack points at `self.cache_thread = None`; the crashing native thread has no Python frame. The callback function AST is identical. [Base log](baseline-comparison/base.log), [head log](baseline-comparison/head.log).
- The [duplicate audit](diagnosis/remote-duplicate-scan.json) found identical lifecycle methods on main and all 13 existing code repair/agent refs. PR #10's [cleanup diff](diagnosis/pr10-cleanup-diff.json) changes fixture teardown only. No existing application lifecycle repair was duplicated.
- A [QtCore-only reproducer](diagnosis/minimal-ownership.py) also crashes with both Qt 6.11.1 and 6.12.0, including real event loops. Merely parenting QThread is insufficient. Actual completion callbacks already run on the GUI thread. These observations do not establish a Qt-6.12-only defect, justify a dependency pin, or establish that missing slot decorators caused the crash.
- Minimal polling variants complete and destroy 800 worker/thread pairs under Qt 6.12 and 400 under 6.11 across manual and real event loops; deliberate delayed-cleanup variants complete another 60 pairs. These are stress iterations, not extra app test cases. [Experiment results and rejected alternatives](diagnosis/README.md).

Qt documents that a thread can still perform native cleanup after `finished` and that successful `wait()` synchronizes completion. The application retains the documented `finished → worker.deleteLater` connection while taking control of QThread deletion order. The evidence supports a lifetime overlap; no precise failing C++ instruction or installed-device crash rate is claimed. [QThread completion documentation](https://doc.qt.io/qt-6/qthread.html#isFinished), [QObject deferred deletion](https://doc.qt.io/qt-6/qobject.html#deleteLater).

## Regression results

| Check | Untouched PR #12 | Repair |
|---|---:|---:|
| Identical 11 real-worker subprocess tests | 5 pass, 6 fail | 11 pass on Qt 6.12; 11 pass on Qt 6.11 |
| Focused desktop suite | Prior #12: 51 pass | 62 pass |
| Offline cache suite | Prior #12: 43 pass | 43 pass |
| Workflow syntax, compile and CRLF-aware whitespace | — | Pass |

The five deterministic native-finish tests hold a real `finished` receiver while `isRunning()` is false and `wait(0)` is false. On the base, GUI progress blocks until the five-second fixture bound expires. On the repair, a GUI timer fires while both references remain alive; no queued request, replacement live worker or close can race cleanup. The sixth baseline failure is a live refresh accepted after closing began. Other cases cover sequential destruction counts, newest queued context, active close, live success/failure, cancellation and preservation of cached data. All networking and browser calls are blocked. No retained history of worker wrappers masks cleanup failures.

Logs: [baseline](validation/lifecycle-baseline.log), [Qt 6.12](validation/lifecycle-qt612.log), [Qt 6.11](validation/lifecycle-qt611.log), [105-check focused summary](validation/summary.json), [static checks](validation/static-checks.json). The standalone [verification runner](run-focused.py) records the source/test hashes and commit. Windows CI now selects the new lifecycle module alongside the existing desktop tests.

Tested source SHA-256: `97b08fc865c67e7fea5f660f39a9191bf00f924820a3ad55917067622723091d`.
Test module SHA-256: `1d85f1aa6e7002a7005aacdb479004d2650c115f949966235d3a7c966c903602`.

## Original asynchronous journey and limitations

The unchanged asynchronous 18-journey harness passes in **three fresh Qt 6.12 processes** (1.089 / 1.034 / 1.137 seconds). On Qt 6.11, one run passes all 18 checks and the second stalls in `QTest.qWait` during the nonconsecutive-date search. The owned test process was aborted for a traceback after 25 seconds; this is a controlled diagnostic abort, not a spontaneous SIGSEGV. No further Qt 6.11 attempts were made to obtain a pass. The remaining native cause is unresolved. [Exact commands and outcomes](journeys/stable-validation-summary.json), [retained stalled-run log](journeys/stable-qt611-2/process.log).

Four real `QApplication.exec()` probes—cache and live scan on both Qt versions—pass five completions each, with zero captured callback errors. These 20 completions are separate evidence, not 20 new unique regression cases. A traced diagnostic captures real `isRunning=false`, `isFinished=true`, `wait(0)=false` intervals; tracing changes timing, so its success does not clear the uninstrumented stall. [Validation summary](journeys/stable-validation-summary.md), [real-loop probe](journeys/app-loop-probe.py).

The focused lifetime repair is supported by reproducible failures and final successes. **All threaded QA is not clear:** retain the Qt 6.11 manual-pump stall in the backlog and verify the intended packaged Windows source before claiming installed-client recovery. No native version-specific cause is established.

The original harness SHA-256 is `e420a7930133b12c43454a426e11f4e271689b3cae353080674bdd2f3f2ee103`. It is the unchanged [20 October journey harness](../2026-10-20/journey-smoke.py), with real cache QThreads, synthetic providers, blocked sockets and intercepted browser calls. Neither synchronous delivery nor wrapper-retention flags are used for lifecycle validation.

This follow-up does not repeat the hourly production audit, update-repository inspection or alert delivery checks. Their earlier evidence remains in the [daily report](../2026-10-20/REPORT.md). Windows 5.1.17 and Android 0.1.19 metadata were unchanged; no installed client or device was tested. Four WebEngine cases remain blocked by the cloud sandbox helper, and the obsolete cron assertion remains a baseline failure outside the focused suite. No sandbox protection was disabled.

Canonical desktop/mobile source reconciliation, truthful per-course freshness and alert-source completeness remain separate prioritized work. The unavailable newer Windows checkout remains untouched; it must be preserved and reviewed before integrating source repairs into a supported release. Native Windows/Android, screen readers, installed-updater behavior, live provider recovery and device alert delivery remain unverified.
