# Refresh Live availability: journey scope — 5 November 2026, Perth

This review read the cumulative checklist/backlog, PR #24's recovery report, existing journey tests and the current candidate. It ran the fresh 50-filter and five-startup diagnostics below, but not today's new regressions or aggregate suite. No applicable checkout/parent `AGENTS.md` or checkout `.agents/skills` instructions were found.

## Source and usability finding

Refresh Live must reflect the current date controls and whether the application can start another live request. Previously, successful/failed/stopped completion handlers enabled it unconditionally. A user could have selected multiple dates meanwhile, or the finished worker could still be owned until native cleanup completed. Replacing an `isRunning()` check with an ownership check also closes the interval where a thread reports stopped but `search_live()` still refuses a second launch because `scan_thread` remains set.

The candidate uses the existing `update_day_mode()` path consistently: enable only for one selected date, when not closing, with neither live nor cache thread still owned. Terminal handlers recompute instead of forcing enablement; cleanup recomputes after clearing the existing live thread/worker references. Ordinary course/time validation remains separate, so an enabled button is not a guarantee that every possible input is valid.

A related appearance gap was confirmed after the initial functional checks: the ID-specific outline-button rule overrode the generic disabled text color. The [recorded palette probe](style-selector-proof/probe.json) shows enabled and disabled Refresh Live both using `#f6f6f6`, while a plain disabled button uses the existing `#7d7d7d` faint color. Adding `QPushButton#OutlineButton:disabled` to the existing disabled rule restores that established appearance. No palette constant or broader design changes. The probe's changed-selector comparison was performed in memory; the final source diagnostics and image below were then rerun on the actual source change.

This changes action availability, not the submitted search or retained result context. Changing date controls while old results remain must not rewrite their booking/date identity. PR #24's cold/retained recovery wording, PR #23's static missing-cache links and earlier calendar/provider repairs remain cumulative.

[Source comparison](journey-source-scope.json) finds five changed methods: `update_day_mode`, `scan_finished`, `scan_failed`, `scan_thread_done` and `styles`; **46 existing `GolfHub` methods are unchanged**. Both worker classes are AST-identical. Removing the new UI update call from cleanup yields an AST identical to the prior cleanup method: wait checks, timer intervals, deletion and ownership release are preserved. Provider/core, course-result/cache and booking files, all three production workflows, alert ZIP and manifest are byte-identical to PR #24. This does not diagnose or repair the historical Windows timeout.

The final reviewed/diagnosed application hash is `addf599e372aa821069385621f73e85d1e681de4760298634ebacf634d9263db`. Metadata records PR #24 head `53cbfd463af717b3e1e7670af1911e0cd11c4714` separately from these changed application bytes; it does not claim an uncreated final commit or CI result.

## Fresh safe diagnostics

Linux Qt offscreen, Python 3.12.14 / PySide6 6.11.2, scale 1, isolated temporary directories and fixed Perth date **2 January 2033** were used. Network/DNS, browser calls, actual worker construction and application cache saves were blocked or intercepted. Both final executions passed on their first attempt after the selector change, reported zero callback exceptions and confirmed unchanged source bytes during execution.

| Diagnostic | Actual result | Evidence boundary |
|---|---|---|
| [50 filter combinations](journeys.json), [script](journeys.py), [log](journeys.log) | **50/50 pass**: 9/18 holes × Any/1–4 players × five time presets. Submitted January 2/4/7 dates, visible synthetic rows, loaded-day totals and unchecked-date wording remain correct. | Real offscreen controls submit into an intercepted worker launch and synthetic cache callback. These checks do not exercise native cleanup or prove provider availability. |
| [Five startup/fallback decisions](startup-decisions.json), [script](startup-decisions.py), [log](startup-decisions.log) | **5/5 pass**: no-saved, saved-empty and saved-error states schedule the intercepted 100 ms cache check. A missing single date calls mocked live fallback with submitted January 2 despite January 3 pending controls. Missing multi-date data retains unavailable guidance without a live call. | Constructor dispatch is intercepted before explicitly invoking actual startup/completion methods with a mocked loader. This is not complete installed startup, disk/network recovery or a launched provider search. |

