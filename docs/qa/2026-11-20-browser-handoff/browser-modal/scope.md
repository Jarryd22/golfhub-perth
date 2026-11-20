# Real browser-warning modal evidence

The final source passes **four route/viewport cases and 68 recorded diagnostic assertions**: configured Altone Park VIEW COURSE and a synthetic Araluen MiClub-shaped manual BOOK URL, each at 1280×800 and 980×640. Browser calls are intercepted as `False` for failure and `True` for retry. Actual Space/mouse input invokes application handlers; a queued observer inspects the real QMessageBox, then Return on its actual OK button dismisses it.

On exact PR32, the [two direct-course baseline cases](before/probe.json) observe no warning after `False`. Their 18 assertions verify this baseline behavior and the subsequent `True` retry control; they do not establish that the intended recovery behavior was already present.

The [final direct](final/direct/probe.json) and [final long-URL](final/long_booking/probe.json) records verify exact title/body/address, visible modal state, PlainText, shown mouse-and-keyboard selection flags, mapped OK-button containment, readable existing palette, fit within the parent viewport, unchanged results and the same URL on a successful intercepted retry. Both processes start and end on runtime SHA256 `bbf50a77…`, with zero final failures, exceptions or Qt callback errors. These diagnostic assertions are separate from formal unittest counts.

The final [direct capture](final/direct/failure-modal-980x640.png) and [long-address capture](final/long_booking/failure-modal-980x640.png) were inspected. Their 1280×800 counterparts are byte-identical widget images; global placement differs in the JSON. The direct dialog is 353×125 and the long-address dialog 525×155. The longer exact address wraps and the complete body/OK action fits. Final OK text is `#090909` on measured `#f59e0b` background. Window title is checked by Qt property because these widget grabs exclude native window decorations.

## Focus and selection limits

**Automatic focus return did not pass in this offscreen environment.** The [first candidate run](after/probe.json) ended at exit one with two failed focus assertions—one per viewport—after otherwise successful real warning/dismissal checks. Retry was not reached. Its exact script, JSON, log and images remain retained.

A separate [plain Qt reference](plain-qt-reference/result.json), with no Golf Hub import or helper, also loses both `QApplication.focusWidget()` and `activeWindow()` after the same QMessageBox/OK-Return sequence. Explicitly activating the host restores its original button focus. Final retry therefore uses **documented explicit window reactivation**, which restores the source action before the mouse retry. The original automatic-focus failure is not relabelled as a pass. No application focus workaround was added, and native automatic focus remains unverified.

Final shown message/body flags are `3`, enabling mouse and keyboard text selection. This verifies the shown Qt properties, **not actual Ctrl+A selection, clipboard copy, screen-reader or native copyability**. No clipboard interaction occurred.

## Preserved intermediate findings

- Initial static-warning screenshots show a dark, low-contrast OK label. The subsequent local dialog style uses the application's existing dark-text/gold-button palette.
- [Styled direct](candidate-inspection/direct/probe.json) and [styled long-URL](candidate-inspection/long_booking/probe.json) observations pass 52 recorded checks across four cases, including explicit-reactivation retry. However, their shown flags are `5`, with keyboard selection false; those runs are intermediate evidence, not final selectable-text validation.
- The [plain Qt setter-order probe](flags-order/result.json) explains the flag reset: applying the stylesheet changes earlier flags from `3` to `5`. Moving the existing flag setter after the stylesheet leaves message and label flags at `3` after actual show/event delivery. This supported the narrow ordering correction.
- The original baseline script, geometry-coordinate correction, initial focus-failing script, plain references, activation/long-address instrumentation and final stronger oracles are retained. Compressed diffs preserve each script change. No existing formal test assertion was weakened.

There are **eight diagnostic process executions**: six UI probe processes (12 case executions including repeats) and two plain Qt reference processes. One process failed the two automatic-focus assertions; none timed out. The **final unique scope is four route/viewport cases**, not twelve new tests. [Provenance](provenance.json) records every run, source stage and artifact hash. Application regression/aggregate failures and results are recorded separately by the main task.

## Commands and scope

Original working directory: `/workspace/scratch/golfhub-20261120-browser-modal`.

```bash
timeout --signal=TERM --kill-after=5s 30s /workspace/golfhub-perth/.venv/bin/python modal_probe.py --root /workspace/golfhub-20261119-repair --output before > before/run.log 2>&1
timeout --signal=TERM --kill-after=5s 30s /workspace/golfhub-perth/.venv/bin/python modal_probe_geometry.py --root /workspace/golfhub-20261120 --output after --expect-warning > after/run.log 2>&1
timeout --signal=TERM --kill-after=5s 15s /workspace/golfhub-perth/.venv/bin/python plain_qt_focus.py > plain-qt-reference/run.log 2>&1
timeout --signal=TERM --kill-after=5s 15s /workspace/golfhub-perth/.venv/bin/python flags_order_probe.py > flags-order/run.log 2>&1
```

The two intermediate UI commands use `modal_probe_activation.py --expect-warning --route direct` or `--route long_booking`, with matching `candidate-inspection/<route>` output/log paths and the same 30-second bound. Final commands replace that script with `modal_probe_final.py` and use `final/<route>` paths. All scripts and evidence are copied unchanged from scratch into this directory; source hashes distinguish uncommitted intermediate implementations that share the starting Git HEAD.

Initial focus and OK focus are explicitly anchored; retry reactivates the window as described. This is not full keyboard traversal from launch. The long address follows the configured/tested MiClub URL shape with a controlled synthetic date, not live booking validation. Worker bodies, startup searches, persistence, provider/weather/network and booking/hold/dialog execution are blocked; browser dispatch is mocked. No native Windows/Android, real browser, clipboard, booking/hold, notification delivery or performance test was performed. No denied route, remote operation, workflow, security change or WebEngine sandbox bypass occurred. Historical Windows `cache_close` and canonical-source reconciliation remain unresolved.
