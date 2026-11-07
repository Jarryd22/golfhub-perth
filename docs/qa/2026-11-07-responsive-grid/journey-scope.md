# Independent result-grid journey review — 7 November 2026

This is a confirmed **P3 visual-consistency defect**, not a demonstrated booking
blocker. Exact PR26 `2fa359011391f5307aeb60c0f18ba9370190d77f` leaves an obsolete
column with stretch after a three-column result grid narrows to two columns.
At an actual 683px grid width, 173px (25.3%) is assigned to that empty column.
Time, spot and BOOK labels remained readable; no clipping, inaccessible action
or failed live booking was established.

## Configured before, experiment and corrected final

The original [probe](pre-review/before/probe.py), [JSON](pre-review/before/probe.json),
[log](pre-review/before/probe.log) and [manifest](pre-review/before/before-manifest.json)
are preserved. The fixture uses configured Araluen with 15 synthetic cached
rows and an Any-player handoff. It renders at 1500×800, then narrows to 1100×800
with the course panel open; a separately constructed narrow view is the control.

| Same 683px grid | Column stretches | Measured column widths |
| --- | --- | --- |
| Exact PR26 after wide→narrow | 1, 1, 1 | 250, 250, 173 |
| Exact PR26 constructed narrow | 1, 1 | 337, 336 |
| Probe-only obsolete-stretch reset | 1, 1, 0 | 337, 336, 0 |
| Corrected final source after wide→narrow | 1, 1, 0 | 337, 336, 0 |
| Corrected final source constructed narrow | 1, 1 | 337, 336 |

The [probe-only experiment](pre-review/before/experiment/probe.json) changes
QGridLayout stretch values in memory on unchanged baseline source. It proves
the cause, not a source repair. The [corrected final replay](after/probe.json)
and [log](after-probe.log) run against final app SHA256
`9b35080c55f9a987ae0ecc204e8be5e23bddf3cb85f9b78af9ba464ef1d1cc0b`.

All four configured controls pass before and after: 12 rows initially visible;
actual SHOW ALL click exposes 15; actual 15th-row BOOK click passes that row's
URL to an intercepted browser call; collapse restores 12. Show-all/collapse
accessible names retain configured course, round and submitted-date context.
Browser navigation is intercepted and the Any-player path does not prepare
holds. No provider, worker or persistence activity runs.

The [original screenshot](pre-review/before/wide-then-narrow.png),
[final screenshot](after/wide-then-narrow.png) and
[fresh narrow control](after/fresh-narrow.png) were visually inspected. Final
cards occupy the same widths as the fresh view, while the row actions and
labels remain intact. The wider result cards are a layout consistency benefit;
no new button size, native accessibility or speed improvement is claimed.

The reusable [replay script](probe.py) adds only `--root`/`--output` support to
the original fixture. Original SHA256 is
`767333adc42085e7b38b9eed9999aabe31152db3408950d77e7e35561498976b`;
replay SHA256 is
`9d6dd7e5786eeeb1919ce7db398cae7dbadfa2cb7cf841b3348c9a70b414c0d9`.

## Initial-candidate blind spot and correction

The initial candidate iterated only existing `grid.columnCount()`. It passed
this 15-row diagnostic, the 50 filter combinations and five startup decisions.
Those fixtures did **not** cover sparse one-/two-card grids. Independent review
found that the initial change could skip initialization of computed but not yet
occupied columns, widening one card to 1200px instead of the previous 400px and
two cards to about 595px instead of 397px.

The [independent edge evidence](pre-review/independent-review/candidate-edge.json)
and [expanded-test failure](pre-review/expanded-tests.json) are preserved: the
eight-method file records three assertion failures across two methods on the
initial candidate, zero errors/skips. Its source hash is
`f4ad1f2870298f256e93df656a2db55336cdea58c7256129b571f613526824af`.
All original candidate outputs remain under `pre-review`; they are intermediate
results and are not counted as corrected-final evidence.

The corrected loop covers `max(columns, grid.columnCount())`, retaining the
previous initialization of computed columns while clearing obsolete ones.
The same dense configured/filter/startup scripts were rerun once on corrected
source, without fixture or assertion changes. Their passes still do not replace
the separate sparse compatibility regressions. Root's expanded regression and
aggregate records establish that additional coverage.

## Additional corrected-final diagnostics

[Script hashes](diagnostic-script-hashes.json) verify that the existing filter
and startup scripts were copied byte-for-byte. `journeys.py` uses its dated
directory depth to choose the source root; `startup-decisions.py` receives
explicit root/output arguments. Each final process completed once with exit 0
inside a 60-second bound.

- **50/50 filter combinations passed**, [JSON](journeys.json), [log](journeys.log):
  9/18 holes × Any/1–4 players × five time presets, actual submitted source
  controls, synthetic partial three-date cache and loaded-day/missing-date
  assertions. Worker launch is intercepted.
- **5/5 startup decisions passed**, [JSON](startup/startup-decisions.json),
  [log](startup-decisions.log): no saved data, saved empty/error data, single-date
  live fallback and multi-date missing-cache handling. Scheduled/live work is
  intercepted; this is not an actual network startup or worker timing test.
- The [980×640 diagnostic image](compact-980x640.png) was inspected; the expanded
  missing-date recovery note fits. No new layout or accessibility claim is made
  for native devices.

The [summary](diagnostic-summary.json) records four configured controls, 50
filter combinations and five startup scenarios separately from unit-test totals.
All have zero callback errors and matching corrected-final source hashes.

## Source scope and limits

The [AST/byte comparison](journey-source-scope.json) confirms only
`ResponsiveCardGrid._relayout` changes. Restoring that original method makes the
entire application AST identical to PR26. Column calculation, minimum widths,
spacing, row visibility, show-all behavior, booking handlers, all GolfHub methods
and both workers remain unchanged. Core/provider, course-result/cache and
booking files, all three production workflows, alert archive and manifest are
byte-identical. The archive was compared as bytes, not extracted or executed.

No applicable AGENTS.md or SKILL.md was found in the inspected checkout; absent
instruction directories were lookup results, not an access denial. All probes
used Linux Qt offscreen, isolated writable runtime paths and blocked sockets,
DNS, providers, weather, worker construction and persistence; browser calls were
intercepted. There was no live booking/hold, notification delivery, Windows or
Android device UI, native worker-timing, screen-reader, touch, DPI/resume or
updater validation. Historical Windows `cache_close` and canonical-source
reconciliation remain unresolved. No repeated Linux diagnosis, timeout change,
denied workflow-history retry/reroute or production action occurred here.

The separate course-panel count-visibility observation remains deferred; this
repair does not change selection controls or introduce a product redesign.
