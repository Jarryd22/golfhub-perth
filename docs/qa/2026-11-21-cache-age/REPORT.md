# Usable cache rows survive malformed age metadata — 21 November 2026, Perth

A saved snapshot with valid course/tee-time rows and a truthy non-string `generated_at` value is accepted by the cache loader, but raises `AttributeError` while formatting its age. On first launch, that interrupts saved-result rendering **before the automatic shared refresh is scheduled**. Controlled files reproduce the problem on exact [PR33](https://github.com/Jarryd22/golfhub-perth/pull/33); no natural producer incident is claimed.

The repair changes one guard in `cache_age_label`: non-string metadata uses the existing **“saved earlier”** fallback. Valid rows and snapshot bytes remain usable and unchanged. Schema validation, downloads, persistence, timestamp conversion, naive-timezone interpretation, refresh intervals, provider/weather logic and Qt UI code are unchanged. This does not establish that unknown-age data is fresh.

Branch `fix/desktop-cache-age-metadata-20261121` is based on PR33 at `4fe841359f1d0b3e4a261649c286f04d0bfbac54`.

## Inspection and before/after evidence

At **08:17:17 Perth**, the [repository audit](repository-audit.json) found 38 branches, 31 draft PRs #3–33 and zero non-PR issues. PR33 was the only new repair since the previous audit; main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`. Both update repositories, README blobs, release metadata and five workflows are unchanged. Android's designated latest remains **0.1.19**; the first-listed 0.1.8 is older. Windows remains **5.1.17**. These are metadata observations, not updater/device tests. Prior reports, cumulative checklist/backlog, local QA-only work and original dirty checkout were inspected and preserved. No applicable ancestor/checkout AGENTS or `.agents/skills` was found.

The [duplicate audit](duplicate-audit.json) found the same unguarded formatter across **36 current non-data refs and 25 known preserved local files**, with zero read/parse errors. PR19 validates result/row structure; PR32 fixes deferred startup request ordering; PR33 handles browser launch failure. None repairs this optional age-metadata path. The production refresh-index timestamp parser is separate. The hourly cache/weather watch was not repeated.

The [startup probe](startup-probe/provenance.json) loads seven real isolated JSON files through the actual loader, then delivers the window's real initial zero-ms Qt timer through `QApplication.exec()`. The later shared timer's `start(100)` is intercepted and recorded; no worker or provider executes.

| Metadata case | Exact PR33 before | One-line repair after |
|---|---|---|
| Valid aware ISO timestamp | Saved row, “5 minutes ago,” refresh scheduled | Unchanged |
| Explicit JSON null; invalid ISO string | Saved row, “saved earlier,” refresh scheduled | Unchanged |
| Truthy integer, boolean, array, object | Four `AttributeError` callbacks; initial prompt remains, no saved summary and no shared-refresh scheduling | Saved matching row, unknown-age label, one normal `start(100)` request each |

**Before: 3/7 recovery cases pass. After: 7/7 pass.** All 14 before/after case executions preserve original file bytes and have no worker owners. These are seven unique diagnostic cases, not 14 additional unit tests. The probe's case name `absent` writes explicit null; omitted metadata is separately covered by the final mixed-date regression. Root inspected the 1000×730 before/after captures: saved rows and unknown-age guidance replace the initial prompt. Existing date punctuation is a previously deferred issue, not changed here.

## Regression and journey results

Five methods are added to the existing CI-selected startup module. All original 15 methods, classes and helpers are preserved. The **same final file** on exact PR33 gives **16 passed/four errored methods**, with **11 `AttributeError` records**, zero assertion failures/skips. Final repair: **20/20 passed**, zero failures/errors/skips. Coverage includes JSON metadata types, aware/naive ISO controls, real saved-file startup, intercepted shared download and single-date rendering, mixed loaded/missing dates, lazy submitted booking context and byte preservation. [Commands and retained stages](regressions/scope.md), [baseline](regressions/baseline/result.json), [repair](regressions/repaired/result.json).

An independent, distinct recovery journey records **43/43 assertions** at 980×640: mixed saved/provider-error/missing dates → actual calendar narrowing → Find/live refresh → Stop → inert ownership cleanup → corrected course/round/player/time selection → successful fixture results. Three inert threads and two intercepted BOOK callbacks preserve prior context and saved files; zero persistence calls occur. Obsolete date sections disappear on successful replacement. No additional product defect was found. Candidate source was already present before this probe, with stable hashes; it is not relabelled as untouched PR33. Its launcher exit-status field was lost in a truncated tool response, while complete successful JSON/log and process completion were verified; no rerun was made solely to recover that field. [Precise input/interception scope](recovery-journey/scope.md).

**Final aggregate: 366 passed = 234 desktop CI-selected + 95 cache/integrity + 37 additional**, in 28 isolated module processes, zero failures/errors/skips. [Summary and logs](final-aggregate/summary.json). Earlier startup, PR33 browser failure, date/round/group/time/course filters, retained booking context, empty/error/offline handling and data-only alert integrity are rechecked. No alert runtime or delivery is executed. Python compilation, actionlint 1.7.12, whitespace checks and [independent review](review.md) pass. No test bound, assertion or production interval was loosened.

Commands from `/workspace/golfhub-20261121`:

```sh
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-21-cache-age/regressions/run-startup-tests.py --root /workspace/golfhub-20261120 --test-file /workspace/golfhub-20261121/tests/test_startup_cache.py --output docs/qa/2026-11-21-cache-age/regressions/baseline
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-21-cache-age/regressions/run-startup-tests.py --root /workspace/golfhub-20261121 --test-file /workspace/golfhub-20261121/tests/test_startup_cache.py --output docs/qa/2026-11-21-cache-age/regressions/repaired
/workspace/golfhub-perth/.venv/bin/python docs/qa/2026-11-21-cache-age/run-aggregate.py --root /workspace/golfhub-20261121 --output docs/qa/2026-11-21-cache-age/final-aggregate
/workspace/golfhub-perth/.venv/bin/python -m py_compile app/shared_cache.py tests/test_startup_cache.py
/workspace/scratch/actionlint-1.7.12/actionlint
git -c core.whitespace=cr-at-eol diff --check
```

Scripts originally executed at the scratch paths recorded in their provenance before byte-identical copying. Runtime: Linux, Python 3.12.14, Qt 6.11.2, offscreen; source declares `APP_VERSION = "5.0"`. Runtime directories are isolated; provider/network/browser/booking operations are blocked or intercepted. Local records identify the starting Git HEAD plus changed-source hashes. Exact pushed head and all-event terminal CI are recorded after publication in the PR/task result, not inferred from local hashes.

- Shared-cache source SHA256: `ca42e9054d611e8368556328266479b320baf96217c8a69d5997a198a448885d`.
- Final startup-test SHA256: `80c7676bb983b558adcbc092c8edea7530e3b4be9862c68403d33a6b692e63cc`.
- Unchanged Qt source SHA256: `bbf50a775cfbfbe8e126fac8b0fd958545d7455567fc76d72e9aac5ff0cc7403`.
- [Artifact manifest](evidence.json).

## Failed attempts and remaining limits

The first baseline test file reproduced the metadata errors. Review then moved a booking-handler patch before lazy construction so the fixture intercepts the bound callback; no repaired execution or unmocked modal used that earlier fixture. A subsequent repair run had **19 pass/one failure** because the new test incorrectly expected per-day `context["date"]`. Existing behavior retains the complete submitted range, while per-day URLs/accessibility identify each result date. The corrected oracle verifies the full range plus exact per-day result URL and row. Earlier files, baseline runs and the failed repair run are preserved; no date behavior was changed to satisfy the test.

The full staged whitespace check also found trailing spaces in three raw unittest progress lines. Original bytes are preserved as adjacent `test.raw.log.gz` archives; readable copies remove only trailing whitespace. [Normalization record](regressions/whitespace-normalization.json) retains hashes and the failed check. An initial local commit existed before that output was inspected and was corrected before any push; application/tests/results were unchanged.

Historical Windows `cache_close` remains unresolved: [retained failure and follow-up](../2026-10-21-midnight/ci-followup/REPORT.md). The unchanged lifecycle suite ran once in the aggregate; this is not a repeated Linux diagnosis. Prior modal-focus failures, manual-pump stalls, obsolete cron assertion and blocked WebEngine tests remain in their reports. Current passes do not erase them or establish canonical source integration.

Not performed: installed Windows/Android, natural malformed-metadata incidence, live cache/weather/provider health or bookability, real browser/booking/holds, notification delivery, updater/assets/signatures, native accessibility/DPI/resume, clipboard use or performance benchmarking. Recovery probes use inert worker ownership. Host-local interpretation of naive timestamps and other freshness policy remain unchanged. No substantial redesign or product-direction choice is implemented.

All five workflows are unchanged. This repair branch matches ordinary desktop push and desktop/cache PR checks, not production main-specific pushes. No denied production-history/manifest/encoded-branch route or docs-only publication is retried. No merge, deployment, release, manual/production dispatch, credential/security change, purchase, external contact or live transaction occurs. Original dirty checkout and prior evidence remain preserved.
