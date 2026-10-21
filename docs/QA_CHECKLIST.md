# Golf Hub regression checklist

Record the commit, app version, operating system, timezone, scale factor, device/window size, data source and test time. Mark each item **pass**, **fail**, **not run**, or **inspection only**. Do not equate a source-widget test with a packaged Windows or Android test.

## Before each pass

- Inspect active tasks, remote branches and draft PRs. Check dependencies before selecting work.
- Preserve dirty checkouts; use a clean separate workspace. Read any repository and release instructions.
- Identify whether the target is remote desktop source, a local candidate, installed Windows, or Android. Do not mix results from different versions.
- Inspect both update repositories, signed manifests and version provenance; distinguish metadata validation from an installed-client upgrade.
- Use isolated application/cache directories. Never complete a booking, make a temporary provider hold, send real notifications, change credentials, or publish as part of QA.

## Desktop journeys

| Journey | Checks and expected behavior |
|---|---|
| First launch | Clean state builds a usable window; no crash. Default day and 28-day bounds use Perth time. Saved data appears with truthful source/age. Cold offline startup has an actionable state. |
| Dates | Today/tomorrow agree with Perth across UTC midnight and month/year boundaries. Single, nonconsecutive and 28-day selections persist; at least one date remains. Mouse and keyboard can select/apply dates. Live refresh is available only for one date. Test an app left open across Perth midnight separately. |
| Course search | Case-insensitive course names filter the list. Confirm suburb behavior matches its label. Check individual selection, Select visible, Clear, selection count, and reopening the panel. |
| Round | Switch 18→9→18. Available courses, requested cache key, card round labels and official URLs agree. Unsupported courses are excluded. |
| Group/time | Any and 1–4 players respect available spaces. Presets and custom ranges filter correctly. Equal endpoints and open bounds work. Reversed ranges explain the error before a worker starts; controls/results remain intact and focus returns for correction. |
| Results | Counts agree with visible rows; course names sort A–Z. Show all/first 12 retains rows. Multi-day groups expand lazily without mixing dates. Course and row links refer to the chosen date/round. |
| Booking handoff | Intercept URL calls or use local fixtures for automated tests. Verify exact-row and official-calendar handoffs, unavailable links, ambiguous rows, cancellation, and release guards. Do not select live booking cells or submit any transaction. |
| Weather | Complete, unavailable, partial and genuinely zero forecasts render honestly. Check cached-source age and expiry after integrating the relevant weather PRs. Never infer a valid forecast from a plausible-looking zero. |
| Freshness | Distinguish publication time from each course's observation time. Stale fallback remains marked stale after republication. A selected-course live refresh preserves other saved courses. Failed refresh retains usable data with a warning. |
| Empty/error/offline | Distinguish no matching times, provider error, unreleased calendar, missing date cache and network outage. Official links and recovery guidance remain usable. Check saved-cache offline and no-cache offline separately. |
| Races/stop/close | Change dates, round and filters during startup/cache/live work. Only the submitted current search wins. Stop prevents queued work; close does not leave running Qt callbacks or threads. |
| Layout | 980×640, 1280×800, 1600×1000, open course panel, many results, 100%/150%/200% display scale. No clipped primary actions; vertical scrolling reaches all content. Record logical vs physical dimensions. |
| Accessibility | Accessible names for each field, course checkbox and repeated booking button; visible focus; keyboard-only date and course selection; sensible tab order; readable text/error contrast; screen-reader announcement of result/error changes. |

## Android (separate versioned run)

- On an isolated copy of the intended mobile baseline, run `flutter analyze` and the existing widget/unit suites; do not run tools that mutate the dirty source checkout.
- Test clean startup, offline saved data, single/multi-date filters, 9/18 holes, group/time presets, booking handoff, returning from the browser, course details and maps.
- Check keyboard-open course search, landscape, small screens, large text, TalkBack names, and Android tap-target guidelines.
- Keep a map open past the freshness boundary and background/resume across Perth midnight.
- Exercise notification logic with mocks only; do not send device test notifications or contact real users.

## Repeatable source checks

With the repository requirements installed, run each `tests/test_*.py` module in a fresh Python process (Qt/WebEngine state can persist within one process):

```text
python -m unittest discover -s tests -p test_perth_dates.py -v
python -m unittest discover -s tests -p test_midnight_rollover.py -v
python -m unittest discover -s tests -p test_calendar_keyboard.py -v
python -m unittest discover -s tests -p test_course_controls.py -v
python -m unittest discover -s tests -p test_time_range_ui.py -v
python -m unittest discover -s tests -p test_multiday_ui.py -v
python -m unittest discover -s tests -p test_search_race.py -v
python -m unittest discover -s tests -p test_thread_lifecycle.py -v
python -m unittest discover -s tests -p test_cache*.py -v
python scripts/qa_desktop_smoke.py --output <isolated-output-directory>
git diff --check
```

