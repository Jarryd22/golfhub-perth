# Independent review — 1 November 2026

No blocking findings in the final runtime, test or desktop-workflow diff against exact PR #20 (`63c910556c4f4dc210e41c3e6db665845436a8f0`). [Reviewed file hashes](review-metadata.json) identify the working-tree code; this review does not imply that an uncreated final commit was tested.

## Correctness and scope

The defect lies in exception serialization before the already-repaired error renderer: `str(TimeoutError())` is empty, so result consumers treat the failed provider observation as a falsey/no-error value. It can disappear as a checked-empty result, count as fresh success at the shard health gate, bypass prior-good fallback, or count a failed delayed retry as recovered.

The shared `exception_message()` preserves every nonblank message exactly, including leading/trailing whitespace and newlines. Empty or whitespace-only messages become the exception class name. It is used at all six reviewed exception-to-result boundaries: Wembley calendar, page-error aggregation, final core processing, live-worker escape, delayed-shard retry, and shard future completion. Normalizing page errors before aggregation preserves the original exception type instead of reducing a message-less error to a generic outer `RuntimeError`.

Successful empty responses remain `error=None`. A later successful page still supplies rows after an earlier page failure; existing Wembley calendar fallback behavior remains unchanged. The result schema, exception classes caught, request construction, provider/browser policy, weather handling, timeouts, concurrency, health threshold and stale-data rules are unchanged. The helper has no new dependency or import cycle.

Class-name fallback does not broaden the transport retry allowlist. A blank `TimeoutError()` becomes an honest failure but does not newly qualify for the message-based delayed retry path. Existing nonblank transport messages retain their exact classification and retry budgets. No retry/test timeout or assertion was relaxed.

This is a producer-side repair for newly generated results. Historical saved or published `error=""` values cannot be reliably distinguished from prior false-success data by this change; no migration/backfill or current production incident claim is made. Canonical-source integration and release remain separate work.

## Regression review

The nine producer-to-widget methods exercise ordinary/Wembley empty and whitespace exceptions, exact nonblank diagnostic preservation, checked-empty success, mixed page outcomes, single/multi-date error rendering, intercepted official handoff and the actual ScanWorker escape catch. Worker fixtures execute the normal synchronous run with mocked fetch calls; they do not establish native QThread or live-provider behavior.

The eleven standard-library cache/core methods cover blank/whitespace errors, mixed page diagnostics, Wembley and outer processing, preserved successful-empty/named results, failed delayed retry counts, the fresh-majority gate, unknown publication, stale prior-good reuse and direct-constructor publication rejection. Main-shard fixtures use completed local futures, temporary output and mocked fetch/config/weather; they do not contact providers or exercise native provider threads.

The inspected UI baseline record has four passing/five failing methods with ten failed assertion/subtest records; repaired UI source passes all nine. The cache-agent baseline evidence reports two passing/nine failing methods with twelve failed assertion records and no errors. The reviewer did not duplicate these executions; the root aggregate owns final after-run counts and exact-head CI verification.

## Workflow and static checks

Only `test-desktop.yml` changes, adding `test_provider_exceptions.py` to both path filters and the isolated-process module list. Its permissions remain read-only. The new `test_cache_provider_exceptions.py` matches the unchanged cache discovery pattern. Application/script changes select the test workflows on a PR; a `fix/desktop-*` branch also selects desktop push tests.

Production cache/news push triggers remain limited to `main`, and alerts remain dispatch-only. Cache `workflow_run` listens to the alert checker on `main`, not these test workflows. All three production workflow files and `test-cache.yml` are byte-unchanged from the base. The authorized repair push/PR therefore does not select a production workflow. No dispatch, manual CI rerun, merge or deployment occurred in this review.

CRLF-aware `git diff --check` passed. Source-file line endings were retained; the tracked diff is narrowly limited to the helper, six replacements, two imports and three desktop-test workflow entries. Actionlint and aggregate execution are owned by the root and are not claimed as reviewer-run checks.

## Visual review and limits

Current before/after 1280×800 offscreen Araluen captures were inspected: the empty timeout changes from “0 matching times” with no course card to “Availability incomplete” with a course warning and usable official-booking action. The 980×640 capture shows the prior missing-date message remains wrapped and reachable during a 9-hole/custom-range search. These are synthetic Linux source-widget captures, not native Windows/Android validation; existing date punctuation remains separate backlog work.

The current cumulative checklist/backlog and historical Windows timeout context were reviewed. The Windows `cache_close` failure remains unresolved; no Linux reproduction, test relaxation or inference of resolution was performed. Source reconciliation, per-course freshness, installed updater, native devices, screen readers/DPI, live booking and notification delivery remain pending. No application, test, production workflow, credential or security setting was edited by the reviewer; only review evidence was written.
