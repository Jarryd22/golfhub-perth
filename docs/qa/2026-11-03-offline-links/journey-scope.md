# Missing-cache links: journey and design scope — 3 November 2026, Perth

This independent review inspected the candidate based on PR #22, `bddf4ff537c4e2e5d6d18ab061fa6011cba5430d`, the cumulative checklist/backlog, yesterday's report and five-scenario deferred finding, and existing journey tests/diagnostics. It did not run application code or tests, inspect today's screenshots, access providers or verify native devices. Final executions/counts and exact-head CI belong in today's report. No applicable parent/checkout `AGENTS.md` or checkout `.agents/skills` instructions were found.

## Focus and source boundaries

The confirmed gap occurs after a multi-date search receives no shared snapshots and has no saved snapshots: existing unavailable wording appears, but selected courses' configured static direct links disappear. A single loaded empty snapshot already makes those links appear. PR #16's existing all-missing regression selected an integrated provider only; the new case is distinct from missing-date wording, provider errors, weather and canonical freshness work.

The candidate keeps the unavailable message, status and header while appending the existing **Official booking links** section. It extracts that section unchanged from the multi-date renderer: an AST comparison found the helper's `if direct_by_name` body identical to the original block. It sorts and shows one direct card per course for the whole range. The submitted context determines selected courses and round; unsubmitted controls do not redefine the response. Group/time preferences do not turn static visitor links into matching tee times.

`add_direct_results([])` builds configured direct results without passing a date to `direct_result`, so it performs no weather request. No availability summary, loaded-day count, live provider request, cache write or exact tee-time row is fabricated. These links remain available as actions when cache data is missing; their destination websites still require connectivity, and URL reachability/current bookability is not verified.

The replacement clears stale date-section references and sets `last_results` to the static cards actually displayed, or an empty list for integrated-only selections. That preserves the established meaning of displayed results and allows a later live refresh to retain visible links; it does not classify any course/date as checked. The existing owned scroll timer is reused. Single-date live fallback, saved-cache fallback and loaded/partially loaded result paths retain their behavior.

At review time, application SHA-256 was `316ff3f3263828191298e63817e1e5d84cc2415dc45eeb9ea5e96b162b5af383`. Only `cache_finished`, `render_multi_results` and the added helper differ among `GolfHub` methods; **48 existing methods are AST-identical**. Provider/core, shared cache, course-result construction, booking-assist/dialog, all three production workflows, alert ZIP and manifest are byte-identical to PR #22. This review does not establish a final remote commit or release behavior.

## Journey coverage and limits

| Journey | Relevant safe evidence and practical boundary |
|---|---|
| First launch and offline recovery | Existing startup regressions use real isolated files and mocked HTTP bytes for valid/malformed/missing cache. The five-scenario startup diagnostic explicitly invokes `show_initial_cache()` after intercepting constructor dispatch, with scheduled/live work intercepted. This proves rendering/recovery decisions, not complete installed cold startup or actual network recovery. Today's target begins at the cache completion callback. |
| Search, dates and coverage | Existing queued/submitted-context, Perth bounds/midnight, mouse/keyboard calendar and missing-date tests remain relevant. All-missing data must remain unavailable rather than become “0 matching times across 0 loaded days.” Loaded empty, failed-provider and unreleased-calendar states retain their distinct existing paths. No OS-resume or live scheduling claim follows. |
| Course, round, group and time | Course-control tests and the separate 50-scenario offscreen matrix cover 9/18 holes, Any/1–4 players, five presets and submitted filtering with worker launch intercepted. Regression evidence should distinguish direct-only, mixed and integrated-only selections, pending controls and round eligibility. The matrix is not 50 additional unit tests or provider coverage. |
| Links and booking | Static `DirectCourseCard` actions retain their stored configured URLs and course/round accessible names. Range links remain date-neutral and appear once per course. Intercepted button/keyboard activation can verify handoff arguments; it cannot verify URL reachability, provider pages, temporary holds or bookings. Exact-row booking plans/consent/capacity/release guards are unchanged. |
| Weather and freshness | New fallback cards have unavailable weather without fetching it. Existing synthetic cache tests cover reuse/bounded processing, not live forecast validity. PR #8 with #4→#6 remains separate/unmerged; missing forecast values still have the documented zero-default risk in this source line. Publication age is not per-course observation age. Canonical freshness/subset integration remains pending. |
| Alerts | PR #15 checks inert archive/manifest bytes. The production workflow still executes its bundled runtime without invoking that validator. No ZIP execution, worker behavior or notification delivery is verified; zero-watch runs establish none of these. |

## Clarity, accessibility and speed

The supported usability benefit is a recovery action beside an honest unavailable state. Existing section wording explains that these are official booking/visitor pages, not verified slots. Existing card names, wrapped explanatory text and keyboard button behavior are reused; today's compact/reachable-action evidence must be assessed separately. This source review cannot establish native screen-reader announcements, touch targets, DPI scaling or contrast across devices.

The change builds the same small static card section already used for loaded multi-date searches and adds no network request or worker. No timing benchmark or golfer research supports a claim that the app is faster or more appealing. Broader onboarding, submitted-filter summaries, freshness presentation and visual redesign remain existing product/integration decisions.

## Historical and unperformed work

PR #22's 266 aggregate passes and its intentional baseline failures are historical results, not today's totals. Preserve today's baseline failures, any fixture/tooling failures and every final-head CI event/attempt separately. Historical Windows `cache_close` remains unresolved despite later green checks and 40 Linux non-reproductions; same-platform comparison and the failing-child stack remain pending/unavailable. No repeated Linux diagnosis or weakened timeout/assertion is part of this review.

Installed/native Windows and Android, live/shared-network recovery, real booking/holds, screen readers/DPI/resume, installed updater/signatures, alert execution/delivery and canonical desktop/mobile/service reconciliation remain unperformed or pending. This reviewer made no application/test edit, remote write, production action, health-watch request or third-party contact. No denied, pending or uncertain action remains.
