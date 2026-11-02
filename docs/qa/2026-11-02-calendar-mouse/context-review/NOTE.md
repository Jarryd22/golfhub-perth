# Independent calendar exploration — 2 November 2026, Perth

The clean baseline is exact PR #21, `9aa16f733458db871c2452a18a247536ab348498`. Cumulative checklist/backlog and the November 1 report were read before exploring course/date/keyboard transitions. Existing course selection/count/name-search, Perth rollover, keyboard date selection and retained booking context repairs were not duplicated. No new course-picker change was justified by this review.

## Confirmed mouse gap

When the displayed month starts on Monday, Qt's first grid row contains a complete preceding week. GolfHub's `_date_at_view_position()` instead interpreted that row as current-month days 1–7. Its adjacent-month event guard therefore treated valid late-month mouse positions as next-month dates and ignored them. The error also allowed a click on painted-over preceding-week padding to navigate/select an adjacent date when that date was in the allowed range.

This is distinct from PR #10's keyboard activation repair: keyboard activation uses Qt's selected date directly. Before the repair, the normal app popup could select the blocked date with Space and apply it. Existing adjacent-month tests used months that did not start on Monday.

The [static source comparison](source-comparison.json) finds the same hit-test method in the preserved loose checkout, so this is not a duplicate port of a known canonical fix. Only `_date_at_view_position` differs within `MonthOnlyCalendar` in the reviewed candidate. This does not resolve which desktop/mobile source is canonical.

## Evidence and counts

| Evidence | Exact PR #21 | Candidate |
|---|---|---|
| Settled isolated popup: 36 actual mouse actions, Monday-start March/November 2032 and August 2033 plus non-Monday January 2033 | 23 selected expected dates; 13 valid clicks ignored. All nine January controls passed. | All 36 selected expected dates. |
| Normal app popup: March 25 and November 24 at 980×640 and 1280×800 | Four earlier-date control clicks passed; all four target clicks ignored. | All eight mouse clicks selected their dates. |
| Keyboard action following each app mouse probe | Space selected the target in all four cases because mouse had failed. | Space deselected the target in all four cases because mouse had already selected it. This is expected toggle behavior; `keyboard_selected_same_day=false` in the after JSON is not a failure. |
| Identical final new regression module | Eight methods: four pass/four fail, 24 assertion/subtest failure records, zero errors/skips. | Eight pass, zero failures/errors/skips. |

Baseline grid evidence: [JSON](calendar-grid-probe.json), [log](calendar-grid-probe-settled.log). Repaired grid evidence: [JSON](after/calendar-grid-probe.json), [log](after/calendar-grid-probe.log). Normal app evidence: [before JSON](calendar-window-probe.json), [after JSON](after/calendar-window-probe.json). All confirmed probes reported zero Qt callback exceptions. These are diagnostic actions, not additional unit tests.

The actual app popup images for the 980×640 March case were inspected: [before](window-2032-03-980x640-mouse.png) shows only March 1 and 22 selected; [after](after/window-2032-03-980x640-mouse.png) also highlights March 25 and shows three selected dates. These are 440×478 popup captures from the stated logical window size. No clipping/layout or native accessibility conclusion is implied. Other captured images were not visually inspected by this reviewer.

The eight regression methods cover 28-, 30- and 31-day Monday-start months, selection/removal, preceding/following padding mouse/double-click actions, all six non-Monday starts, disabled date bounds, header clicks, next-month navigation and the normal app popup's accepted dates reaching submitted search parameters. Tests obtain actionable cells from Qt's actual `currentIndex()` after focusing the target date, independently of the application's date-position formula. Final test hash: `e046b5511d05345be8dc197c7867b7872b9fd107b7570cc5f2569b5327b54530`. [Baseline metadata](../new-tests-baseline.json), [after metadata](../new-tests-after.json), [runner](../run-calendar-tests.py).

## Retained exploratory failures and corrections

1. The initial system-Python execution failed before importing application code because PySide6 was not installed for that interpreter. [Log](calendar-grid-probe.log). The saved environment's `/workspace/golfhub-perth/.venv/bin/python` was then used. This was an environment/tooling failure, not a product failure or access denial.
2. The first runnable probe selected the first matching numeric label, which could be a preceding-month duplicate. Its 20-action/13-selected result is not valid evidence for seven product failures. [Initial script](calendar-grid-probe-initial.py), [JSON](calendar-grid-probe-initial.json), [log](calendar-grid-probe-venv.log).
3. The enabled-cell correction still used changing, insufficiently settled popup geometry. Its 36-action/19-selected result is not the confirmed defect count. [Unsettled script](calendar-grid-probe-unsettled.py), [JSON](calendar-grid-probe-unsettled.json), [log](calendar-grid-probe-corrected.log). Fixing popup size and settling eight event passes before/after actions produced the stable 36-action baseline above; the normal app popup then independently confirmed it without a fixed-size override.

The confirmed diagnostic scripts later gained explicit source/output arguments for the repaired run; the original scratch history and copied initial scripts/data remain preserved. No regression-test assertion was weakened, and the first final regression module passed all eight methods against the repaired source without fixture corrections.

## Boundaries

All execution used Linux Qt offscreen source widgets, isolated temporary application paths and fake dates. Sockets, DNS, browser calls and cache/live worker construction were blocked. Normal app construction intercepted `show_initial_cache`, then stopped owned timers. Mouse coordinates and accepted/submitted dates were exercised; no provider request, booking/hold, shared-cache watch or notification occurred.

Installed Windows/Android, native screen readers/DPI/resume, complete network/offline startup, release/updater checks and notification delivery remain unperformed. Historical Windows `cache_close`, canonical reconciliation and existing weather/freshness/alert-source limits remain pending. No repeated Linux timeout investigation, production workflow, remote write or third-party contact was performed by this reviewer. No denied, pending or uncertain action remains.
