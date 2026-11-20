# Keyboard result expansion and lazy dates

One new keyboard sequence was exercised at **980×640 and 1280×800** on exact PR32 `66eaf00f76e748cf6f76ef6a758574a3d996360c`. The first execution completed at exit zero: **84 recorded assertions passed**, with zero exceptions or Qt callback errors. No probe revision, failed intermediate execution or runtime/test edit was needed. These are diagnostic assertions, not additional unittest methods.

The first date has 15 synthetic Araluen times; a second, initially unbuilt date has 14. From explicit header focus anchors, actual Tab/Space/ShiftTab input checks:

- The collapsed course exposes exactly twelve BOOK stops and the Show All action. Space reveals the rest; ShiftTab reaches the last newly revealed BOOK.
- BOOK dispatches the exact displayed final row. Collapsing to twelve keeps focus on the action; ShiftTab skips hidden rows 13–15.
- Collapsing the whole first date removes its BOOK buttons from the traversed focus sequence. Space on the second date builds its course once, with the expected twelve initial BOOK stops.
- The second Show All exposes all 14 rows. Its last BOOK keeps the submitted four-player/18-hole/date context after pending controls change to one player/nine holes/Afternoon/a later date.
- Three keyboard close/reopen cycles per viewport reuse the same course and row objects, introduce no duplicates, and preserve that course's expanded state. Reopened Tab navigation begins at its official-page action.

All **four BOOK callbacks** were intercepted at `window.open_tee_time`, before destination, browser, provider-plan or booking-dialog execution. No browser success/failure contract is inferred from these intercepts. Browser and external operations remain blocked. The [JSON](first/probe.json) retains named assertions, focus traces, context and counts; the [log](first/run.log) retains existing Qt warnings.

Both captures were inspected: [compact](first/expanded-980x640.png) and [ordinary](first/expanded-1280x800.png). They show the scrolled lower part of the expanded second date. Final-row BOOK and SHOW FIRST 12 fit at both sizes; the compact image intentionally starts partway through the rows. Header “CACHE READY” remains constructor copy because the fixture renders synthetic results directly, not because a cache fetch was verified. Pending controls intentionally differ from retained results. The known date-label encoding issue remains outside scope.

The existing tests check programmatic expansion, counts, names and responsive layout. The November 16/18 diagnostics also expand date sections programmatically. This pass adds actual focus traversal after visibility changes; it does not justify a new repair.

Original command from `/workspace/scratch/golfhub-20261120-expansion`:

```bash
timeout --signal=TERM --kill-after=5s 30s /workspace/golfhub-perth/.venv/bin/python expansion_probe.py --root /workspace/golfhub-20261119-repair --output first > first/run.log 2>&1
```

[Provenance](provenance.json) records exact source/script/artifact hashes. The runtime remains `53105554…`, and the source worktree stayed clean. Actual input begins at explicitly anchored focus points; pending course/filter values are fixture setters, so this is not full keyboard traversal from launch. Startup timers and workers are blocked/stopped. No native Windows/Android, screen-reader, live provider/browser/booking/hold, persistence, notification delivery or performance test was performed. Historical Windows `cache_close` and canonical integration remain unresolved. No restricted-route retry, remote mutation, production workflow or WebEngine sandbox change occurred.
