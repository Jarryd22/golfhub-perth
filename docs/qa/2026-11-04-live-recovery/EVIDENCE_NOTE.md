# Live recovery evidence

The real single-date cache-miss controller path was reproduced on exact PR23
`50ae64a00b4372d1f8c33dd787c2d5406510da2e`. With no saved results, an outer
`ScanWorker.run()` executor-setup failure emitted the real `failed` signal. The
old view still said **Checking courses live...** while its header, status and
intercepted modal incorrectly claimed cached results were preserved.

The same probe against the repair replaces that view with **Could not load
tee-time results. Try Find Tee Times or Refresh Live again.** The header says
**LIVE REFRESH FAILED**, and the status says **Live refresh failed - no results
available**. Search remains enabled, progress is hidden, and no results are
invented or saved. Both probes had zero callback errors.

- [Before JSON](before/cold-failure-probe.json) and [1280×800 image](before/cold-failure.png)
- [After JSON](after/cold-failure-probe.json) and [1280×800 image](after/cold-failure.png)
- [Reusable probe](cold-failure-probe.py), [before log](before-probe.log), [after log](after-probe.log)
- [Read-only source overlap audit](failure-source-overlap.json): the available
  local refs and preserved loose source have the same old fatal-failure method;
  this audit did not fetch remotes or change that checkout.

The two images were visually inspected. The after image visibly replaces the
stale checking sentence with readable recovery guidance and removes the false
cache-preservation claim. Both action buttons remain visible. The pre-existing
date punctuation rendering is outside this repair.

## Identical-file regressions

Final `tests/test_live_recovery_states.py` SHA256:
`f443f88c94d698488af3ce9cef8c1a899a2aee10c41d936a002662afb60d74ae`.

| Source | Methods | Outcome | Evidence |
| --- | ---: | --- | --- |
| Exact PR23, Qt source `316ff3f3263828191298e63817e1e5d84cc2415dc45eeb9ea5e96b162b5af383` | 11 | 2 passed, 9 failed; 10 assertion failures because one method has failure/stop subtests; 0 errors/skips | [JSON](new-tests-baseline.json), [log](new-tests-baseline.log) |
| Repair working tree, Qt source `fc61c95941605ba2bb79608fdf619d988ca9e3037f595377b353c10be3bfbfc3` | 11 | 11 passed; 0 failures/errors/skips | [JSON](new-tests-after.json), [log](new-tests-after.log) |

The working-tree run records the checked-out parent commit; the source hash
identifies the uncommitted implementation actually tested. Root integration
verification records the final commit separately.

Coverage includes empty first-launch cache-to-live failure; cold cancellation;
previous multi-day results cleared by an actual new cache search before failure
or stop; retained single cards, saved bytes and original booking context;
retained lazy multi-day rows/date; retained static offline course links;
cancellation with existing cards and no partial save; successful retry; repeated
failure without duplicate empty frames; rendering `window.last_results` as an
aliased input; and closing without opening a dialog or replacing the body.

The initial test helper was accidentally named `fail`, shadowing
`unittest.TestCase.fail`. Its baseline run recorded 4 assertion failures and
6 errors; its repaired-source run passed 11 methods. The helper was renamed and
parameterized-journey cleanup made independent before the final identical-file
runs above. The [initial test copy](initial-fixture/test_live_recovery_states.py),
[baseline JSON](new-tests-baseline-initial.json),
[baseline log](new-tests-baseline-initial.log),
[after JSON](new-tests-after-initial.json) and
[after log](new-tests-after-initial.log) are retained, not counted as additional
final passing tests. No application behavior or expected result was weakened to
address that fixture error.

## Method and limits

These are Linux Qt offscreen tests with real source widgets and real worker
signals. Native thread construction and `moveToThread` are intercepted; the
actual worker executes synchronously with its executor failing before provider
work. Cache files use isolated temporary directories. Socket/DNS/provider and
weather access are blocked. Browser calls are intercepted, booking-plan choice
is cancelled, and booking-assist dialogs are blocked. Failure/cancellation must
not call the UI save function; successful retry observes a mock save only.

The cold probe was copied byte-for-byte from the scratch reproduction recorded
before implementation, preserving its original timestamp. This work does not
test native Windows/Android, real provider failure frequency, native worker
timing, screen readers, live booking or notification delivery. It neither
reinvestigates nor resolves the historical Windows `cache_close` timeout.
