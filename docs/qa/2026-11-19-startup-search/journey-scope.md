# First-launch timer observations and controls

The owned automatic startup refresh can replace an already accepted manual live search on exact PR31. This was reproduced with **real `QApplication.exec()` and the unchanged owned 0ms/100ms timers**, an actual Qt Refresh Live click, isolated saved-cache bytes and inert worker threads. The click is injected immediately after the initial saved-render callback; this establishes a reachable controller ordering, not its natural frequency or a native scheduling benchmark.

Before repair, the changed-controls case submits **3 January 2033 / 18 holes / four players**. Pending controls are then changed, without another search submission, to **4 January / nine holes / one player**. The 100ms timer remains active after the explicit click (about 99ms remained in the first clean observation), expires, and starts a cache worker while the live worker is still owned. Cache context replaces the live context. The old live row is then passed to the intercepted save function in a **4 January / nine-hole envelope**, despite its 18-hole label and 3 January source URL. BOOK's accessible date becomes 4 January too. In the unchanged-controls control, the extra cache request still starts, but date/round happen to remain consistent.

The [settled baseline records](before-settled/) retain both observations. Their exit-zero results mean the diagnostic completed cleanly, not that the product behavior passed recovery assertions. After repair, [both corresponding runs](after-settled/) pass all **seven named recovery assertions each**: one worker, no automatic cache owner, cancelled automatic timer, submitted context preserved, correct save envelope, correct BOOK accessible date and unchanged original saved bytes. The new [after script](startup_timer_after_probe.py) adds these assertions to the same fixtures and observations; the [compressed diff](after-only-assertions.diff.gz) preserves every addition.

Three independent controls use the same [control script](startup_controls_probe.py) against each source:

- Normal automatic startup: the real initial callback displays saved data; without an explicit search, the 100ms refresh still starts exactly once using the latest pending date/round/group controls. The Perth timer stays active.
- Close before the 0ms initial callback: no initial callback or worker starts; both startup timers and the Perth timer are inactive afterward.
- Close after initial saved rendering but before the 100ms refresh: the saved view was reached, then the window closes with no worker and no remaining startup/Perth timers.

These three controls pass **25 recorded assertions on baseline and 25 on repair**, with zero callback errors or fixture failures. Each normal-startup control additionally checks its thread mock's `start.assert_called_once()` outside the recorded assertion list. This is **five unique diagnostic cases**; it is not five additional unittest methods or native-thread coverage. The two manual-live scripts also include setup/start checks outside their seven named after-oracles. Formal regressions and aggregate counts are reported separately.

The settled 1280×800 changed-controls captures were inspected [before](before-settled/changed_controls/after-live-completion.png) and [after](after-settled/changed_controls/after-live-completion.png). Summary, course, exact row and actions fit. Pending nine-hole controls and the submitted 18-hole result coexist in both images by design. The corrected save envelope and accessible date are established by JSON, not a visible date change in those screenshots.

## Preserved execution history

The [original scratch evidence](before/) was copied byte-for-byte before later runs. Two initial executions hit their 15-second external bounds. A third, instrumentation-only execution hit a shorter 12-second bound. Phase output reached both startup observers; a four-second faulthandler dump showed the main `QApplication.exec()` frame. The fixture requested quit while inert worker references remained, so Golf Hub's normal close guard refused exit. This was a diagnostic cleanup failure, not a product freeze or the historical Windows timeout.

The correction writes the observation checkpoint, releases inert owner references only after observations, and then quits. No product code, injected action or startup interval changed; no timeout was increased. Both corrected executions completed at exit zero with no callback errors. Their original synchronous terminal screenshots were not yet laid out, so they remain preserved without a product-layout claim. A separate [capture-only diff](before-capture-delta.diff.gz) defers capture by 20ms through a real timer. Both settled baseline executions, both after executions, and the three controls on each source complete cleanly. In total, this evidence retains **three fixture timeouts and 12 completed executions**, including repeated capture-only baseline observations; those repetitions are not additional unique cases.

## Commands and provenance

Original scratch command, executed once per `changed_controls` and `unchanged_controls` case before correction:

```bash
timeout --signal=TERM --kill-after=5s 15s /workspace/golfhub-perth/.venv/bin/python startup_timer_probe.py --root /workspace/golfhub-20261117-repair --case changed_controls --output changed_controls > changed_controls/run.log 2>&1
```

The instrumented and clean scratch commands use a 12-second bound, with outputs under the named history directories. From this dated evidence directory, settled baseline and repair commands are:

```bash
timeout --signal=TERM --kill-after=5s 12s /workspace/golfhub-perth/.venv/bin/python startup_timer_settled_probe.py --root /workspace/golfhub-20261117-repair --case changed_controls --output before-settled/changed_controls > before-settled/changed_controls/run.log 2>&1
timeout --signal=TERM --kill-after=5s 12s /workspace/golfhub-perth/.venv/bin/python startup_timer_after_probe.py --root /workspace/golfhub-20261119-repair --case changed_controls --output after-settled/changed_controls > after-settled/changed_controls/run.log 2>&1
```

Each is also executed with `unchanged_controls` and matching output paths. Control commands use `startup_controls_probe.py`, each of `automatic_latest_controls`, `close_before_initial`, and `close_between_callbacks`, the same source roots/bound, and `controls-before/<case>` or `controls-after/<case>` output/log paths. [Provenance](journey-provenance.json) records all relative artifacts, hashes, source roots, counts and initial failure history. PR31 baseline runtime hash is `e739043b…`; tested repair runtime hash is `53105554…`. Both worktrees began at `23defe0`, so runtime hashes distinguish the uncommitted repair.

Initial saved data is read from an actual isolated synthetic file and its bytes stay unchanged. **UI persistence is intercepted**; no incorrect save reaches a real cache. Real Qt worker QObject terminal signals are used, but QThread objects are mocks and worker bodies never run. Provider/weather/network/browser, booking/hold and notification operations are blocked or intercepted. This does not test native Windows/Android, live availability, actual disk failure, delivery, natural race incidence or the historical Windows `cache_close` timeout. No restricted/denied route, remote write, docs-only publication or production workflow was attempted by these diagnostics.
