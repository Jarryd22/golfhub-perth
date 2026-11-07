# Independent source review — 7 November 2026, Perth

No blocking finding remains in the corrected responsive-grid change against exact PR26 `2fa359011391f5307aeb60c0f18ba9370190d77f`. Reviewed file hashes and source comparisons are recorded in `review-metadata.json`. This review does not certify later edits or remote CI.

The final two-line change assigns stretch 1 to every currently active column and 0 to retained columns outside that active range. The loop covers the larger of the calculated active count and QGridLayout's retained column count. This removes layout-history-dependent blank space after narrowing while preserving the existing allocation when a wide grid contains only one or two cards. Widget ordering, visibility limits, placement formula, spacing and column thresholds are unchanged. Empty grids and a maximum of one column remain supported.

## Review finding caught before publication

The initial candidate iterated only `self.grid.columnCount()`. When a sparse grid had never populated all calculated active columns, it omitted their existing stretch policy. At 1200 pixels with a three-column maximum, exact PR26 gave one card width **400**; the initial candidate gave **1200**. Two cards changed from **397/396** to **595/595**. This was an unintended change beyond removing obsolete column weights, despite the initial six regressions and 310-test aggregate passing.

The correction uses `max(columns, self.grid.columnCount())` and adds sparse-grid and hide/narrow/restore regressions. The original candidate, original six-test results and the review geometry evidence remain retained under `pre-review`. Running the final eight-method test file on that initial candidate produces **two failing methods / three assertion records**. The same final file on exact PR26 gives **three passing and five failing methods / ten assertion records**; corrected source gives **8/8 passing**, zero errors/skips. These unit results were inspected from the parent's logs, not rerun by this reviewer. No assertion was relaxed to accept the regression.

## Independent verification and scope

This reviewer ran the same bounded offscreen geometry probe on exact PR26, the initial candidate and the corrected source: **48 states per source**, covering card counts 0/1/2/3, maximum columns 1/2/3 and successive widths 500/1200/683/500. The final probe exited successfully. Post-checks confirm that maximum-one-column geometry is unchanged, all wide sparse/full card widths match PR26, narrow card rows fill 500 pixels and zero-card grids remain empty. These are geometry observations, not additional unit-test methods or lifecycle tests. The probe uses QWidget cards; the parent/other agent owns configured-card visual and intercepted-booking evidence.

Only `ResponsiveCardGrid._relayout` differs at the function-AST level; 107 function ASTs remain unchanged. Provider/core/cache code, course configuration, the lifecycle module, alert archive/manifest and other workflows are byte-identical to PR26. The test-only desktop workflow adds the new module to both path filters and its existing isolated-process list. Existing timeouts and safeguards remain unchanged. No applicable ancestor/checkout AGENTS.md or .agents/skills directory was found.

The duplicate audit records the same original grid implementation across 28 immutable source refs and the preserved loose checkout; no competing fix was found. This reviewer inspected that evidence rather than repeating remote audit or the hourly watch.

The supported benefit is modest, predictable use of available card width after resizing. Baseline BOOK and Show all actions were already functional according to the configured probe; this is not a restored-booking claim. No new performance, golfer-preference, native accessibility, DPI or installed-client claim is supported. Historical Windows `cache_close`, canonical-source/release-candidate integration, native Windows/Android and actual notification delivery remain unresolved or unperformed. No lifecycle repetition, provider call, booking/hold, production-history retry, remote mutation or external action occurred in this review.

The parent remains responsible for final aggregate results, pushed head and every exact-head CI event/attempt, including failures/cancellations. No outstanding review blocker remains for the recorded corrected hashes.
