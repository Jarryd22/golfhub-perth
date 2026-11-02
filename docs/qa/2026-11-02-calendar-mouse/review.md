# Independent review — 2 November 2026

No blocking findings in the final application, mouse-regression or desktop-workflow diff against exact PR #21 (`9aa16f733458db871c2452a18a247536ab348498`). [Reviewed file hashes](review-metadata.json) identify the working-tree source; final commit and CI verification belong to the parent task.

## Correctness and scope

`MonthOnlyCalendar` fixes its first weekday to Monday, disables the week-number column and uses a weekday header row. For months beginning on Monday, the inspected actual Qt model includes a complete preceding week. The old formula instead treated that preceding row as days 1–7 of the displayed month. It therefore mapped real last-week dates into the following month and incorrectly rejected their mouse events. Conversely, a hidden preceding-month date within the booking bounds could pass the filter and navigate away.

The three added application lines subtract one extra week only for this zero-offset case. The existing `QDate.addDays()` operation handles month/year boundaries. Non-Monday month mapping is unchanged. The repair stays tied to the existing fixed Monday-first configuration; future changes to that configuration should update this mapping and its tests together.

Mouse press, release and double-click filtering still use the same path. Adjacent-month suppression, cell painting, disabled/minimum/maximum date handling, selected-date limits, keyboard activation, relative dates and midnight rollover are untouched. No provider, cache, worker, booking or lifecycle behavior changes. This is a correction to pointer-coordinate interpretation, not a new calendar interaction design.

## Regression review

All eight new methods were reviewed. Current-month click targets come from Qt's public `setSelectedDate()` cursor and `view.currentIndex()`, then use the real cell rectangle for QTest pointer delivery. This avoids copying the production arithmetic and distinguishes duplicated day numbers in the hidden preceding week from the visible current month. Assertions check the popup's separate chosen-date set, so moving the native cursor alone cannot satisfy them.

Coverage includes selecting/removing the last seven dates in Monday-start 28-, 30- and 31-day months; hidden preceding/following cells that are otherwise enabled and within bounds; all six non-Monday starting weekdays; disabled dates; weekday headers; month navigation; and a real app popup followed by Apply and intercepted search submission. Socket/browser and worker paths are blocked, and widgets are destroyed while QApplication remains alive. Existing keyboard/double-click regressions remain in the cumulative suite without relaxed assertions.

The final identical-file regression records were inspected: exact PR21 has four passing/four failing methods, with 24 failed assertion/subtest records and no errors/skips; the repaired working tree passes all eight. The separate settled grid probe changes from 23/36 to 36/36 successful actions with zero callback errors. These are distinct test/probe counts, not 44 new test methods. The reviewer did not rerun them.

## Visual and evidence review

The current 980×640 app-popup captures for March 2032 were inspected. Before repair, a successful click on 22 is highlighted while the attempted click on enabled 25 remains unselected. After repair, 25 is also highlighted and the chosen-date count rises from two to three. The source-widget layout is unchanged; this is synthetic Linux offscreen evidence, not native Windows/Android testing.

The unchanged app-window diagnostic subsequently presses Space on the same date. On repaired code that date was already selected by the mouse, so Space correctly toggles it off: `keyboard_selected_same_day=false` and its absence from `applied_dates` are expected toggle results in that diagnostic, not a keyboard regression. The dedicated `test_actual_app_popup_applies_last_date_to_submitted_search` separately verifies mouse selection followed directly by Apply and the submitted dates.

Initial probe failures involving the system Python environment, duplicate day-number targeting and unsettled layout geometry are retained by the evidence owner and must remain distinct from the final settled before/after result. The reviewer inspected the final tests and settled captures; it did not relabel earlier executions as passes. The separately reproduced offline-link issue remains deferred, outside this repair.

## Workflow and limits

The workflow diff only adds `test_calendar_mouse.py` to desktop push/PR path filters and the isolated-process module list. Permissions remain read-only. A repair `fix/desktop-*` push selects desktop tests; the application/workflow PR diff also selects the existing cache/integrity test workflow. Production cache/news push triggers remain `main`-only, alerts remain dispatch-only, and cache `workflow_run` listens only to the alert checker on main. All production workflow files and `test-cache.yml` are unchanged. No production trigger, dispatch, manual rerun, merge or deployment was performed by the reviewer.

CRLF-aware whitespace checking passed. Aggregate runtime tests, actionlint and exact-head all-event CI verification are owned by the parent task. Current cumulative checklist/backlog and the source-scope audit were read; the narrow fix does not duplicate the earlier keyboard, date or midnight work. The historical Windows `cache_close` timeout and canonical-source reconciliation remain unresolved. No repeated Linux lifecycle investigation, native device, screen-reader/DPI, updater, live booking or notification-delivery test was performed. Only review evidence was written by this reviewer.
