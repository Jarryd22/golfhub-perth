# Cache-age metadata regressions — November 21

Five methods were added in a separate `CacheAgeMetadataTests` class in CI-selected `tests/test_startup_cache.py`. The original 15 methods, both original classes and module cleanup remain AST-identical to exact PR33. The test author did not edit runtime, workflows or other test modules.

The new coverage checks JSON non-string scalar/container timestamps, including previously working falsy values; aware ISO/Z/offset timestamps and existing invalid-string/future-age behavior under a fixed clock; actual saved JSON retaining rows and requesting exactly one 100ms shared refresh; a mocked HTTP download retaining shared classification, rows and saved bytes; and mixed valid/bad/absent metadata with one genuinely absent snapshot. The latter preserves three loaded dates out of four, lazy rows, original submitted range/player/round/time context, exact per-day URLs and rows, and accessible booking dates. A naive ISO control retains existing host-local interpretation without introducing timezone policy.

## Final identical-file results

- **Baseline exact PR33:** 20 methods run, **16 passed / four errored methods**, represented by **11 AttributeError records**, zero assertion failures/skips. All 15 original methods pass. Five non-string formatter subcases and four saved-startup subcases error, plus one single-day shared method and one mixed-date method.
- **Repair:** **20/20 passed**, zero failures/errors/skips.
- The five new methods contain 26 recorded subscenarios: baseline 17 pass/nine error, repair 26 pass. The other two baseline errors are whole methods. Subscenarios are not extra unittest methods; the naive control and other assertions are not separately inflated into counts.
- Final test SHA256: `80c7676bb983b558adcbc092c8edea7530e3b4be9862c68403d33a6b692e63cc`.
- Baseline shared-cache SHA256: `9a42d4156486c7000a61492d9041e11c1a68c5c84b3634037f6f600a2f90459f`; candidate: `ca42e9054d611e8368556328266479b320baf96217c8a69d5997a198a448885d`.
- Qt source is unchanged at `bbf50a775cfbfbe8e126fac8b0fd958545d7455567fc76d72e9aac5ff0cc7403` on both roots.

The external runner uses explicit source roots and the same final test file. Baseline source root is `/workspace/golfhub-20261120` at PR33 `4fe841359f1d0b3e4a261649c286f04d0bfbac54`; candidate root is `/workspace/golfhub-20261121` at that starting HEAD plus the recorded shared-cache edit. Each subprocess has a 60-second external bound; baseline exits 1 for expected errors, final repair exits 0. Full stdout/stderr and JSON remain in `baseline/` and `repaired/`; exact command template, hashes and history are in `provenance.json`.

## Preserved review-stage outcomes

The initial baseline file (`28676d96…`) produced the same 16-pass/four-errored result. Before any candidate execution, review noticed that lazy result construction binds the BOOK handler during expansion: patching it afterward would miss interception. That initial file/result/log remain under `pre-review-lazy-handler/`. The patch was moved before expansion/click, and message-box methods were blocked with explicit no-dialog assertions. No modal or booking operation occurred with the earlier fixture.

The next file (`8b0b733b…`) produced the same expected baseline, then **19 passed / one assertion failed** on the candidate. Its mixed-date assertion incorrectly expected each section date in `context['date']`. Existing behavior retains the submitted range context, whose date is the first selected date; each result URL and accessible name carry the individual date. The final oracle checks the complete original range context plus the exact per-day result URL and row. This corrects a fixture expectation and strengthens the actual contract; no app/date behavior or guard was changed. Both results/file and compressed review diffs are retained under `pre-review-range-context/` and `pre-review-lazy-handler/`.

The final file was rerun against both sources. Earlier outcomes are not overwritten or counted as additional unique methods. Existing Qt/offscreen warnings remain in raw logs.

## Safety and limits

Tests use isolated real JSON files, mocked HTTP bytes, intercepted refresh scheduling and BOOK handlers. Sockets/DNS, native worker construction, providers/weather, browser launches, booking dialogs and UI persistence are blocked. Shared-cache serialization is exercised only inside the isolated cache; bytes are compared before and after rendering. New UI tests invoke controller methods directly; the separate root-owned probe supplies actual 0ms Qt-timer evidence. No actual provider, browser, booking hold, notification, Windows/Android device or production corruption incidence is tested. Historical Windows `cache_close` and canonical integration remain unresolved. No denied route or remote action was attempted by this agent.

## Raw-log whitespace preservation

The full staged whitespace check found a trailing progress-line space in three baseline logs. Their original bytes are preserved in adjacent `test.raw.log.gz` archives; the readable `test.log` copies remove trailing horizontal whitespace only. `whitespace-normalization.json` records original, normalized and archive hashes. Results, test/source bytes, assertions and counts are unchanged. The check failure and unpublished local-commit correction are retained; no rerun was needed.
