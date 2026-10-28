# Read-only gap review — October 28

Confirmed on exact PR16 `62d1b1c569e3a47004ef85eb6de9133054f354d2`, with unchanged source and no callback errors. [Probe JSON](probe.json), [source provenance](provenance.json), [screenshot](one-time-plus-full-calendar.png). The script invokes rendering directly; its pending controls do not represent the synthetic submitted result context.

## Focused count defect

With one exact tee-time row at Araluen and no rows at Wembley, the status says **1 matching tee time across 2 courses** for each Wembley calendar state: `available`, `unreleased`, and `full`. There is exactly one TeeTimeCard and only Araluen has a row-bearing ResultCard. A full or unreleased Wembley calendar should not increase the number of courses with matching exact tee times.

Cause: `render_results()` derives `matched_course_count` from `live_count - no_match_count`. Calendar results are included in the former but excluded from the latter. Multi-day rendering already counts courses by filtered rows. This is a numerical result-summary defect, distinct from PR16's absent-snapshot wording and from provider availability collection.

Suggested regression matrix:

- One row-bearing course plus calendar-only `available`, `unreleased`, and `full`: count one matching course; keep calendar cards/actions visible.
- Only full/unreleased calendar and no exact rows: zero matching courses.
- Only available calendar: retain its existing calendar-availability summary/status, without inventing exact tee times.
- Multiple matching rows from one course: count once, even with Show all/first 12.
- Two row-bearing courses plus an empty/error/direct-link course: count two.
- Apply group/time filters so one row-bearing course becomes filtered-empty: count only the remaining matching course; respect submitted context despite changed pending controls.
- Unselected results do not affect counts; 9/18-hole and lazy multi-day behavior remains intact.

ResultCard renders tee-time cards only after error/calendar/direct-booking/empty branches. Current production constructors make those states mutually exclusive with exact rows; preserve this contract and avoid broad malformed-data behavior changes in this repair.

## Separate error-wording backlog observations

Provider failure in a loaded snapshot still produces a zero-match summary. Multi-day collapsed titles say **No matching live times** while expanded cards correctly say live times were unavailable. Collier's empty-card override additionally replaces the error meta with **No public tee times showing for this date**, alongside the correct error warning. These are reproduced presentation contradictions, but a broader error/partial-coverage wording decision should remain separate from the small numerical count fix.

No application edits, tests of a repair, live provider calls, bookings, notifications, production workflows, native Windows/Android testing or historical timeout reproductions were performed. No blocked actions.
