# Calendar mouse selection — 2 November 2026, Perth

When a displayed month starts on Monday, Golf Hub ignores mouse clicks on some valid dates near its end. Qt includes a full preceding week in the first grid row; Golf Hub's mouse mapping was one week ahead, so its adjacent-month guard discarded those clicks. Keyboard selection still worked. Three added lines align the mapping with Qt's grid and also prevent clicks on hidden preceding-month padding from navigating unexpectedly.

## Scope and inspection

Branch `fix/desktop-calendar-mouse-20261102` starts from unchanged draft [#21](https://github.com/Jarryd22/golfhub-perth/pull/21), `9aa16f733458db871c2452a18a247536ab348498`. The [current audit](context-audit.json) inspected 25 branches, 19 drafts #3–21, 23 non-data source refs, no other open issues, both update repositories and prior reports/checklist/backlog. All relevant refs and the preserved loose source had the same incorrect mouse formula; [duplicate/scope review](candidate-scope-review.json). PR9/10/14 cover date validation, keyboard activation and rollover, not this mapping. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`; release metadata remains Windows 5.1.17 / Android 0.1.19.

The saved executor resumed after startup. No repository work ran while it was starting. Original dirty October 22 work and completed worktrees remain preserved. No applicable AGENTS.md or checkout `.agents/skills` files were found. Local execution used Linux, Python 3.12.14, PySide6/Qt 6.11.2, host UTC, isolated data paths and offscreen scale 1. The remote desktop source identifies as v5.0; canonical-source reconciliation remains pending.

Only `MonthOnlyCalendar._date_at_view_position` changes in application code. Keyboard activation, painting, selection limits, Perth bounds, workers, providers, cache, booking and alert code remain unchanged; [source comparison](source-scope.json). The new test module joins the existing desktop test workflow. No production workflow or timeout/assertion was changed.

## Before and after

[Detailed evidence and preserved exploration history](context-review/NOTE.md), [baseline grid JSON](context-review/calendar-grid-probe.json), [repaired grid JSON](context-review/after/calendar-grid-probe.json), [normal-app before](context-review/calendar-window-probe.json), [normal-app after](context-review/after/calendar-window-probe.json).

| Journey | Exact PR21 | Repair |
|---|---|---|
| Settled popup, 36 actual mouse actions across three Monday-start months and one control month | 23 select correctly; 13 valid clicks ignored | 36/36 select correctly |
| Normal GolfHub popup at 980×640 and 1280×800, two target dates plus earlier-date controls | All four control clicks pass; all four target clicks ignored | All eight clicks select correctly |
| Example: March 25, 2032 | Cell incorrectly interpreted as April 1 and discarded | March 25 selected; count/summary update |
| Hidden preceding-week cell inside the permitted date range | Can navigate/toggle an adjacent date although painted over | Click/double-click remains suppressed |
| Mouse select February 28, 2027, Apply, then Find Tee Times | Target absent from accepted/submitted dates | February 1 and 28 reach the submitted search; single-date live action remains disabled |
| Non-Monday months, disabled bounds, weekday header, following padding | Existing behavior | Preserved |

[Before popup](context-review/window-2032-03-980x640-mouse.png) and [after popup](context-review/after/window-2032-03-980x640-mouse.png) were inspected: March 25 becomes highlighted and the selected count rises from two to three. These are 440×478 popup captures from a 980×640 logical application window. The diagnostic presses Space afterward; in the repaired run this correctly **deselects** the newly mouse-selected date. Its `keyboard_selected_same_day=false` field is expected toggle behavior, not a keyboard regression. The dedicated regression separately verifies direct mouse→Apply→submitted search.

## Verification

| Evidence class | Result |
|---|---|
| **Failed exact-baseline regressions** | Identical final module on clean PR21: **8 methods, 4 pass / 4 fail**, 24 assertion/subtest failure records, zero errors/skips. [Metadata](new-tests-baseline.json), [log](new-tests-baseline.log). |
| **Passed repaired regressions** | **8/8**, covering 28/30/31-day Monday months, selection/removal, preceding/following padding, click/double-click, all six other starting weekdays, disabled bounds, headers, navigation and accepted/submitted dates. Actual Qt `currentIndex()` locates cells independently of application arithmetic. [Metadata](new-tests-after.json), [log](new-tests-after.log). |
| **Passed aggregate** | **266/266 = 138 desktop CI-selected + 91 cache/integrity + 37 additional booking/rendering**, zero failures/errors/skips, 23 fresh module processes, sockets/browser blocked. [Summary and source/test hashes](validation/summary.json), [runner](run-focused.py). PR16–21 and earlier filter/date/keyboard/booking fixes revalidated. The normal 11-test lifecycle module ran once. |
| **Separate diagnostics** | **50/50 filter scenarios**, 9/18 holes × Any/1–4 players × five presets ([JSON](journeys.json)); **5/5 startup/fallback decisions** ([JSON](startup-decisions.json)). Worker/scheduled work intercepted. The 36 popup and eight normal-app mouse actions above are separate diagnostics, not additional unit tests. Five separate offline-link scenarios reproduce a deferred defect below. All final probes report zero callback errors. |
| **Offscreen/source checks** | Before/after popup images and [compact recovery view](compact-980x640.png) inspected. Python compile, CRLF-aware whitespace, checksum-verified actionlint 1.7.12 and [independent review](review.md) pass. [Journey/design scope](journey-scope.md). |
| **Not performed** | Installed/native Windows or Android UI, touch, screen readers/DPI/resume, live provider/shared-network recovery, booking/holds, installed updates/signatures, alert worker execution or notification delivery. |

Tested application SHA-256 `b439bb2ba3a4449d2cf039a1c9146ec361a5d47fec600ed1c06b395c1db4fbd8`; new test SHA-256 `e046b5511d05345be8dc197c7867b7872b9fd107b7570cc5f2569b5327b54530`. Local pre-commit evidence distinguishes the parent commit from changed-file hashes. The draft records final remote head, all-event/attempt CI, checkout commits and PR merge-tree equality after publication. Windows offscreen CI is source testing, not an installed-app test.

## Deferred findings and limits

- **Confirmed, deferred:** an all-missing multi-date cache search hides configured static direct-course links. Altone Park alone loses its link; a mixed selection loses Altone/Boddington links. One loaded empty snapshot makes those links appear. Five configured-site scenarios used empty temporary local cache and intercepted actions. [Evidence](deferred-offline-links/README.md). A later focused change should preserve unavailable wording/retry guidance and expose selected static links once, without implying checked availability. Today's single repair stays focused on date selection.
- Exploratory failures are retained: the first system-Python invocation lacked PySide6 and stopped before app import; an early selector chose duplicate adjacent-month day numbers; a later fixture used unsettled geometry. These are not valid product counts. Stable geometry and the normal app popup independently confirmed the defect; final identical-file regressions passed on their first repaired execution. [History](context-review/NOTE.md). No assertion or timeout was weakened.
- **Historical Windows `cache_close` remains unresolved:** PR14 push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and timed out one child at 30 seconds. Later green checks and 40 Linux non-reproductions do not prove a cause or repair. Exact-source Windows pairing and a failing-child stack remain **pending/unavailable** here, not denied. No repeated Linux diagnosis. [Authoritative follow-up](../2026-10-21-midnight/ci-followup/REPORT.md).
- Earlier Qt event-pump stalls, four WebEngine sandbox-helper blocks, obsolete cron assertion, fixture-write denials, interrupted work and other historical tooling/fixture failures remain documented. No sandbox or denial was bypassed.
- Parent monitoring already reported November 17 false-zero weather recovery and known Wembley product errors/calendar observations. This pass did not repeat that health watch or access providers. PR3 is Quick18-specific; PR5/7 and #4→#6→#8 remain existing unmerged repairs. Successful workflows or calendar products do not establish exact live bookability or observation freshness.
- Canonical desktop/mobile/service source and existing per-course freshness/subset changes remain pending. The cache suite includes 27 inert alert-bundle integrity tests; zero-watch executions do not verify delivery. Existing persisted blank-error records remain PR21's documented limitation.

The fix makes visible dates respond consistently to mouse and keyboard. It adds constant date arithmetic, no request or eager UI work; no benchmark or user-feedback claim is made. Broader onboarding/freshness clarity, submitted-filter summaries and design proposals remain review decisions. No redesign, monetization or product-direction change was implemented.

No merge, deploy, release, production/manual workflow dispatch, credential/security change, spending, third-party contact, live booking/hold or real notification occurred. No denied or uncertain write remains.
