# Independent review — 28 October 2026

No blocking finding in the focused application, test or test-workflow change against PR16 `62d1b1c569e3a47004ef85eb6de9133054f354d2`. Reviewed working-tree hashes and static-check evidence are retained in [review-metadata.json](review-metadata.json); they do not imply testing of an uncreated final commit.

## Application behavior

The old single-day status computed matching courses as `live_count - no_match_count`. Non-error calendar-only Wembley results enter `live_count`, while any `calendar_availability` value excludes them from `no_match_count`, even if they have no exact rows. Thus one matching course plus an available, full or unreleased calendar incorrectly reports two matching courses. With only a full/unreleased calendar, it incorrectly reports one matching course alongside zero times.

The repair counts non-direct results that retain filtered exact rows, matching the existing multi-day counting rule. It uses the same submitted context and `filtered_rows()` as the time total. Multiple rows from one course count once, and courses filtered down to zero rows do not count. The new count replaces both affected numeric status expressions; available-calendar-only wording retains precedence.

The application diff is six added and two removed lines. It changes no row filtering, card construction, calendar/provider handling, direct links, dates, cache/freshness behavior, workers or notification paths. Existing production result constructors give calendar-only/error/direct results empty exact-row lists. The focused repair does not introduce new schema validation or broaden into provider-error wording. The separate provider-error-summary observation remains outside this change.

The source duplicate audit covers all 18 non-cache/news refs: none has a row-derived single-day matching-course counter. PR16's absent-snapshot wording remains separate and unchanged.

## Regression and workflow review

The eight new test methods cover all three calendar-only states alongside matching rows; full/unreleased states with zero rows; available-calendar wording; inclusive player/time filtering; multiple times and show-all count stability; error/direct/empty-Collier exclusions; submitted context versus edited controls and unselected results; and single/multi-day parity. They compare counts with actual constructed tee-time cards, block socket/browser paths, stop startup timers and clean up Qt widgets before interpreter shutdown. No existing assertion or timeout was weakened.

The baseline metadata's eight failures include subtest assertions; they must not be described as eight failing methods without consulting the log. The reviewer inspected this evidence but did not rerun the application tests; root/author aggregate results remain separate evidence.

The only workflow edits add `test_result_counts.py` to the existing desktop push/PR path filters and isolated-process module list. Read-only permissions, offscreen Windows execution and timeouts remain unchanged. The repair branch matches `fix/desktop-*`; its application/workflow diff selects desktop push/PR tests and PR cache/integrity tests. Inspect every event/attempt at the final head, including the push run.

Production workflow files are byte-unchanged against PR16. News/cache push triggers require `main`; alerts are dispatch-only; the cache `workflow_run` listens to the preferred-date alert checker on `main`, not test workflows. The reviewed repair push/PR therefore does not select a production workflow.

Checksum-verified actionlint v1.7.12 passed all current workflows with exit 0 and an empty [log](actionlint.log). The official Linux archive SHA-256 matched `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` before extracting/executing only its `actionlint` member. CRLF-aware whitespace validation also passed.

## Limits

No new application regression run, live-provider request, native Windows/Android/device/UI interaction, screen-reader/DPI test, installed updater or notification-delivery test was performed by this reviewer. The historical Windows `cache_close` timeout remains unresolved; no Linux paired reproduction, timeout relaxation or causal attribution was attempted. Canonical desktop/mobile source reconciliation remains pending. No merge, deploy, release, production trigger, credential/security change, spending, third-party contact, booking or notification occurred.
