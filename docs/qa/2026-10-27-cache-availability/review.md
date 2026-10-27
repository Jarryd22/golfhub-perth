# Independent review — 27 October 2026

No blocking finding in the focused application, regression-test or test-workflow diff against PR #15 (`4ce2be23255edc9d7579d8529ef2f7e366c304ca`). Reviewed working-tree file hashes are recorded in [review-metadata.json](review-metadata.json); this is not a claim that tests ran against an uncreated final commit.

## Source findings

- The defect is a presentation contradiction: `render_snapshot_batch()` already marks a missing snapshot `available=False`, but the baseline day title/body and aggregate match summary treat it as a searched empty date. The repair consumes that existing metadata without changing fetch, save, freshness, provider or worker logic.
- For the production call path, an unavailable date contains only locally constructed direct-booking links, never tee-time rows. The new early return in `_populate_day_section()` therefore replaces the false empty message without discarding fetched times. Direct links remain collected once in the range-level link section.
- Each lazy builder captures its own availability and date through default arguments. Editing pending controls does not change the captured missing-date status. Existing direct callers omitting `available` retain the prior loaded behavior.
- Loaded empty results, provider-error cards, unreleased/available calendar cards and saved-device fallback retain their distinct existing behavior. Match counts still use the submitted player/time filters. Partial summary and status now scope counts to loaded days; fully loaded views retain their wording.
- The new test module exercises missing headings, lazy expansion and compact wrapping, partial filtered counts, genuine empty results, local fallback, all-missing recovery, provider/calendar states, direct-link interception and compatibility with callers lacking coverage metadata. It blocks sockets and intercepts browser calls, stops startup timers and destroys widgets before interpreter shutdown. No timeout or old assertion was relaxed.

## Workflow review and static validation

The only workflow edits add `test_multiday_cache_states.py` to the desktop push/PR path filters and isolated-process module list. The desktop workflow retains read-only permissions and Windows offscreen execution. The repair branch matches `fix/desktop-*`, so pushing application changes should schedule desktop test CI. Its PR also matches cache-CI application/workflow paths, so cache/integrity tests and actionlint should run. Inspect all events and attempts on the exact remote head; do not infer all-CI success from a PR-only helper.

Production cache/news push triggers are restricted to `main`; the alert checker is dispatch-only. Cache `workflow_run` listens only to the preferred-date alert checker on `main`, not the test workflows. Therefore the reviewed repair push/PR does not select a production workflow. No workflow was dispatched or rerun during review.

Official actionlint v1.7.12 Linux archive SHA-256 matched `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` before extraction/execution. All current workflow files passed `actionlint -no-color` with exit 0 and an empty [log](actionlint.log).

## Evidence limits

The reviewer inspected the recovered October 22 1280×800 offscreen before/after images: the missing day changes from a no-match claim to an unchecked-availability explanation, and the headline scopes zero results to two loaded days. These are historical source-widget screenshots, not new October 27 or native-device evidence. The current root-run regression records were inspected: exact PR #15 baseline has 7 failures / 3 passes; repaired working tree has 10 passes, with source/test hashes retained. The reviewer did not rerun these tests.

No repository AGENTS.md or .agents/skills instructions were found in the reviewed checkout. Cumulative checklist/backlog and the October 21 CI follow-up were read. Historical Windows `cache_close` timeout remains unresolved; this review did not repeat its Linux investigation or infer resolution from current tests. Canonical desktop/mobile reconciliation, installed Windows/Android, screen-reader/DPI, live booking, update installation and notification delivery remain outside this review. No application/test code, production workflow, credentials or release was changed by the reviewer.
