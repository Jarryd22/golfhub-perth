# Repeated-search cache-to-live recovery — 17 November 2026, Perth

A confirmed controller defect can leave a repeated search displaying **Checking the shared cache** after all work has ended. When a previous live request has delivered its terminal result but its thread reference is still retained, Find remains available. If the new single-date cache request returns no data before that old reference is released, `search_live()` rejects the fallback. Neither cleanup callback resumes it. The user can retry manually, but the existing in-progress message is false.

This focused repair retains that submitted fallback and starts it once the old live ownership is released. A newer valid Find request supersedes it; invalid input does not, and accepted close cancels it. Cache hits remain immediately usable. A small result-pending flag distinguishes a completed old request from a newly accepted live request, preserving busy controls even if `isRunning()` is false before terminal delivery. Provider logic, timeouts, native thread ownership, persistence and workflows are unchanged.

Branch: `fix/desktop-cache-live-handoff-20261117`, based directly on [PR30](https://github.com/Jarryd22/golfhub-perth/pull/30), `a3e522b5e2d79856f994fb342a7c6b1253a1143d`. This is an application repair; the previously denied documentation-only branch is not being republished or retried.

## Inspection and reproduction

The [repository audit](repository-audit.json) found 35 branches, 28 drafts #3–30, no non-PR issues, unchanged main `25de15b65af6f9dcad4a4d13788fb87ab976df31`, and unchanged README-only Android/Windows update repositories. Releases remain Windows 5.1.17 and Android 0.1.19; metadata inspection is not updater/device verification. All five workflow hashes match prior inspected definitions. No applicable ancestor/checkout AGENTS or `.agents/skills` was found.

The [duplicate audit](duplicate-audit.json) compared 33 immutable source refs and 21 preserved local/archive Qt sources, including relevant methods and cleanup call paths. None defers this fallback. PR25 covers Refresh Live ownership and a successful overlapping cache hit; it does not repair the missing-data ordering. Original dirty work and prior local verification branches remain preserved. November 15/16's local-only reports and their 74/119 tests remain historical; their documentation chain is not included in this repair branch. Their [recorded evidence was inspected](prior-local-evidence-audit.json).

The initial controlled diagnostic ran on local documentation head `663a21fc5ec25b6a74b0c60c3467b67d6fe19b2b`, whose Qt runtime byte-matches PR30. Four affected orderings cover failed/cancelled old live requests, each with cold or previously displayed results. Two controls cover a cache hit before old cleanup and a miss after old cleanup. Actual Find/Refresh/Stop buttons and real QObject terminal signals are used, with inert thread stand-ins; no native timing or provider call is exercised.

| Observation | Before | After |
| --- | --- | --- |
| Four affected orderings | Only old live + cache threads were constructed; both owners cleared; no fallback. Header/body still said checking shared cache, with no progress or rows. | Exactly one additional live worker is started with the submitted January 5 / nine-hole / one-player / Morning context. Header becomes live-refresh-in-progress, and busy controls remain consistent. |
| Cache hit before old cleanup | Cached results render; no extra live request. | Preserved, including enabled Find and hidden progress immediately after cache cleanup. |
| Miss after old cleanup | Normal live fallback starts. | Preserved. |

See [before observations](probe-before/probe.json), [after observations](probe-after/probe.json), [journey scope](journey-scope.md), [provenance](journey-provenance.json) and the preserved scripts/logs. Before's four affected cases observe the defect; the diagnostic's exit 0 means a clean fixture, not four passing product journeys. After adds explicit recovery/start-once assertions. Formal failing regressions below establish pass/fail independently.

## Regression and aggregate results

The final identical 22-method test file was run against exact PR30 source and the repair:

- **Baseline:** 14 passed, eight failed, zero errors/skips. All ten original tests passed. The eight failures assert the absent fallback in six terminal/out-of-order cleanup cases, invalid-input retention, and the replacement-worker ownership case. [Result](baseline/result.json), [log](baseline/test.log).
- **Repair:** **22/22 passed**, zero failures/errors/skips. Twelve methods are added; every original method/helper remains AST-identical. [Result](final-focused/result.json), [log](final-focused/test.log).
- **Final aggregate:** **342 passed = 210 desktop CI-selected + 95 cache/integrity + 37 additional**, in 28 isolated module processes, zero failures/errors/skips. The unchanged lifecycle suite ran once as part of this aggregate; there was no repeated Linux diagnosis of the Windows timeout. [Summary](final-aggregate/summary.json).
- Python compilation, actionlint 1.7.12 and [independent source/evidence review](review.md) passed. Existing assertions and timeout bounds were not loosened.

Coverage includes success/failure/cancellation, both cleanup orders, newer queued single/multi-date requests, invalid submission, close, cache hits, retained date/round/player/time context, starting once, simulated result saving/rendering and intercepted BOOK context. Original startup, date/calendar, course/player/time, empty/error/offline, booking guard, cache persistence and alert-integrity regressions are included in the aggregate. Alerts remain data-only integrity checks; no bundled worker or notification delivery is executed.

Commands, from `/workspace/golfhub-20261117-repair`:

```sh
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-17-cache-live-handoff/run-handoff-tests.py --root /workspace/golfhub-20261113 --test-file /workspace/golfhub-20261117-repair/tests/test_live_button_state.py --output docs/qa/2026-11-17-cache-live-handoff/baseline
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-17-cache-live-handoff/run-handoff-tests.py --root /workspace/golfhub-20261117-repair --test-file /workspace/golfhub-20261117-repair/tests/test_live_button_state.py --output docs/qa/2026-11-17-cache-live-handoff/final-focused
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-17-cache-live-handoff/run-aggregate.py --root /workspace/golfhub-20261117-repair --output docs/qa/2026-11-17-cache-live-handoff/final-aggregate
/workspace/golfhub-perth/.venv/bin/python -m py_compile app/qt_golfhub_app.py tests/test_live_button_state.py
/workspace/scratch/actionlint-1.7.12/actionlint
```

Python 3.12.14 / Qt 6.11.2 / Linux offscreen, isolated runtime directories and blocked network/browser/provider actions. Focused runs use the selected source root with the same external test file; the original PR30 checkout stays clean. Candidate runs record HEAD PR30 plus uncommitted source hashes, not a falsely claimed new commit:

- Before Qt SHA256: `09b17e1a6a89a164d96ed6fc82413d0fa9f64d37244736b225a1150a12736ca1`.
- Final Qt SHA256: `e739043b8c4e60556cee1b713fe28464d2dc72242b39b02df4c99d8ffca94927`.
- Final test SHA256: `2192ab164afc11a0d4747a1e35e835821edb7c9ad85c0a58d975cc31d780689b`.

## Retained failed/intermediate evidence

The first diagnostic had eight callback TypeErrors because its fake `quit` adapter incorrectly accepted no signal arguments. Its script/log/JSON/image and lossless correction diff remain in [initial fixture evidence](initial-fixture-callback-arity/before/probe.json); only the adapter was corrected before clean reproduction. The earlier clean four-case replay and later two controls remain separate. The [before provenance](before-provenance.json) records these stages.

Review added a meaningful thread-start assertion to the new regression helper. The prior test file and first baseline/focused runs remain in `pre-review-start-assertion/`; the final strengthened file was rerun against both source versions and produced the counts above. After-only diagnostic assertions and their compressed diff are also retained. No runtime fix was made to hide a fixture failure.

Historical failures remain unresolved or recorded in their original reports: the [Windows cache_close timeout](../2026-10-21-midnight/ci-followup/REPORT.md), with 76 passing tests and one timed-out child; PR30/PR29 baseline failures; the responsive-grid intermediate failure; and prior fixture/static-check corrections. Later green CI and 40 Linux non-reproductions do not diagnose the Windows failure. This repair addresses a distinct, deterministic controller handoff and does not claim to fix native shutdown.

## Limits and publication boundary

Not performed: installed Windows/Android, native Windows thread scheduling/cleanup or natural production incidence of this controlled handoff, live provider/cache/weather monitoring, real bookings/holds, notification delivery, screen readers/touch/DPI/resume, updater/signatures or performance benchmarking. The unchanged 11-method lifecycle module does exercise real Linux QThreads once in the aggregate; it does not validate the new handoff under natural native scheduling. Offscreen captures illustrate controller states; they do not establish native UI behavior or user feedback. Canonical desktop/mobile release-candidate reconciliation remains pending. Existing weather #4/#6/#8, Wembley and Quick18 repairs remain separate and unmerged; no duplicate health watch or provider repair was attempted.

This committed report records local prepublication validation. Remote branch, draft PR and exact-head CI results are established separately in the PR description and final task result only after verification. Normal repair push/PR CI is authorized; production triggers were checked by unchanged workflow hashes and are not selected by this branch/PR. No manual workflow is dispatched.

The parent-reported approval denial for November 14's docs-only PR remains in force; its original stated reason was not supplied. That action, denied production-history endpoint, restricted directory and restricted manifest reads were not retried or routed around. No merge, deployment, release, credential/security change, spending, outreach, live booking or notification occurs in this pass.
