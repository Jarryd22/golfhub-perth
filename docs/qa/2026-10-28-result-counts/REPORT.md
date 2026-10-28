# Matching-course counts — 28 October 2026

One exact Araluen tee time plus a Wembley calendar-only result was reported as **1 matching tee time across 2 courses**, even when Wembley's calendar said full or unreleased. Only Araluen had a tee-time card. The focused repair reports **1 matching tee time across 1 course**, retaining both cards and the calendar's separate information.

## Scope and prior work

Branch `fix/desktop-matching-course-count-20261028` starts from unchanged draft #16, `62d1b1c569e3a47004ef85eb6de9133054f354d2`. The [context audit](context-audit.json) inspected 20 branches, all 18 non-cache/news source refs and the 14 open drafts #3–16 before choosing work. Every source ref retained the incorrect single-day subtraction; none contained this repair. Main remains `25de15b`. PR15's offline validator and PR16's missing-snapshot treatment are preserved, not duplicated. Original October 22 and completed October 27 worktrees remain untouched.

No AGENTS.md or checkout `.agents/skills` instructions were found. The selected executor is Linux, Python 3.12.14 and PySide6/Qt 6.11.2, offscreen at default scale 1, host UTC, with isolated writable app/cache directories. The reviewed remote desktop identifies itself as v5.0; the newer local desktop/mobile candidate remains unavailable and canonical-source reconciliation is still pending.

The old status count was `live_count - no_match_count`. A non-error calendar-only result contributes to the first term and is excluded from the second, so it always inflated the count. Six added and two removed application lines count non-direct results with filtered exact rows, matching the existing multi-day rule. Counts use submitted filters, and each row-bearing course counts once. The zero-match status uses the same count. Available-calendar-only wording retains precedence. No filter, row, card, link, provider, date, cache/freshness, worker or notification behavior changes.

## Before and after

[Original probe and provenance](before/FINDINGS.md), [before JSON](before/probe.json), [after JSON](after/probe.json), [reusable probe](count-probe.py), [before screenshot](before/one-time-plus-full-calendar.png), [after screenshot](after/one-time-plus-full-calendar.png). All use synthetic data with sockets/browser paths blocked and no worker launch.

| Scenario | Exact #16 status | Repair status |
|---|---|---|
| One exact row + available calendar | 1 matching tee time across 2 courses | 1 matching tee time across 1 course |
| One exact row + full calendar | 1 matching tee time across 2 courses | 1 matching tee time across 1 course |
| One exact row + unreleased calendar | 1 matching tee time across 2 courses | 1 matching tee time across 1 course |
| Full/unreleased calendar alone | 0 matching tee times across 1 course | 0 matching tee times across 0 courses |
| Available calendar alone | Wembley booking-availability wording | Unchanged |

The eight new methods compare status with actual tee-time cards. They cover calendar states, filtered-out courses, inclusive time/player boundaries, many rows per course and Show all, direct/error/empty-Collier exclusions, unselected results, submitted versus pending controls and single/multi-day consistency.

