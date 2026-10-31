# Retained-result context: independent scope and design review — 31 October 2026

This review inspected the candidate based on PR #19, `ba1faeae0dc9cf3314e8dc884f79b13e2520d22c`, the preserved reproduction JSON/scripts, existing booking safeguards and tests, and the cumulative checklist/backlog. It did not execute the application or tests. The retained baseline offscreen lazy-result image was visually inspected; no native/device UI was inspected. Current regression, aggregate, diagnostic and CI results belong in their own logs and report, not in this review's counts. No applicable checkout `AGENTS.md` or `.agents/skills` was found.

## Finding and scope

The retained baseline evidence supports two related defects:

- An old BOOK button still identifies the original course, time, round and date, but after a new live search is submitted its booking plan takes the new search's player count. The recorded 1-player, 2 January result becomes a 4-player plan while keeping the 2 January row URL. Failure and cancellation preserve that mismatch; changing unsubmitted controls alone does not reproduce it.
- An old, unbuilt multi-day section still advertises one matching time, but expanding it after a new live search applies the new player/time filters. The recorded morning row disappears under the new four-player afternoon filter while its old heading and total remain.

Binding a copy of the render context to row-action handlers and lazy builders is a focused correction. `self.context` remains the new submitted work's context; clicking or expanding old results must not restore it globally. The original result and row objects continue to supply the exact source URL, time, available spaces, course and round. The correction changes the source of player/time preferences, not the source of availability or booking URLs.

`context=None` preserves existing direct-call behavior, while an explicitly supplied empty context remains distinct from fallback. A shallow `dict` copy is sufficient for the fields consumed here: `players`, `from` and `to` are scalar values. Site/date list objects are not used to reselect lazy rows or construct booking URLs at action time. Existing date strings are separately captured for the displayed section/accessibility labels. No general deep-copy framework or global context swap is needed for this fix.

[`context-scope-review.json`](context-scope-review.json) records the reviewed candidate hash. Only five `GolfHub` methods change: `open_tee_time`, `filtered_rows`, `_populate_day_section`, `render_multi_results` and `render_results`. Fourteen reviewed search, completion, cancel, thread-cleanup, close, booking-choice and result-clear methods have identical ASTs to PR #19. Booking-assist/dialog code, shared cache, provider/core result code and all three production workflows are byte-identical. This is not a lifecycle, freshness, provider, cache-policy or canonical-source rewrite.

## Booking safeguards and regression boundaries

The existing plan builder still checks the requested group against available spaces, identifies supported exact public timesheet URLs and requires explicit boolean confirmation before constructing temporary-hold behavior. Manual selection, cancellation, unsupported providers and unavailable links keep their existing branches. The change does not bypass `_booking_choice`, enable automatic holds, alter generated scripts, navigate a provider page or complete a booking.

For safe QA, intercept browser calls and dialogs, use fake/non-running live workers for context transitions, and inspect pure plan arguments. Any confirmed-assist test must use a mocked dialog; generated hold/release scripts are data to inspect, not scripts to send to providers. Existing opt-in, exact-resource/date/product, ambiguity, capacity and release guards remain relevant regression checks.

The focused retained-context regressions should establish all of the following without weakening existing object/URL/label assertions:

- Old single-day BOOK actions preserve their original player count while new live work is pending, after failure and after cancellation. Test both Any→numeric and numeric→Any transitions so an unbound fallback cannot pass unnoticed.
- Old lazy day bodies retain their original player and time filters after a new submitted context, including in-place changes to the active context. Counts, headings, visible rows and button names must continue to agree.
- A lazy day's BOOK action retains its own rendered date/round URL and original player choice; Show all/first controls reveal the original filtered cards.
- Successful replacement results bind the new context. Acting on an old card must leave active work's context unchanged; this is not a reason to overwrite `self.context`.
- Direct `open_tee_time`/`filtered_rows` callers that omit the optional context retain existing behavior, and the existing keyboard action test continues to verify result/row identity plus the newly bound context.

## Clarity, accessibility and speed

**Clarity:** the inspected baseline image contains a concrete contradiction: a section heading says one matching time while its expanded body says none. Preserving the original filter context removes that inconsistency when the old result is retained. It also keeps the requested booking group aligned with the search that produced the displayed card. This is a code/evidence-based usability improvement, not measured golfer feedback.

**Accessibility:** existing BOOK names already retain displayed course, time, round and date. The intended repair preserves those names and keyboard activation while making their actions consistent with the displayed result. It does not add requested player count to accessible names, announce dynamic search changes, prove native screen-reader behavior or resolve the broader submitted-filter-summary design question. Keep those existing product/accessibility decisions separate.

**Speed and appeal:** the patch adds small in-memory context copies and bound callables. Lazy body construction remains deferred until expansion; no new network call, worker, timer or eager rendering pass is introduced. That supports retaining the current interaction structure, but no timing benchmark, startup-latency measurement, golfer task-time study or preference research was performed. Do not claim the app is faster, more attractive or preferred by golfers on this evidence. No visual redesign or new product direction is implemented.

## Evidence categories and remaining limits

| Area | Safe source/automated boundary | Do not infer |
|---|---|---|
| Retained booking and lazy-result probes | Synthetic rows, actual button/section actions, fake non-running workers, pure plans intercepted/cancelled, blocked sockets/browser/dialogs. Before/after JSON can establish the context mismatch and repair. | Real live-worker scheduling, provider behavior, a reservation, temporary hold or successful booking. |
| Existing search/date/filter matrix | Offscreen Qt controls, submitted parameters, synthetic results, bounded keyboard/date/round/player/time checks, with intercepted worker launch. | Native Windows/Android behavior, real provider availability, OS resume or production search latency. |
| Startup/offline/cache recovery | PR #19's real isolated files and mocked HTTP bytes cover their malformed-shape cases; separate startup diagnostics intercept scheduled/live work. | Complete installed first launch or actual network outage/recovery. The retained-context repair does not change these paths. |
| Layout/accessibility | Inspected offscreen images and Qt name/relationship/keyboard assertions at recorded logical sizes. | Native screen readers, DPI scaling, Android tap targets or user-research findings. |
| Weather/freshness | Existing synthetic cache tests and unchanged source can be rechecked. | PR #8 and #4→#6 weather repairs are still separate/unmerged; current false-zero forecasts are not fixed here. Publication age is not per-course observation age. Canonical freshness/subset reconciliation remains pending. |
| Alerts | PR #15 checks archive/manifest bytes without importing the runtime. | Integrity or zero-watch runs do not prove worker correctness or delivery. No ZIP execution, Firebase client, alert worker, device send or production dispatch occurs. |
| Worker close behavior | A normal unchanged lifecycle-module run may be part of the aggregate. | Historical Windows `cache_close` is still unresolved; a current pass does not replace the missing failing-child stack or same-platform comparison. No repeated Linux paired investigation is performed. |

Native/installed Windows and Android, real booking/hold flows, notification delivery, updater installation/signatures, full real-network startup and canonical desktop/mobile/service integration remain unperformed or pending as previously recorded. Preserve historical Windows/Qt failures, blocked WebEngine cases and earlier fixture failures in their dated evidence. No direct-provider access denial was bypassed or retried for this review.

Sources: current Qt diff, `app/booking_assist.py`, `app/booking_dialog.py`, booking-context/UI/opt-in/guard tests, [booking reproduction](before/booking-context-probe.json), [lazy reproduction](before/lazy-context-probe.json), [inspected baseline image](before/retained-lazy-context.png), prior QA reports and cumulative checklist/backlog. This review writes only evidence documents, with no application/test edits, remote writes, production actions or third-party contact.
