# Perth midnight daily QA — 21 October 2026

A desktop left open across Perth midnight kept yesterday labelled **Today**, retained yesterday's 28-day bounds and submitted yesterday on a new Find Tee Times request. The focused repair rebases editable date controls while preserving the absolute dates of already submitted work and displayed results.

## Scope and provenance

Base: unchanged draft #13, `8b01866f3783d9ef021e114c81c139dede1facc1`, after dependent drafts #9→#10→#11→#12. Branch: `fix/desktop-perth-midnight-20261021`. The original `/workspace/golfhub-perth` checkout remained clean on main `25de15b`; work used separate repair and exact-base worktrees. No repository AGENTS.md or .agents/skills were present. A [current context audit](context-audit.json) inspected 15 main/fix/agent refs and all 11 open drafts #3–13; no existing midnight repair was found. No previous branch was rewritten.

This is Linux source-widget testing, Python 3.12.14, PySide6/Qt 6.11.2, offscreen, isolated runtime/cache directories, with blocked sockets and browser calls. Host UTC; mutable fake UTC instants are converted through the actual Perth-day helper. Visual probes use 980×640 logical pixels at the default offscreen scale. The reviewed remote source identifies itself as the v5.0 line; newer dirty desktop/mobile candidate source was unavailable and untouched.

## Before and after

The [identical diagnostic probe](baseline-probe.py) advances UTC `2032-12-31T15:59:59Z` to `16:00:00Z`, crossing Perth into 1 January 2033. It opens real Qt widgets and intercepts the cache launch; no native worker or provider is involved.

| Observable | Untouched #13 | Repair |
|---|---|---|
| Selected date after yesterday expires | 2032-12-31 | 2033-01-01 |
| Relative label | Today / 31 Dec | Today / 1 Jan |
| Minimum / maximum | Dec 31–Jan 27 | Jan 1–Jan 28 |
| Newly submitted cache search | Dec 31 | Jan 1 |
| Valid absolute selected date | Retained | Retained; Tomorrow becomes Today |
| Submitted context and lazy result dates | Retained | Retained |

[Before JSON](baseline-probe.json), [after JSON](after-probe.json), [before picker](picker-before.png), [after picker](picker-after.png), [before window](window-before.png), [after window](window-after.png). Screenshots were inspected: the baseline picker can say Today is Jan 1 while still selecting Dec 31; the repaired picker selects Jan 1 with the correct range. Known date punctuation corruption remains the existing reconciliation backlog, not a new cosmetic rewrite.

## Repair behavior

Only the app's date control opts into a rolling Perth window; standalone fixed-range controls retain their existing semantics. An owned 30-second timer refreshes idle controls; activation, search parameters, opening the picker, and applying/toggling picker dates also recheck the clock. The timer is stopped by normal/deferred close; native worker-cleanup timers are unchanged.

Keep valid absolute selections, remove dates outside today through today+27, and use today if none remain. Do not add the new last day to an existing 28-day selection. Open-popup pending choices follow the same rule without being applied automatically; Cancel still discards them. Clear expired date formatting and update the Today banner and month navigation. Emit datesChanged only for an actual final selection change. Independent review found an intermediate Apply notification; silent rebasing during Apply plus a final comparison fixes it, with a regression. [Independent review notes](review.md) report no remaining blocker and verify cursor/page preservation, newly enabled month navigation, fixed-range controls and close-time suppression.

Do not mutate submitted context, active/queued cache requests or already rendered/lazy result dates. A live fallback explicitly carrying an earlier submitted context keeps its original date; a new user-initiated live search uses the refreshed controls. No automatic search, worker lifecycle rewrite, freshness/subset rewrite, provider call, booking or notification change is introduced.

## Verification

| Check | Untouched #13 | Final source |
|---|---:|---:|
| Identical 15 new regressions | 4 pass, 10 failing methods, 1 missing-timer error | 15 pass |
| Existing focused desktop tests | Prior report: 62 pass | 62 pass |
| Offline cache tests | Prior report: 43 pass | 43 pass |
| Compile / CRLF-aware whitespace / actionlint v1.7.12 | — | Pass |

The baseline has 12 failing assertions including subcases, separate from the missing-timer error. [Baseline log](new-tests-baseline.log), [baseline metadata](new-tests-baseline.json), [after log](new-tests-after.log), [after metadata](new-tests-after.json), [120-check summary](validation/summary.json), [static checks](validation/static-checks.json). The [runner](run-focused.py) isolates each module and records source/test hashes. Fifteen new methods cover fresh cache/live submissions, preserved submitted fallback, relative labels, 28-day pruning, long suspension, UTC midnight, leap/month/year transitions, picker pending/cancel/apply, one final selection notification, timer delivery, activation and submitted lazy results. The timer test runs a real bounded QEventLoop with an accelerated interval; live worker construction is mocked. Existing 11 lifecycle cases use actual worker subprocesses and remain separate from those mocks.

Source SHA-256: `214cf0e3cff96f5014c75d70178abf8ca1470c0d271bad64a0c5734677a6ba50`.
New test SHA-256: `4c783f5aebdd05ae60111a5d7572fed086d4894624f630d982cd58c14a07c73f`.

Windows test-only CI now selects **77 desktop tests**; the existing Linux cache job selects **43 tests and actionlint**. Production workflows are main-only or dispatch-only, so this repair push/draft triggers tests only. Final commit/remote/CI results are recorded in the draft PR description after publication; the local validation log records its pre-commit parent and working-tree hashes to avoid implying it ran against a yet-uncreated commit.

## Limits and remaining work

- The prior Qt 6.11.1 manual-event-pump journey stall remains unresolved; today's focused tests use the installed Qt 6.11.2 and do not repeat or clear that harness issue. Four WebEngine tests remain blocked by the earlier sandbox-helper restriction and were not retried. The obsolete cron assertion is outside this focused suite and remains a known baseline failure.
- Windows 5.1.17 and Android 0.1.19 latest-release API asset URLs/sizes/digests match the 20 October evidence. Update repository main refs remain Windows `b53909b…` / Android `cfec2bb…`. Today did not download or verify signed manifests/binaries, run the installed updater, or validate native Windows/Android, screen readers/DPI, actual OS suspension/resume or notification delivery. No hourly health audit was duplicated.
- Newer dirty desktop/mobile source, per-course freshness and subset preservation remain pending canonical reconciliation. These source repairs are unmerged and are not claimed as installed-release behavior.
- The gh CLI API returned Forbidden; connected GitHub tools and Git transport provided the required access. System `go run` was unavailable (`Go: Unknown option: run`); checksum-verified actionlint v1.7.12 release binary performed validation instead. These were resolved tooling limitations, not approval denials. No sandbox restriction was bypassed.

No merge, deployment, release, production workflow dispatch, credential/security change, spending, third-party message, booking/hold or real notification occurred.