| Evidence class | Result |
|---|---|
| **Failed exact-baseline regressions** | Eight methods: **3 pass, 5 fail**, with **8 failing assertions including subtests**, zero errors/skips. [Log](new-tests-baseline.log), [metadata](new-tests-baseline.json). The metadata failure count is assertion/subtest count, not failed-method count. |
| **Passed repaired regressions** | **8/8** methods pass, zero failures/errors/skips. [Log](new-tests-after.log), [metadata](new-tests-after.json). |
| **Passed aggregate automated checks** | **202/202**, fresh process per module, blocked sockets/browser. Breakdown: **95 desktop CI-selected + 70 cache/integrity + 37 additional booking/rendering checks**. [Summary](validation/summary.json), [runner](run-focused.py). |
| **Passed source-widget matrix** | **50 scenarios**: 9/18 holes × Any/1–4 players × five time presets, submitted dates and synthetic partial-cache rendering. Worker launch intercepted. PR16 missing-date wording remains correct. [JSON](journeys.json), [runner](journeys.py), [log](journeys.log). These are diagnostic scenarios, not extra unit tests. |
| **Offscreen visual inspection** | Current 1280×800 before/after images inspected: matching-course status corrected while both cards remain. [980×640 view](compact-980x640.png) inspected during prior-fix revalidation; recovery guidance remains reachable. No native UI claim. |
| **Passed static/review checks** | Python compile, CRLF-aware whitespace, checksum-verified actionlint v1.7.12 and [independent review](review.md). [Hashes/static metadata](review-metadata.json). |
| **Source/metadata inspection only** | Update repositories still only main, no open PRs; Windows 5.1.17 / Android 0.1.19 release metadata and asset sizes/digests unchanged. No new manifest download, signature or installed-update test. |
| **Not performed** | Native installed Windows/Android, screen readers/DPI/resume, complete cold-start provider/network journey, live booking/hold, installed updater and real notification delivery. Windows paired timeout diagnosis remains unavailable here. |

The aggregate covers window construction, course input/selection and round changes, Perth dates/midnight/keyboard selection, player/time filters, lazy date rendering, saved/missing multi-date cache states, booking URL/plan/opt-in/release guards with mocked dialogs, search races and the unchanged standard worker module. Booking scripts are inspected as generated strings, never sent to providers. Cache weather/budget tests and PR15 integrity tests run; this does **not** validate current published weather or execute an alert worker. No test was loosened.

Local pre-commit metadata names the checked-out #16 parent and separately identifies modified files by hash; it does not imply an uncreated commit was tested. Application SHA-256 `55e381413d3681c3afff01cfb5ced3b99675b7a5d8089e3ce10a29a8782879a6`; new test SHA-256 `76c8627c6bf4cc9854d96358a185ca0b54ec53b5d4484b9055d68d99c2ca2b24`. Exact remote-head CI and all events/attempts are recorded on the draft after publication. Desktop CI now selects 95 tests; Linux cache/integrity CI selects 70 plus actionlint.

## Remaining findings and decisions

- **Historical Windows timeout remains unresolved:** #14 push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438) passed 76 tests and failed `cache_close` at 30 seconds. Later green checks and 40 Linux non-reproductions do not establish a cause or fix. The missing failing-child stack/same-platform pair still require Windows/Python 3.12.10/Qt 6.12.0. That diagnostic is **pending/unavailable**, not denied: this executor is Linux and no connected desktop is available. Only the unchanged standard lifecycle module ran once in the aggregate; no paired Linux investigation or timeout relaxation was repeated.
- **New reproduced backlog finding, deliberately deferred:** loaded provider-error dates still get no-match summary/day titles despite correct unavailable warnings. A Collier error card additionally says no public tee times are showing. The [same before/after JSON](before/probe.json) retains these contradictory labels; this count fix does not change them. A focused follow-up should distinguish failed observations from verified empty results across single/multi-date and Collier wording, with native/canonical integration separately reviewed.
- The prior Qt 6.11 manual-pump stall, four WebEngine sandbox-helper blocks and obsolete cron assertion remain outside this focused suite. Prior #15 fixture-write denials and October 27's corrected fixture-time failure remain in their dated reports; they are not converted to passes or retried here. Today's repaired checks have no failed execution; exact-baseline failures above are retained.
- Supplied 07:53 Perth monitoring already covers the published 56-payload cache and November 12 false-zero weather. PR8 and #4→#6 dependencies cover that forecast defect; PR3 is Quick18-specific, not a Whaleback/MiClub repair. No hourly watch or competing provider/weather fix was performed. Zero-watch alerts do not prove delivery.
- Canonical desktop/mobile reconciliation and review of the existing unmerged reliability chain remain the product/integration decisions. No redesign or release direction was implemented.

Production workflows are byte-unchanged; only the new regression module joins existing test workflow filters/list. No merge, deployment, release, production dispatch, manual CI rerun, credentials/security change, spending, third-party contact, booking/hold or real notification occurred.
