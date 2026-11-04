# Live recovery: journey and usability scope — 4 November 2026, Perth

This independent review read the cumulative checklist/backlog, PR #23's report and the current source diff. It also ran the two safe diagnostics below. It did not run the new recovery regressions or aggregate suite; their results belong in the main report. No applicable checkout/parent `AGENTS.md` or checkout `.agents/skills` instructions were found.

## Reviewed change

The candidate distinguishes a stopped or failed live refresh with previous displayed results from one with no results to retain. Cold failure replaces the obsolete “Checking courses live...” body with retry guidance; cold cancellation no longer implies that an existing cache was preserved. When previous result cards remain, the message describes those visible results rather than asserting disk-cache provenance.

`clear_results()` now resets `last_results` and `day_sections` when it removes their widgets. This prevents later recovery wording from treating already removed cards as retained results. Existing renderers repopulate that metadata for their new view. Prior tee-time cards and static links that are actually retained keep their stored context and actions; a static link is not a verified tee time.

This is the worker-wide failure/completion presentation path. Individual provider exceptions still become ordinary error-bearing results, covered by the existing PR #18/#21 behavior. The patch does not change provider requests, retries, cancellation scheduling, successful-result persistence or booking safeguards. Empty/no-card display state is not proof that no cache file exists anywhere on disk; the new wording avoids making that claim.

[AST/byte inspection](journey-source-scope.json) identifies only `scan_finished`, `scan_failed` and `clear_results` as changed `GolfHub` methods; **48 existing methods are unchanged**. Provider/core, course-result/shared-cache and booking files, the three production workflows, alert ZIP and manifest are byte-identical to PR #23. The reviewed/run application hash is `fc61c95941605ba2bb79608fdf619d988ca9e3037f595377b353c10be3bfbfc3`; the recorded base head is `50ae64a00b4372d1f8c33dd787c2d5406510da2e`, not an uncreated candidate commit.

## Fresh diagnostics

Both scripts use the saved Python 3.12.14 / PySide6 6.11.2 environment, Linux Qt offscreen at scale 1, isolated temporary paths and fixed Perth date **2 January 2033**. Sockets/DNS, browser calls, cache/live worker construction and application cache saves are blocked or intercepted. Both report the same application hash and confirm source bytes stayed unchanged during execution.

| Diagnostic | Observed result | Boundary |
|---|---|---|
| [50 filter combinations](journeys.json), [script](journeys.py), [log](journeys.log) | **50/50 pass**, zero callback errors: 9/18 holes × Any/1–4 players × Any time/Morning/Midday/Afternoon/Custom. Submitted dates are January 2, 4 and 7. Exact visible rows match the synthetic capacity/time expectations; the missing dates remain unchecked and counts cover one loaded day. | Actual offscreen controls submit to an intercepted launch and synthetic partial-cache callback. No provider availability, worker scheduling or native device is tested. |
| [Five startup/fallback decisions](startup-decisions.json), [script](startup-decisions.py), [log](startup-decisions.log) | **5/5 pass**, zero callback errors. No-saved/valid-empty/provider-error startup states schedule the intercepted 100 ms shared-cache check. Single-date absence calls mocked live fallback with submitted January 2 despite pending January 3 controls. Multi-date absence keeps actionable unavailable wording without a live call. | Constructor dispatch is intercepted, then actual `show_initial_cache()`/`cache_finished()` is invoked with a mocked loader. This proves decisions and rendering, not a complete disk/network cold start or successful recovery. |

These **55 diagnostic scenarios are separate from unit-test totals**. Both executions passed on their first run; no fixture correction, assertion relaxation or rerun was needed. They revalidate prior journeys, while the new focused regression suite must independently establish today's failure/cancellation repair.

The generated [980×640 recovery image](compact-980x640.png) was inspected: the expanded unchecked-date message is visible and fits its body, and the source/header still identifies one of three days loaded. The image is intentionally scrolled to that message. It is not a screenshot of today's cold live-failure/cancellation state and does not establish that all content fits simultaneously without scrolling.

## Journey boundaries

| Area | Relevant coverage and remaining limit |
|---|---|
| First launch, errors and offline use | The five decisions above complement existing real-isolated-file/mocked-download shape regressions. Retained versus absent display state needs today's dedicated recovery tests. Full installed startup, real network failure/reconnection and OS resume remain unperformed. |
| Dates, course and filter input | Existing mouse/keyboard calendar, Perth midnight, course count/name search, round eligibility and reversed/equal/open time-range tests remain relevant. The fresh 50-scenario matrix covers submitted rows, not all courses/providers or accessibility on a native platform. |
| Coverage, links and booking | PR #16–23 distinctions remain: missing dates, errors, true empty results, calendar status, exact-row counts, retained context and missing-cache static links. Intercepted handoffs can verify URLs/context; they cannot verify reachability, bookability, holds or completed bookings. Exact-row consent/capacity/release code is unchanged. |
| Weather and freshness | No new weather request or completeness validation is introduced. PR #8 with #4→#6 remains separate/unmerged; the source still has the documented missing-field zero-default risk. Publication time is not per-course observation time. Canonical freshness/subset integration remains pending. |
| Alerts | Existing tests inspect inert ZIP/manifest bytes. No runtime extraction/execution, Firebase operation, notification send or delivery test occurs. Integrity and zero-watch executions do not verify delivery. |

## Clarity, accessibility and speed

The supported clarity improvement is truthful completion/recovery wording and visible retry guidance after a cold failure or cancellation. Existing controls are restored by the completion handlers; no new interaction or product direction is introduced. Source inspection shows the existing names, keyboard actions, captured booking context and lazy date construction remain intact. Offscreen label/wrapping checks do not establish native screen-reader announcements, focus traversal, touch targets, DPI or contrast across devices.

The change adds state checks, text updates and metadata clearing to existing handlers. No request, retry, timer or eager result-building mechanism is added. No benchmark or golfer study supports a claim of faster performance or greater appeal. Broader onboarding, submitted-filter summaries, typography and freshness presentation remain existing canonical/product review decisions.

Historical Windows `cache_close` remains unresolved despite later green runs and 40 Linux non-reproductions; the failing-child stack and exact-source Windows comparison remain pending/unavailable. No repeated Linux diagnosis or weakened tests occurred here. Prior Qt/WebEngine blocks and fixture/tooling failures remain in their dated reports. Preserve today's intentional baseline failures and every final-head CI event separately from these passing diagnostics.

Installed/native Windows and Android, real provider/shared-network recovery, live booking/holds, updater/signatures, screen readers/DPI/resume, notification delivery and canonical desktop/mobile/service integration remain unperformed or pending. This reviewer changed only evidence scripts/documents, with no app/test edits, provider access, health-watch duplication, production action or third-party contact. No denied, pending or uncertain action remains.
