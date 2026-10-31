# Independent review — 31 October 2026

No blocking findings in the reviewed change. Base is exact PR19 `ba1faeae0dc9cf3314e8dc884f79b13e2520d22c`; [review-metadata.json](review-metadata.json) records reviewed hashes, method comparisons and static checks.

## Behavior and scope

Single-day result cards now receive a booking callback bound to a copy of their displayed search context. Multi-day sections capture that context when their headings are rendered, then use it for both deferred row filtering and the resulting booking callbacks. Thus a later live search can update the active `self.context` while retained results continue to use the player/time filters under which their headings and rows were displayed. Existing per-day date capture remains intact.

The copies are shallow, which is sufficient for the scalar `players`, `from` and `to` values consumed here. Neither helper mutates the supplied context or temporarily replaces active search state. `context is None` preserves legacy direct-call behavior while allowing an explicitly supplied empty dictionary. All ResultCard creation paths, including the special empty-course path, use the captured callback. Show-all rows inherit the same callback.

Only five app method ASTs change: `open_tee_time`, `filtered_rows`, `_populate_day_section`, `render_multi_results` and `render_results`, plus the `partial` import. Search submission, cache completion, live success/failure/cancellation, save paths, worker/thread lifecycle and close handling remain unchanged. Successful replacement still renders and saves under the active new search; this repair does not restore old context into those paths. Existing stale/subset-cache behavior is outside the change and remains a separate backlog item. `shared_cache.py` and `booking_assist.py` are byte-identical to PR19.

## Evidence and tests inspected

The baseline [booking probe](before/booking-context-probe.json) records an old one-player result handing off four players after a later live search starts, fails or is cancelled. Its original date/URL and visible label remain unchanged. The baseline [lazy probe](before/lazy-context-probe.json) records a retained day heading claiming one match while later expansion applies the new player/time filters and renders no tee-time card. These are inspected synthetic Linux offscreen observations, not fresh reviewer executions or native-device tests.

Reviewed ten new regression methods covering booking during pending/failed/cancelled refreshes, Any-to-explicit and explicit-to-Any player changes, deferred and already-built multi-day cards, successful replacement/save context, unsubmitted controls and legacy direct calls. Actual button handlers and pure booking-plan construction are exercised by the tests; browser, dialogs, sockets and worker/thread execution are intercepted. Fake worker lifecycle is not evidence for native thread cleanup.

The existing booking-context keyboard assertion now additionally requires the original submitted context argument. Its result/row, focus, accessible-name and no-browser assertions remain. No existing timeout or lifecycle assertion is weakened. Parent owns baseline/final execution, aggregate counts and exact-head CI; this reviewer did not repeat the aggregate.

The source audit found no duplicate protection across all 21 source branch heads or the preserved loose checkout. Earlier PR12 date/accessibility, PR13 lifecycle and PR14 idle-midnight fixes address different behavior.

## Workflow and static checks

The desktop workflow adds the new module to both event path filters and its explicit Windows module list. The filename does not match the dependency-free cache job's `test_cache*.py` discovery. Existing runner, permissions, timeout and test execution policy remain unchanged.

All three production workflows and `test-cache.yml` are byte-identical to PR19. Cache/news pushes remain restricted to main, alerts remain dispatch-only, and cache completion listens to the preferred-date alert checker rather than test CI. No workflow was dispatched during review.

Official actionlint 1.7.12 archive SHA-256 was verified before extraction/execution: `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`. All workflows pass with exit 0 and no findings in [actionlint.log](actionlint.log). CRLF-aware `git diff --check` also passes.

No native Windows/Android, live provider/booking/hold, notification delivery, runtime ZIP or production testing was performed. Historical Windows `cache_close` and canonical-source reconciliation remain unresolved. No denied, pending or uncertain operation blocked this review.