These **55 final scenarios are not added to unit-test totals**. The earlier 50+5 functional passes on application hash `4b28a598d1e8b2bb1b88f8a95195e8fca2b620b4a00ea75d428d44de5f35055b` remain preserved byte-for-byte with their scripts, logs, image and scope files in [pre-style/journeys](pre-style/journeys/journey-scope.md). They did not verify the disabled appearance and are not counted again as final checks. No failed diagnostic execution, fixture correction or weakened assertion occurred; the final pair was rerun because application source changed. Button transitions and exact palette assertions need the separate focused regressions; their results belong in the main report.

The final [980×640 image](compact-980x640.png) was inspected: the expanded unchecked-date recovery note fits and remains visible, the header identifies one of three dates loaded, and Refresh Live now appears dimmed for that multi-date selection compared with the [preserved pre-style image](pre-style/journeys/compact-980x640.png). The view is intentionally scrolled to the recovery note. It is a partial-cache filter view, not visual proof of a terminal live-worker transition or all content fitting without scrolling.

## Journey coverage and limits

| Journey | Relevant evidence and remaining limit |
|---|---|
| First launch/error/offline | The five decisions above complement existing real-isolated-file/mocked-download shape regressions and PR #24's recovery tests. No full installed cold start, actual outage/reconnection or OS-resume test occurred here. |
| Dates and search controls | Existing mouse/keyboard calendar, Perth rollover, course name/count/selection, 9/18 eligibility and reversed/equal/open time-range tests remain relevant. Current control dates govern whether a new live action is offered; retained cards keep their previously captured context. Native input/accessibility and real request timing remain unverified. |
| Results, links and booking | Existing missing/error/empty/calendar distinctions, filtered counts, retained booking context and static-link recovery are unchanged. Intercepted handoffs verify stored URL/context arguments, not website reachability, live slots, holds or bookings. Booking consent/capacity/release logic is unchanged. |
| Weather/freshness | No weather/provider behavior changes. PR #8 with #4→#6 remains separate/unmerged, including the documented missing-field zero-default risk in this source line. Publication age is not per-course observation age; canonical freshness/subset reconciliation remains pending. |
| Alerts | Existing integrity checks use inert archive/manifest bytes. No alert runtime execution, Firebase call, send or delivery test occurs. Neither integrity nor zero-watch runs establish delivery. |

## Clarity, accessibility, performance and history

The supported usability improvement is that Refresh Live no longer offers the action when the selected date mode or retained work prevents it, and its disabled appearance now uses the established faint styling. Existing labels, tooltip text, keyboard semantics and palette constants remain. Offscreen state/palette assertions do not prove native screen-reader announcements, focus traversal, touch targets, DPI or contrast compliance. No redesign or broader product-direction change is introduced.

The change adds small predicate/helper evaluations at existing state transitions, with no request, retry, timer or eager rendering mechanism. No benchmark or golfer feedback supports a faster-performance or greater-appeal claim. Broader onboarding, filter-summary and freshness presentation proposals remain existing canonical/product decisions.

Historical Windows `cache_close` remains unresolved despite later green checks and 40 Linux non-reproductions. Its exact-source Windows comparison and failing-child stack remain pending/unavailable; this review ran no repeated Linux diagnosis or lifecycle suite and changed no timeout. Earlier Qt/WebEngine blocks and fixture/tooling failures remain in dated reports. The November 4 production-workflow-history lookup was denied by the connector allow-list; it was not retried or rerouted here, and production run timing remains unverified.

Installed/native Windows and Android, live/shared-network recovery, provider booking/holds, updater/signatures, screen readers/DPI/resume, notification delivery and canonical source integration remain unperformed or pending. This reviewer changed only the agreed diagnostic/evidence files, with no app/test edits, provider access, production action, security/credential change, spending or outreach. No new denied, pending or uncertain action remains.
