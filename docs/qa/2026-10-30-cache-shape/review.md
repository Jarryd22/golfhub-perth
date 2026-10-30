# Independent review — 30 October 2026

No blocking findings remain in the reviewed change. Base is exact PR18 `eb6697c76a38e4e5c2117ed4444ef1f61cc619d3`; reviewed file hashes and check details are in [review-metadata.json](review-metadata.json).

## Scope and behavior

The eight added lines in `validate_snapshot` reject non-object course records, non-list non-null `decorated_rows`, and non-object members of those row lists. Rejection applies to the complete payload. Nothing silently drops an invalid course or tee time and then presents the remaining subset as complete. `fetch_shared_snapshot` validates before saving, so its existing exception path returns no downloaded snapshot and leaves the previous local file intact. `load_local_snapshot` likewise returns no snapshot for malformed data, allowing the existing startup recovery scheduling to continue. The unchanged previous-shard loader also uses this validator and catches the same exception.

Missing and null `decorated_rows` remain valid. The unchanged UI passes them through `filtered_rows`, which treats absent/null rows as empty. Empty results, checked-empty courses, provider errors, direct links, calendar status and custom row/stale fields are preserved. The validator does not mutate accepted data. This remains container-shape validation, not complete field-value/schema validation or a freshness/authenticity guarantee.

`app/qt_golfhub_app.py` is byte-identical to PR18. No provider, retry, worker-lifecycle, booking, alert, updater or production workflow implementation changed. The existing Windows `cache_close` timeout and canonical-source questions remain unresolved.

## Evidence and coverage inspected

The parent’s [before probe](before/probe.json) records four structural failures: null/string course records, a null row, and object-shaped rows. Each caused a startup `AttributeError` before recovery scheduling, and a mocked shared response overwrote the valid saved bytes. The [after probe](after/probe.json) records rejection of all four, no startup exception, the existing 100 ms recovery scheduling, and byte-for-byte preservation of the valid saved file. These are inspected Linux offscreen/mocked evidence, not a reviewer rerun or native-device result.

Reviewed 10 pure snapshot regression methods and 5 Qt startup/fallback methods. They cover mixed valid/invalid records, empty invalid containers, preserved complete payloads, the unchanged outer-envelope checks, local-file preservation, no file creation for invalid downloads, real isolated cache round trips, previous-shard compatibility/stale metadata, valid saved rendering, startup recovery scheduling and saved fallback without a live worker. Sockets/browser actions and worker construction are blocked or intercepted. Parent owns the baseline/final runs and aggregate counts; the reviewer did not duplicate them.

The source audit found the same outer-only validator on all 20 current non-data source branch heads and the preserved loose checkout. No existing branch/draft duplicates this inner-result/row-shape repair. Main, drafts, update repositories and instruction checks are recorded in the dated context audit; per-course freshness/subset preservation and PR15 runtime archive validation are separate work.

## Workflow review

An initial review finding was resolved before final review: naming the Qt module `test_cached_startup.py` would also match the dependency-free cache job’s `test_cache*.py` discovery. The final `test_startup_cache.py` name avoids that pattern and is included in both desktop event filters and the explicit Windows module list. The pure `test_cache_snapshot_shape.py` remains selected by cache discovery. No Qt dependency or production workflow change was needed.

The three production workflows (`refresh-cache-10min.yml`, `course-news.yml`, `check-alerts.yml`) are byte-identical to PR18. Cache/news push triggers remain restricted to main; alerts remain dispatch-only; the cache completion trigger listens to the preferred-date alert checker, not test workflows. No workflow was dispatched by this review. Read-only test permissions and existing timeouts are unchanged.

Official actionlint 1.7.12 was downloaded and its archive SHA-256 verified before extraction/execution: `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`. All workflows pass, exit 0, with no findings in [actionlint.log](actionlint.log). Whitespace validation with the repository’s existing CRLF allowance also passes.

## Limits

No native Windows/Android, installed update, live provider/booking/hold, notification delivery, runtime ZIP execution or production testing was performed. Final remote head and all exact-head CI events/attempts remain the parent’s completion checks. No access denial or unresolved action blocker occurred during this review.
