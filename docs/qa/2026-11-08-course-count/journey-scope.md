# Course-panel input and independent journey review — 8 November 2026

This is a **P3 information-visibility repair**, not a selection-data or booking
repair. Exact PR27 `405cbec95ed5b9fc84e23dba9fb64a7df98a29bf` starts with the
pending count on the closed course button. Closing the panel later replaces it
with CHOOSE COURSES while the separate selected-count label becomes hidden.
Selection data and intercepted search decisions remain correct before and after.

## Actual-input reproduction

The identical [probe](course-count-probe.py) ran once on each source, using real
Qt mouse clicks, focused Space activation, checkbox clicks, name-query typing,
Clear/Select visible and 9/18-hole controls. Its search button invokes actual
`search_cache`/`params`; `_start_cache_search` is intercepted so no worker or
provider request runs. The fixed Perth fixture date is 2 January 2033.

[Before JSON](before/probe.json), [before log](before/probe.log),
[after JSON](after/probe.json), [after log](after-probe.log),
[original artifact hashes](before-manifest.json).

| Recorded closed state | Pending count | Exact PR27 button | Final button |
| --- | ---: | --- | --- |
| Many courses, closed with Space | 37 | CHOOSE COURSES | COURSES 37 OF 41 |
| Cleared selection, closed with mouse | 0 | CHOOSE COURSES | COURSES 0 OF 41 |
| Araluen checkbox selected, closed with Space | 1 | CHOOSE COURSES | COURSES 1 OF 41 |
| Name filter hides selected Altone, closed with mouse | 2 | CHOOSE COURSES | COURSES 2 OF 41 |
| Name filter has no visible matches, closed with Space | 2 | CHOOSE COURSES | COURSES 2 OF 41 |
| 9-hole selection, closed with Space | 2 | CHOOSE COURSES | COURSES 2 OF 41 |
| 18-hole selection reopened and closed with Space | 2 | CHOOSE COURSES | COURSES 2 OF 41 |

The separate count label is hidden in all seven states. Actual Qt accessible
Name follows the button text, so its count is restored too; this is Qt interface
inspection, not a native screen-reader or announcement test. Initial closed
state and a round change while closed already showed the correct count and
remain unchanged. Immediate opening still says HIDE COURSES with the separate
count visible. Existing selection-change labels inside the open panel remain
unchanged.

All **14 recorded states** now expose a count, versus seven missing it on the
baseline. Six compatibility journeys pass on both sources. Seven search
decisions are identical: six nonempty intercepted submissions and one existing
zero-course guard. In particular:

- Zero selection opens the existing "Select at least one course" information
  message and launches nothing.
- A filtered-out selected Altone remains submitted with Araluen, even when the
  name query has no visible matches.
- Araluen, Chequers and Embleton remain checked across 18→9→18 input; 9 holes
  submits Araluen/Embleton, while 18 holes submits Araluen/Chequers.
- Every mouse/Space toggle preserves the checked set and query; submitted date
  and round agree with the controls.

Before/after zero- and one-course [compact images](after/one-closed.png) were
visually inspected at 980×640. The two baseline views have the same CHOOSE
COURSES button despite different selections; final views show 0 and 1 clearly
without changing geometry, colors or introducing a new interaction. The useful
benefit is seeing the pending selection size without reopening the panel. No
booking-completion, speed or native accessibility improvement is claimed.

## Prior coverage and scope

A separate read-only comparison found that the original eight-method
`tests/test_course_controls.py` had remained unchanged since PR11. Its setup
opens the panel, and count assertions follow checkbox, Space, row, bulk,
filter and round changes; none checks count visibility after closing/reopening.
This repair therefore does not duplicate the PR11 count-signal fix.

The [AST/byte comparison](journey-source-scope.json) finds only
`GolfHub.toggle_courses` changed. Restoring that method makes the entire app AST
identical to PR27. The close branch reuses `update_selected_count`; selection
calculation, name filtering, eligibility, submission, course rows, result grid
and both workers are unchanged. Core/provider, cache, booking, desktop test
workflow, all three production workflows, alert ZIP and manifest are byte-
identical. The archive was compared as bytes, never extracted or executed.

Final application SHA256:
`cc56759453ab2b4f1793d44571f1e5d62b69fc251a9efa75d01911dcc7d13339`.
The before/after count script SHA256 is
`9de3cd8c6ddc0a77169a0158faa043cd121ceba3ed8ebabebc424ff6f4aedb0f`.
Root's expanded regression and aggregate results are separate from these
diagnostic observations.

## Additional final-source checks

Existing scripts were copied byte-for-byte; [hashes](diagnostic-script-hashes.json)
identify all four. Each final process completed once, exit 0, under a 60-second
bound. All record the same final source hash and zero callback errors.

- **50/50 filter combinations**, [JSON](journeys.json), [log](journeys.log):
  9/18 holes × Any/1–4 players × five time presets, real submitted controls and
  synthetic partial multi-date rendering. No worker executes.
- **5/5 startup decisions**, [JSON](startup/startup-decisions.json),
  [log](startup-decisions.log): no saved data, saved empty/error, single-date
  fallback and multi-date missing cache. Scheduling/live work is intercepted.
- **4/4 prior result controls**, [JSON](grid/probe.json), [log](grid-probe.log):
  first twelve rows, show all fifteen, intercepted fifteenth-row BOOK target,
  collapse. PR27's 683px grid still uses 337/336/0 after narrowing, matching
  fresh narrow 337/336. The [1100×800 image](grid/wide-then-narrow.png) was
  inspected. This dense-grid spotcheck does not replace PR27's separate sparse
  compatibility regressions or erase its retained initial review failure.

The [summary](diagnostic-summary.json) keeps states, compatibility journeys,
search decisions and these diagnostics distinct from unit-test totals.

## Limits and execution history

All evidence is Linux Qt offscreen source-widget work with temporary runtime
paths, blocked socket/DNS/provider/weather access, no actual worker/persistence
and intercepted browser handoff. No installed/native Windows or Android,
screen reader, touch/DPI/resume, real provider startup, booking/holds,
notification delivery or updater validation was performed. Historical Windows
`cache_close` and canonical-source integration remain unresolved. No repeated
Linux timeout diagnosis, test relaxation, production workflow/history access,
denied-route retry/reroute or other external action occurred.

The before probe, final count replay and three additional diagnostics all
completed successfully without callback or fixture errors. An initial read
guessed `tests/test_course_selection.py`, which does not exist; file discovery
identified `tests/test_course_controls.py`. That lookup miss and the absent
instruction-file searches are not runtime test failures or access denials. No
uncertain write was retried. The actual baseline visibility defect and root's
expected failing new regressions remain distinct from the passing compatibility
checks.
