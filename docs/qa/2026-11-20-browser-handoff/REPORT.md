# Browser handoff feedback — 20 November 2026, Perth

Golf Hub silently ignored a browser launch returning `False`; launch exceptions could escape its Qt button callbacks. This affected eight course/booking handoff paths. On exact [PR32](https://github.com/Jarryd22/golfhub-perth/pull/32), controlled button presses reproduce eight silent failures and 16 escaped exceptions. Successful handoffs and cancellation/consent guards remain correct.

The focused repair attempts the same address once, catches only `OSError` and `webbrowser.Error`, and shows a parented warning with the exact address for manual opening. The new dialog uses the existing time-range warning's local button style and plain, selectable text. It does not retry automatically, change destinations, infer provider availability, or treat a browser's `True` return as successful page loading or booking.

Branch `fix/desktop-browser-handoff-20261120` is stacked directly on PR32, baseline `66eaf00f76e748cf6f76ef6a758574a3d996360c`. Application changes are one helper and eight call substitutions; prior search, provider, weather, worker, booking-plan and workflow code remain unchanged.

## Inspection and selection

The [repository audit](repository-audit.json) observed **37 branches, 30 drafts #3–32 and zero non-PR issues at 08:48:56 Perth**. Only PR32 was newly added since the previous audit. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`. Both update repositories/README blobs and all five workflows are unchanged. Android's designated latest is **0.1.19**, not the older first-listed 0.1.8; Windows remains **5.1.17**. These are repository/release metadata observations, not updater, signature or installed-device tests.

The [duplicate audit](duplicate-audit.json) inspected **35 non-data source refs and 26 preserved local/archive Qt files**. All 61 copies have eight unchecked browser calls, with no competing browser-failure feedback repair. Existing booking-plan warnings precede the browser call and do not handle its failure. Earlier booking-context and offline-link repairs address different behavior. Prior reports, cumulative docs and local QA-only evidence were read; the original dirty checkout and all earlier branches/evidence are preserved. No applicable ancestor/checkout AGENTS or `.agents/skills` was found, including the new worktree's paths.

Installed Python's `webbrowser.open` source documents a boolean success result; its platform-conditional Windows implementation converts `os.startfile` `OSError` into `False`. This was read as source only: no Windows/browser invocation occurred. Controlled failures establish reachable handling defects, not their natural production frequency.

## Before and after

| Check | Exact PR32 before | Final repair after |
|---|---|---|
| Eight handoff routes × `False` | No launch-failure message | One warning, exact unchanged URL and initiating parent |
| Eight routes × each of `OSError` / `webbrowser.Error` | 16 exceptions reach captured Qt callbacks | Handled, one warning per action, no callback exception |
| Eight routes × `True` | Correct destination, no failure warning | Preserved; no claim that the page loaded |
| Missing links, cancel, confirmed-plan handoff | Existing guards pass | Preserved; no real hold/browser/WebEngine execution |
| Actual VIEW COURSE Space at 980×640 / 1280×800 | Browser returns false; no modal | Visible warning, readable OK and exact address |

Eleven methods are added to the existing CI-selected booking-context module. Its original eight-method class and helpers remain AST-identical. The **same final test file** gives **11 passed/eight failed methods on baseline**, with **24 assertion records**, zero errors/skips; the repair passes **19/19**. The eight outcome-matrix methods cover **32 subscenarios per source**, with four missing-link subscenarios and separate cancel/confirmed-plan controls. These are not additional unittest methods. [Commands, hashes and execution history](regressions/scope.md), [baseline](regressions/baseline/result.json), [repair](regressions/repaired/result.json).

The final real-modal probe has **four cases / 68 named assertions**, all passing: direct and long booking addresses at both viewport sizes. Actual Space, OK Return and intercepted successful mouse retry are exercised. Short and long dialogs fit (353×125 and 525×155); rendered OK uses amber `#f59e0b` with dark `#090909` text. Shown label/message flags permit mouse and keyboard selection, and text stays plain. Screenshots were inspected. No Ctrl+A, clipboard transfer, browser page, screen reader or installed-device copying was tested. [Modal evidence and limitations](browser-modal/scope.md).

A distinct keyboard expansion journey on unchanged PR32 passes **84/84 named assertions at two viewports**, with four intercepted BOOK callbacks: Tab/Shift+Tab/Space, show-all/first-12, hidden-row focus exclusion, lazy date construction/reopening and submitted context after pending filter edits. No expansion defect or extra repair was justified. [Scope and evidence](keyboard-expansion/scope.md).

## Final validation

**361 tests passed = 229 desktop CI-selected + 95 cache/integrity + 37 additional**, across 28 isolated module processes; zero failures, errors or skips. [Final summary/logs](final-aggregate/summary.json). This includes PR32's 15 startup regressions, search/date/9–18-hole/group/time/course controls, retained booking context, empty/error/offline recovery, cache validation and data-only alert bundle integrity. It does not send notifications or execute the alert runtime. The existing real Linux lifecycle module runs in the aggregate; it does not diagnose the historical Windows timeout.

Python compilation, actionlint 1.7.12, whitespace checks and [independent review](review.md) pass. No existing assertion or production timeout was loosened. Final source SHA256 is `bbf50a775cfbfbe8e126fac8b0fd958545d7455567fc76d72e9aac5ff0cc7403`; final regression SHA256 is `e0aa2858de8a0e5ab940d9003f78c8e23e4c3816cc6df71ab83f3a5ef63f7e2c`.

Commands from `/workspace/golfhub-20261120`:

```sh
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-20-browser-handoff/regressions/run-booking-tests.py --root /workspace/golfhub-20261119-repair --test-file /workspace/golfhub-20261120/tests/test_booking_context.py --output docs/qa/2026-11-20-browser-handoff/regressions/baseline
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-20-browser-handoff/regressions/run-booking-tests.py --root /workspace/golfhub-20261120 --test-file /workspace/golfhub-20261120/tests/test_booking_context.py --output docs/qa/2026-11-20-browser-handoff/regressions/repaired
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-20-browser-handoff/run-aggregate.py --root /workspace/golfhub-20261120 --output docs/qa/2026-11-20-browser-handoff/final-aggregate
/workspace/golfhub-perth/.venv/bin/python -m py_compile app/qt_golfhub_app.py tests/test_booking_context.py
/workspace/scratch/actionlint-1.7.12/actionlint
git -c core.whitespace=cr-at-eol diff --check
```

Regression/modal scripts originally ran at scratch paths before byte-identical copying; their provenance records exact arguments. Linux, Python 3.12.14, Qt 6.11.2, offscreen platform, isolated writable runtime directories; source declares `APP_VERSION = "5.0"`. Sockets/DNS/browser/provider/worker bodies are blocked or intercepted in the focused probes. This is not the public Windows 5.1.17 or Android package. Local logs record starting HEAD plus changed source hashes; published exact head and terminal CI results are recorded after publication in the PR/task result. [Artifact manifest](evidence.json).

## Failed and intermediate executions retained

- The initial regression run reproduced the same 24 product failures plus **three test-fixture ownership errors**: tuple unpacking discarded a standalone card before clicking its button. Retaining the owner corrects only the fixture; the original file/log and corrected baseline are preserved.
- An initial static-warning repair passed 19 focused and 361 aggregate tests, but actual visual inspection found its default OK text dark on dark. Those results remain under `regressions/pre-visual-review/` and `pre-visual-review-aggregate/`; they are not final visual approval.
- The constructed-dialog revision initially applied selection flags before styling. Its focused run and full aggregate caught **24 keyboard-selection assertion records across eight methods** (361 aggregate methods executed, 353 passed). Plain Qt reproduces the stylesheet resetting those flags. Moving the assignment after styling passes the unchanged final assertions and actual shown-dialog inspection. Failed source bytes/results remain under `regressions/pre-style-selection-failure/` and `pre-selection-order-aggregate/`.
- The first real-modal after probe has **two automatic focus-return assertion failures**. A plain Qt control without Golf Hub also loses `activeWindow`/`focusWidget` after dismissal in this offscreen environment. Final recovery explicitly reactivates the host before retry; **automatic focus return is not claimed fixed or verified**. All original failures, reference checks and intermediate inspections remain in `browser-modal/`.

Historical Windows `cache_close` remains unresolved: [original failure and follow-up](../2026-10-21-midnight/ci-followup/REPORT.md). Later green source/CI checks do not diagnose it. Earlier manual-pump stalls, obsolete cron assertion, four blocked WebEngine tests and previous fixture failures remain in their reports; this is the applicable aggregate, not every legacy test. No denied action was retried.

## Unperformed work and publication boundary

Not performed: native/installed Windows or Android, natural browser failure frequency, actual browser/page loading, live provider/bookability/holds, current cache/weather health monitoring, notification delivery, updater/assets/signatures, native accessibility/DPI/resume, clipboard use, or performance benchmarking. The hourly watch was not duplicated. Canonical desktop/mobile integration, historical Windows diagnosis and native modal focus/accessibility remain pending; no substantial product redesign is proposed or implemented here.

All five workflow files are byte-identical to PR32. Trigger inspection shows this repair branch invokes ordinary desktop push and desktop/cache PR tests; it does not match production main-specific pushes. No manual/production dispatch, denied docs-only PR, restricted endpoint/manifest route, merge, release, deployment, credential/security change, purchase, external communication or live transaction occurs. Exact remote head and all-event CI outcomes will be checked before the final task result.