Set `QT_QPA_PLATFORM=offscreen` and point `LOCALAPPDATA`, `TEMP` and `TMP` at isolated writable test directories. Do not disable Chromium's sandbox to make tests pass. The smoke tool uses real Qt controls, synthetic data, intercepted browser calls, and no provider requests; its JSON explicitly records callback and accessibility findings. A successful process exit is not a clean product bill of health—read that report. Screenshots use application-loaded Segoe UI fonts on Windows because the offscreen plugin may not discover them automatically.

Before opening a draft, compare new regressions against baseline, visually inspect evidence, obtain an independent diff review, and confirm the branch has no production workflow trigger. Record known failures instead of relabeling them as passes. Enumerate **all workflow events/attempts** for the exact head (for example `actions/runs?head_sha=<sha>&per_page=100`, checking total count/pagination); the commit-workflow helper filters to PR events and cannot establish all-CI success. Keep push and PR executions distinct, retain failures alongside subsequent passes, and verify checkout head/merge tree. For documentation-only commits filtered out of CI, state that the exact new head has no run and name the tested code head.

## Latest pass: 21 October 2026

See the [Perth midnight report](qa/2026-10-21-midnight/REPORT.md). A fake-clock run on unchanged #13 reproduced yesterday still labelled Today, stale 28-day bounds and a new search submitted for yesterday. The focused draft stacked on #13 refreshes editable controls every 30 seconds while idle and immediately on activation, new search, picker opening and picker apply/toggle. No automatic search is started. Preserve valid absolute dates; remove expired choices; choose today only if none remain. Tomorrow becomes Today without changing the chosen absolute date. A full 28-date choice becomes 27 dates after one day, without automatically adding the newly available last date.

