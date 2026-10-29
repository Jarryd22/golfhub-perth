# Independent review — 29 October 2026

No blocking finding in the focused provider-error presentation change against PR17 `d7da8b8b02f58b319a5db1178a49839ec2a009bd`. Reviewed working-tree hashes and static/layout evidence are in [review-metadata.json](review-metadata.json); root aggregate tests and final-head CI are separate evidence.

## Application and regression review

The change consumes existing error information after filtering to submitted selected courses. Direct booking links do not contribute availability-feed errors. When no exact rows or available calendar options exist, a provider error now produces an incomplete-availability summary/status; positive exact-time and available-calendar headlines keep precedence and receive an error warning. Multi-day warnings count dates with failed feeds, while day headings name the unavailable-course count. An absent snapshot remains PR16's distinct unchecked-date state and is excluded from failed-observation day counts.

Collier retains its existing official-calendar URL, button and handoff. Only its false empty metadata override is suppressed when a provider error exists; genuinely empty Collier results retain their existing notice. No provider requests, retry policy, row filtering, matched-course calculation, dates, cache/freshness behavior, worker lifecycle, booking logic or notifications are changed.

The new regression file covers all-failed and mixed empty/filtered/exact/calendar results, multi-day error counts and lazy date context, missing snapshots, saved fallback, unselected/direct-link errors, and Collier error versus genuine-empty metadata/handoff. Socket paths are blocked, browser handoff is mocked, startup timers are stopped and Qt widgets are explicitly destroyed. No old timeout or assertion is weakened. The reviewer inspected test source without duplicating the aggregate run.

All 19 non-cache/news source refs were inspected separately: no existing provider-error summary or Collier-error metadata repair was found. Existing weather/Wembley reliability, missing-snapshot and matched-course-count drafts remain distinct.

## Screenshot/layout finding

The initial `after/multiday-all-error.png` compresses the first expanded card before Qt finishes updating the scroll area's content size. A bounded, socket-blocked [instrumented probe](layout-review-probe.py), using the same application and fixtures, records three event passes without changing app code. Its [geometry evidence](layout-review/probe.json) shows title height **5 → 23 px**, metadata **5 → 15 px**, body height **423 → 496 px** and scrollbar maximum **0 → 73** between passes one and two. Pass three is stable. The [settled multi-day image](layout-review/multiday-all-error.png) shows the full card and scrolling; the initial after image was preserved.

This supports transient layout settlement rather than a persistent clipping regression. The single-day source badge and warning are already non-overlapping at pass one: badge y43–74 and warning y81–116 relative to the results body. No layout rewrite is justified by these observations. Settle geometry before screenshot capture and validate compact-view scroll reachability separately. These are Linux offscreen source widgets, not native device/UI validation.

## Workflow/static review

Only `test_provider_error_states.py` is added to existing desktop push/PR path filters and the isolated-process module list. Read-only permissions, runner choice and timeouts are unchanged. Production workflow files are byte-identical to PR17. News/cache push triggers require `main`; alerts are dispatch-only; cache `workflow_run` listens to the alert checker on `main`, not test workflows. This repair branch push/PR selects test workflows only. Verify all events/attempts on the final head, including Windows push.

Checksum-verified actionlint v1.7.12 passed all current workflows with exit 0 and an empty [log](actionlint.log). The official Linux archive matched SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` before executing its `actionlint` member. CRLF-aware whitespace validation passed.

## Limits

No aggregate application suite rerun, live-provider request, native Windows/Android test, screen reader/DPI test, installed updater or notification delivery was performed by this reviewer. The historical Windows `cache_close` timeout remains unresolved; no repeated Linux diagnosis or timeout relaxation was attempted. Canonical desktop/mobile source reconciliation remains pending. No merge, deploy, release, production workflow trigger, credentials/security change, spending, third-party contact, booking or real notification occurred.
