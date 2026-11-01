# Provider exceptions: independent journey scope — 1 November 2026, Perth

This is a source/evidence review of the candidate based on PR #20, `63c910556c4f4dc210e41c3e6db665845436a8f0`. It compares the cumulative checklist/backlog, the 31 October report and current test/probe sources. This reviewer did not run the application, test suite, provider requests or device UI, and did not inspect current screenshots. Today's executions and final counts belong in the main report and logs. No applicable checkout or parent `AGENTS.md` or checkout `.agents/skills` instructions were found.

## Focus and compatibility

The reviewed correction preserves a nonempty failure marker when a provider exception has an empty or whitespace-only string. `exception_message()` keeps a nonblank message exactly, otherwise uses the exception class name. Core provider/calendar catches, the live worker's escaped-provider catch and publisher catches use it. Successful empty responses retain `error=None`; successful rows on another fetched page retain existing behavior.

This closes a producer-side gap in PR #18: its incomplete-availability wording and error cards depend on a truthy `error`, so a newly caught message-less failure could still become apparent zero availability without an error card. It is a focused follow-up, not another summary redesign. The independent producer-to-widget tests use synthetic exceptions, intercepted links and blocked sockets; the publisher tests need to establish fallback/success accounting separately. Do not infer a current provider incident from these controlled reproductions.

Previously saved or externally supplied records already containing `error=""` remain ambiguous; this repair does not migrate them or infer failure from empty rows. The existing schema accepts their structure. Weather completeness, upstream HTML meaning, retry classification and snapshot freshness policies are separate concerns; avoid describing all failures or false zeros as solved.

A static comparison at review time found all **50 `GolfHub` methods AST-identical** to PR #20. Booking-assist/dialog, shared-cache/course-results, alert workflow, runtime archive and manifest are byte-identical. PR #20's captured displayed context, active search state, lazy builders, booking consent and worker lifecycle are preserved. The source review does not establish the final remote head or CI outcome.

## Journey and evidence boundaries

| Journey | Existing safe coverage/source finding | Limit |
|---|---|---|
| First launch and offline recovery | Startup regressions use real isolated files and mocked HTTP bytes for malformed/valid/missing cache. The separate five-scenario diagnostic calls actual `show_initial_cache()` after intercepted constructor dispatch, mocks loader/timer startup, and checks saved empty/error/no-cache states plus single/multi-date decisions. | No complete installed cold start or actual network outage/recovery. Intercepting the scheduled cache/live worker proves a decision, not completed recovery. |
| Search and dates | Submitted context snapshots, queued-search races, Perth day bounds/midnight and actual offscreen keyboard calendar actions have focused tests. Single-cache absence calls `search_live` with submitted context; multi-date absence offers recovery guidance without starting a live search. | No native OS resume, real worker/provider timing or current availability claim. |
| Round, group and time | The 50-scenario matrix uses real offscreen controls: 9/18 holes × Any/1–4 players × five time presets. Worker launch is intercepted and partial snapshots are synthetic. Separate tests cover inclusive/equal/open ranges and rejection of reversed ranges before work. | These are diagnostic scenarios, not 50 extra unit tests. They do not test every course/provider or production search latency. |
| Course selection | Existing mouse/Space/row actions, visible selection/clear, hidden selected courses, name-only search hint and 18→9→18 selection/count tests remain relevant. | Name matching is not suburb search; no new picker defect or golfer feedback was established here. |
| Results and booking | PR #16 distinguishes missing dates, #17 counts exact row-bearing courses, #18 distinguishes provider errors, #19 rejects malformed structures and #20 binds retained cards/lazy days to their displayed filters. Pure booking plans and intercepted buttons cover source/date/round/group identity and opt-in/capacity/ambiguity/release guards. | No provider page navigation, actual hold, reservation or completed booking. Mocked dialogs and inspected script strings do not verify native WebEngine or provider compatibility. |
| Weather and freshness | Existing tests exercise synthetic complete forecasts, unavailable/out-of-horizon data, reuse and bounded cache processing. Current `_weather_daily_value()` still defaults missing/null values to zero; displayed cache age comes from snapshot publication time. | PR #8 and dependencies #4→#6 remain separate/unmerged. This provider-error fix does not fix incomplete forecasts, per-course stale labels or selected-subset cache preservation. Canonical reconciliation remains pending. |
| Alerts | PR #15 validates archive/manifest bytes as inert data. Production workflow source still extracts and executes its bundled runtime without invoking that validator. | No runtime import/execution, Firebase operation, notification send or delivery test. Neither integrity nor zero-watch runs prove worker behavior or delivery; this loose-source patch does not update the bundled runtime. |

## Clarity, accessibility and speed

The supported usability benefit is that a newly caught message-less failure reaches the existing unavailable-state explanation and official-page action instead of silently appearing as zero matches. The fallback class name is diagnostic text, not new golfer-facing recovery guidance; existing wording supplies that guidance.

Existing accessible names, label relationships, keyboard actions and retained BOOK context remain covered by their tests. They do not verify screen-reader announcements, native tab/focus behavior, DPI scaling, Android tap targets or contrast across devices. Current compact/large screenshots must be inspected separately and identified by logical size. No current visual assessment was performed in this review.

The helper adds string conversion and a blankness check only on exception paths; lazy rendering and worker structure remain unchanged. No startup/search benchmark, task-time study or golfer preference research supports a speed or appeal claim. Existing onboarding, submitted-filter-summary and per-course freshness recommendations remain design/integration work; no redesign is justified by this narrow finding.

## Historical results and outstanding scope

PR #20's report records **238 passed aggregate tests**, **50 filter and five startup diagnostics**, and its intentional exact-PR19 baseline failures. Those are historical results, not today's counts. Preserve today's baseline failures and every final-head CI event/attempt separately.

Historical Windows `cache_close` remains unresolved: the unchanged 30-second timeout failed in PR #14's Windows push run; later green checks and 40 Linux non-reproductions do not establish cause or repair. The missing Windows comparison and failing-child stack remain pending/unavailable. This review did not repeat Linux diagnosis or loosen tests. Earlier Qt/WebEngine blocks and fixture/tooling failures remain in their dated reports.

Native/installed Windows and Android, live booking/holds, notification delivery, installed updates/signatures, full network recovery and canonical desktop/mobile/service integration remain unperformed or pending. No health-watch duplication, direct-provider access, production action, remote write, application/test edit or third-party contact occurred in this review. No denied or uncertain action remains.

Reviewed sources: current core/Qt/publisher diff; `app/booking_assist.py`, `app/booking_dialog.py`, `app/shared_cache.py`; startup, provider-exception, retained-context, calendar, course-control and time-range tests; current diagnostic scripts; alert workflow/integrity tests; `docs/QA_CHECKLIST.md`, `docs/IMPROVEMENT_BACKLOG.md` and `docs/qa/2026-10-31-retained-context/REPORT.md`.
