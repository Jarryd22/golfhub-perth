# Independent completion and journey evidence

The baseline is exact PR28, `4616694b65bf50d481dfd985b94e0fc213c38f0a`, in the unchanged November 8 worktree. Its app SHA256 is `cc56759453ab2b4f1793d44571f1e5d62b69fc251a9efa75d01911dcc7d13339`. Repair diagnostics used app SHA256 `09b17e1a6a89a164d96ed6fc82413d0fa9f64d37244736b225a1150a12736ca1` in the November 12 worktree, while its Git HEAD was still the PR28 parent. These source hashes identify the tested code independently of later documentation commits.

## Confirmed before and after

The [unchanged inert probe](inert-completion-probe.py) uses real QObject signals and existing cache-search UI callbacks, with an inert QThread substitute, inert executor and prepared futures. It never calls the shared-cache provider. [Baseline JSON](before-inert/probe.json) and [log](before-inert.log) retain five deliberately injected escaped exceptions: executor construction, context entry, first submission, iteration before any completion, and iteration after one collected snapshot. Every case emitted zero completion/quit signals, retained the cache reference and left `Checking shared cache for 2 days...` displayed. Normal success, one failed future and all failed futures each completed once, as controls.

[Repair JSON](after-inert/probe.json) and [log](after-inert.log) show all eight cases emitting exactly once and clearing the cache reference, with no callback errors. Four failures without collected data reach the existing unavailable guidance. The interrupted iterator retains its collected date and displays `1 of 2 dates loaded`. The three original controls retain their success/partial/unavailable behavior. The deliberate baseline exceptions are product-defect observations, not fixture execution failures.

The [real-QThread probe](qthread-completion-probe.py) keeps the actual worker, Qt thread and existing signal connections, replacing only the executor and provider work. Its three bounded scenarios are:

- **Setup failure, then retry:** baseline has no completion; repair emits an empty completion, finishes the thread, displays unavailable guidance, then a second submitted search succeeds. Repair observes two worker completions and two thread-finished signals across the failure and retry.
- **Iteration interrupted after one result:** baseline loses terminal delivery despite already collecting a snapshot; repair emits the collected date once and shows its two rows across one loaded day. One completion and one thread-finished signal are observed.
- **Newest search queued behind a failing request:** two newer contexts are submitted while the first executor is gated. Baseline remains on `Your updated search is next...`. Repair completes the failing request, launches only the newest January 6–7 context, preserves its four-player filter, renders four-spot rows and completes both workers. The discarded January 4–5 dates are never submitted to the inert executor.

[Baseline results](before-qthread/probe.json) record zero completions in all three scenarios; explicit fixture cleanup quits and joins each idle thread after observing the escaped exception, while clearing pending work so cleanup cannot initiate a new search. [Repair results](after-qthread/probe.json) record normal completion and reference cleanup in all three scenarios, with no explicit fixture intervention or callback errors. Full [before](before-qthread.log) and [after](after-qthread.log) logs are retained. These are Linux completion-signal checks; no native close-timing barrier or historical Windows investigation was added.

## Capture history and visual inspection

The first real-QThread pair completed as diagnostic executions, but its screenshots were grabbed immediately when cache references cleared. One queued-success image caught Qt layout mid-update. The original [script](immediate-frame-history/qthread-completion-probe.py), JSON, logs and PNGs are retained byte-for-byte under `immediate-frame-history/`; this is not labelled a failed product layout.

The second paired execution resolves only that capture timing uncertainty by processing eight additional Qt event cycles before recording the state/image. The [capture-only diff](qthread-settled-capture-only.diff) and hashes in [provenance](journey-evidence-provenance.json) record the change. Runtime source, failure injection, expectations, cleanup bounds and existing lifecycle tests were unchanged. Both executions have the same completion outcomes. No fixture execution failure occurred.

Visually inspected compact 980×640 before/after images show the stalled checking view becoming a readable unavailable message and `FIND TEE TIMES` button. The partial result image shows a truthful loaded-day count. The settled queued-success image shows the newest January 6 section and `2 of 2 dates loaded`; remaining card content is below the scroll viewport. That probe submits explicit contexts, so its pending controls intentionally remain at their constructor defaults; it is not evidence that pending controls were edited through mouse/keyboard. The existing date punctuation issue visible in these screenshots remains outside this repair's scope.

## Established journey replay

Four prior diagnostic scripts were copied unchanged from November 8. Their byte equality and hashes are recorded in [provenance](journey-evidence-provenance.json). All four execution logs finish successfully; none reports callback errors.

| Evidence | Observed result | Scope |
| --- | --- | --- |
| [50 filter combinations](journeys.json), [log](journeys.log) | 50/50 pass | Actual offscreen controls submit 9/18 holes × Any/1/2/3/4 players × five time presets; expected boundary rows and selected dates agree with the rendered synthetic data. Worker launch is intercepted. |
| [Five startup decisions](startup/startup-decisions.json), [log](startup.log) | 5/5 pass | No saved data, saved empty/error data, single missing-cache fallback and multiple missing-cache guidance; scheduled/live work intercepted. |
| [Course-panel count/input](course-count/probe.json), [log](course-count.log) | 14 observed states show the pending count; six compatibility checks and seven submission decisions pass | Actual mouse/Space toggling, zero/one/many selections, name-filter-hidden choices, zero visible name matches, Select visible and 18→9→18 compatibility. QAccessible names queried; searches intercepted. |
| [Configured result grid](grid/probe.json), [log](grid.log) | Four show-all/booking/collapse controls pass; resize widths match | Configured Araluen synthetic 15-row data: 12→15→12; fifteenth BOOK action sends the expected row URL only to a browser mock. After wide→narrow, active columns are 337/336 pixels and obsolete column is 0, matching a fresh narrow grid's 337/336. |

Visual inspection also confirms one selected course remains visible on the closed-panel button, and the resized grid uses both active columns with visible booking buttons. These diagnostics supplement the parent's regression/aggregate counts; they are not additional unit-test methods and should not be added to that total.

## Source review and limits

Baseline `CacheWorker.run` is AST-identical to the dirty loose checkout's method. Prior cache UI/malformed-payload/provider-error repairs address outcomes after delivery, and the previous lifecycle executor failure fixture targets `ScanWorker`, not this cache setup boundary. The parent's [duplicate audit](cacheworker-duplicate-audit.json) supplies the wider branch comparison. Source inspection of the repair found only the outer `CacheWorker.run` guard added around the existing executor block; no filter, layout, timeout, worker ownership, cache validation, fallback or booking implementation changed.

All new completion inputs are synthetic failures on real reachable executor boundaries, not observed production incidents or claims about their frequency. Sockets/DNS, providers, weather, persistence, browser navigation and booking dialogs were blocked or intercepted. Temporary runtime directories were cleaned; all probe processes completed. No application/test/workflow edits were made by this evidence task.

Native Windows/Android, packaged runtime parity, real provider availability, live booking/holds, screen-reader operation and notification delivery remain unperformed. The historical Windows `cache_close` timeout remains unresolved and is not attributed to or declared fixed by this repair. Canonical source reconciliation and existing dirty-checkout changes remain separate. No new denied or uncertain action occurred in this evidence work; historical access restrictions were respected.