Fifteen new offline widget tests pass (untouched #13: four pass, ten failing methods and one missing-timer error). Include UTC midnight without Perth rollover, year/month/leap boundaries, multi-day suspension, open-picker pending choices, cancel and exactly one final Apply notification. Confirm real timer delivery and stop on close. Submitted contexts, queued searches, live fallback and lazy results retain their original dates. Mocked live construction is not native worker evidence; the separate existing 11 real-worker lifecycle tests also pass locally.

The focused suite has **120 passing checks: 77 desktop and 43 cache** on Linux/Python 3.12.14/Qt 6.11.2. Test-only Windows CI includes the new module. **Correction: original code head `9ed31ad` has mixed CI results.** Windows push run [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests but failed `cache_close` at the unchanged 30-second limit. Later PR-event Windows (77 tests) and Linux cache (43 tests/actionlint) passed. All 15 midnight tests passed in both Windows runs. The failed execution was omitted from the first summary; preserve it and do not infer all-CI success. [Follow-up evidence](qa/2026-10-21-midnight/ci-followup/REPORT.md): 40 fixed-cohort cache-close invocations plus 22 test-case executions across two full-module runs passed on paired #13/#14 Linux sources, across Qt 6.11.2/6.12.0. These repetitions are not extra unique regressions and do not establish the Windows timeout's cause or equivalence to the older stall. Source screenshots at 980×640 and picker JSON show before/after state; they are not native Windows or Android evidence. The prior Qt 6.11.1 manual-event-pump stall, four WebEngine sandbox-helper blocks and obsolete cron assertion remain separate known limitations, outside today's focused pass. Do not disable the sandbox or infer their resolution from passing focused tests.

Current update-release API metadata remains Windows 5.1.17 / Android 0.1.19, with identical asset sizes/digests to the prior pass. No new manifest signature, installed updater, device, screen-reader, DPI or actual notification check. The 15-ref duplicate audit found no existing midnight repair; all #3–13 remain drafts. No hourly production health audit or freshness/subset rewrite was performed. Canonical-source reconciliation still gates integration into the newer desktop/mobile candidate.

## Previous pass: 20 October 2026

See [today's report](qa/2026-10-20/REPORT.md). The draft stacked on #11 adds context to repeated booking/course/expand actions and visible Start/End label buddies. Check actual Qt accessible names for course, tee time, round and submitted date; change the date control without submitting and expand later day sections to prove names stay tied to the displayed result. Date-independent course links deduplicated across a multi-day range must not invent a single date. Check final Collier calendar wording, literal ampersands, row URL precedence and unchanged keyboard handoff.

The custom Start/End controls now have visible labels and real Qt Label relationships. Test the accessibleName property plus relationship on every platform; Unix Qt may expose the selected value as Name. Repeat compact 980×640 custom-range geometry and visibility checks. Source accessibility is not native screen-reader validation.

The expanded mocked smoke also checks all 28 dates and 25 player/time preset combinations. Coverage/link checks remain intercepted and synthetic. Keep the baseline obsolete cron failure and four blocked Chromium sandbox-helper cases separate from passes. External fixture cleanup is used while QApplication is alive; do not turn a crashed process into a pass. Retain initial baseline smoke crash evidence and its successful unchanged rerun. At PR #12, threaded smoke was blocked by repeat segmentation faults in unchanged cache_thread_done; its separate synchronous-cache fixture did not validate thread lifecycle. The [separate lifecycle follow-up](qa/2026-10-20-thread-lifecycle/REPORT.md) now retains workers until native completion. Eleven real-worker subprocess tests pass on Qt 6.11 and 6.12 (six fail on untouched #12); 105 focused checks pass. Verify native cleanup with isRunning=false/wait(0)=false, responsive GUI timers, newest queued search exactly once, live re-entry, cancellation, close, and destruction counts. Cleanup timers must continue while closing. The unchanged asynchronous 18-journey harness passes three fresh Qt 6.12 runs, but Qt 6.11 still has an intermittent manual-event-pump stall: preserve that failure and do not mark all threaded QA complete. Real QApplication.exec cache/live probes pass on both versions. Windows CI and offscreen results are not installed-client validation.

Current Windows/Android metadata remains 5.1.17 / 0.1.19. Manifest metadata checks do not verify signatures or installation. Ten separate socket-blocked archived alert-logic cases pass; loose-source imports and worker delivery remain blocked. Existing freshness/subset repairs require unavailable local-source reconciliation; do not create a competing rewrite. The supplied hourly audit already covers the November 4 false Clear forecasts through draft #8, and batch publication times still do not establish per-course/forecast observation age.

## Previous pass: 19 October 2026

See [today's report](qa/2026-10-19/REPORT.md). The draft stacked on #10 reconciles the known course-count signal adapter, labels filter/course controls and makes the course-name search hint accurate. New regressions cover actual checkbox/row/Space input, one notification per toggle, hidden selected courses, Clear/Select visible and 18→9→18. Check counts against `selected_sites()`, not just checkbox state. Course labels containing a literal `&` must retain it when a QLabel buddy is added.

Eight new regressions pass on Linux Qt 6.12 and 6.11.1. For combo boxes, check `accessibleName()`, the visible label's buddy and actual Qt Label relationship. Qt intentionally uses current text as Name on Unix; do not treat a Windows-only Name expectation as a portable screen-reader test. Checkbox/search interface names are checked directly. Native assistive-technology testing is still required.

Local branch outcome: 143 passed, 2 baseline failures (obsolete cron and Windows-specific combo Name assertion), 4 WebEngine cases blocked by the cloud Chromium sandbox helper. Do not disable the sandbox. Two older modules needed external widget cleanup after tests to avoid interpreter shutdown aborts; retain original and recheck logs. Test-only Windows CI includes 43 focused desktop cases, with cache CI separate. Verify final-head CI on the draft rather than reusing yesterday's results.

Sixteen mocked offscreen journey checks and 148 intercepted course-link combinations passed; initial smoke instability remains documented. Weather sampling must check finite numeric values, boolean/null exclusions, plausible ranges, temperature order and Clear/all-zero patterns, separately from valid zero rain. Only three date/round payloads were sampled; do not infer whole-cache or forecast-age validity.

Check alert deployment source before calling missing loose modules a runtime outage: the workflow uses the committed runtime ZIP. Ten isolated archive logic audit cases pass with sockets blocked; root suite imports and worker/delivery remain blocked. No actual delivery is proven. Release manifests match metadata, but current signature checks need the trusted updater key, absent in this cloud checkout.

## Previous pass: 18 October 2026

See [today's report](qa/2026-10-18/REPORT.md). Keyboard date selection now passes source-widget regressions on the branch stacked on #9. Deliver events to the actual focused calendar table, not directly to its parent. Check arrows without selecting, Return/Enter/Space toggles, held keys, numeric typing, month/bounds changes, at-least-one selection, Tab/Space apply, Escape cancel and click/double-click behavior. This picker uses arrow navigation, with native numeric date editing disabled.

Test-only Windows CI now runs 35 focused Qt tests; cache CI remains separate. Qt test fixtures must destroy hidden top-level widgets and drain deferred deletion before interpreter shutdown; closing a window alone does not release it. Record final-head runs rather than assuming a previous green run covers a new commit. Native screen-reader, scaling and installed Windows/Android validation remain not run. Alert tests on copied local-only source must remain separate from remote-branch counts; block networking and mock delivery.
