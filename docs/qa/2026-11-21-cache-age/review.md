# Independent review — cache age metadata, 21 November 2026

**Verdict: no blocking source, regression or evidence findings.** The one-line guard addresses the reproduced startup interruption while retaining usable rows and existing unknown-age wording. Final saved records support the reported focused and aggregate passes. This review performed source/AST, hash, workflow and evidence inspection; it did not rerun tests, execute the app or perform remote mutations.

Reviewed against exact PR33 `4fe841359f1d0b3e4a261649c286f04d0bfbac54` in `/workspace/golfhub-20261121`:

| File | SHA256 |
|---|---|
| `app/shared_cache.py` | `ca42e9054d611e8368556328266479b320baf96217c8a69d5997a198a448885d` |
| `tests/test_startup_cache.py` | `80c7676bb983b558adcbc092c8edea7530e3b4be9862c68403d33a6b692e63cc` |
| Unchanged `app/qt_golfhub_app.py` | `bbf50a775cfbfbe8e126fac8b0fd958545d7455567fc76d72e9aac5ff0cc7403` |

## Source and regression assessment

Restoring only the original first `cache_age_label` condition makes the entire shared-cache module AST identical to PR33. Unsupported non-string values now return the existing `saved earlier` label before `.replace` is called. Existing string parsing, empty-string behavior, invalid-string fallback, future-age clamp and naive timestamp interpretation remain unchanged. Snapshot validation, persistence, refresh scheduling, providers and Qt code are untouched. The guard does not reject good rows, rewrite metadata or certify freshness.

The [duplicate audit](duplicate-audit.json) inspected 36 current non-data refs and 25 known preserved local files: all 61 formatter copies shared the unguarded AST. PR19's result/row validation and the separate production-index timestamp parser do not protect this path. No competing repair was found within that bounded coverage.

Static comparison independently confirms both original startup-test classes and the module cleanup helper are AST-identical, preserving all 15 original methods. Five new methods cover unsupported JSON values, valid/invalid aware and naive string controls, actual isolated saved files, an intercepted shared download, and mixed-date lazy rendering. The final test file in the evidence directory is byte-identical to the reviewed file. Network/provider/browser/worker/booking paths are blocked or intercepted; shared-cache writes are confined to temporary test storage.

The corrected lazy BOOK fixture patches the handler before expansion binds it. Its final oracle checks the complete original submitted range, exact per-day result URL and row, and accessible date. This agrees with unchanged retained-context behavior; changing `context['date']` for each section would have changed the product contract. Message-box interception and no-dialog assertions also protect the fixture. No existing assertion or timeout was relaxed.

## Saved result reconciliation

The reviewer checked JSON, raw log summaries and hashes, rather than attributing other agents' executions to this review:

- **Frozen-file baseline:** 20 methods, 16 passed and four errored methods, with 11 `AttributeError` records, zero assertion failures/skips. Its 26 recorded subscenarios contain 17 passes/nine errors; the remaining two errors are whole-method errors.
- **Frozen-file repair:** 20/20 methods and 26/26 recorded subscenarios pass, zero failures/errors/skips. The final test/source hashes agree across provenance, results and current files.
- **Final aggregate:** each of 28 logs has exactly one `QA_RESULT` record matching its summary entry; every recorded subprocess exit is zero. Totals are **366 passed, zero failures/errors/skips**. Comparing module names with the unchanged desktop workflow confirms **234 desktop-selected + 95 cache/integrity + 37 additional**. The summary's Git status records the uncommitted candidate, with separate exact source hashes; it is not a pushed-head CI claim.
- **Startup probe:** actual saved JSON and delivery of the owned initial zero-ms timer produce three of seven passing recovery cases before and seven of seven afterward. All 14 before/after executions preserve saved bytes. Four truthy non-string values previously raised callback errors and prevented the refresh request. The later `start(100)` is intercepted; no shared worker execution is implied. The fixture named `absent` contains explicit null, as correctly disclosed; missing-key behavior is covered separately in the final mixed-date regression.
- **Recovery journey:** an additional read-only evidence review confirms 43 unique assertions, all true, matching 43 script checks, stable source hashes and no recorded exception/callback errors. This is one controlled journey with normal timestamps, three inert thread owners, two intercepted BOOK callbacks and zero UI persistence calls. Its launcher exit field is not retained; completed JSON does not establish exit code zero. The report and [scope](recovery-journey/scope.md) preserve that limit.

All 17 artifact hashes in regression provenance and all nine in startup-probe provenance match the copied files. Recovery script/result/scope hashes also match its copy verification. [REPORT.md](REPORT.md), the cumulative checklist and backlog agree with the reviewed counts, source scope and execution limits. At review time their only outstanding generated artifact was the planned `evidence.json` manifest; this review completes the previously pending `review.md` link. Final publication, remote-head and exact-head CI verification remain the parent's subsequent work.

## Retained history and workflow scope

Earlier files and logs remain separate: the first baseline had the same 11 errors; the handler-interception correction preceded any repaired execution; the intermediate repaired test ran 19 pass/one assertion failure because its new oracle incorrectly expected per-day `context['date']`. The retained traceback identifies that mismatch. The final test was rerun against both exact baseline and candidate, rather than reusing the older baseline. These outcomes are not additional unique-test counts.

All five workflow files are byte-identical to PR33, with hashes matching the repository audit. The existing startup module is already selected by desktop CI. Normal `fix/desktop-*` pushes select desktop checks, and pull requests select desktop/cache checks; the repair does not change main-only production push conditions or dispatch behavior. Root's compilation/actionlint/whitespace result is recorded in [final-validation.json](final-validation.json); those commands were not independently rerun by this reviewer.

Installed Windows/Android, native focus/accessibility/lifecycle, natural malformed-metadata incidence, live provider/bookability, browser/booking/holds, alert delivery, updater assets/signatures and freshness policy remain unverified. Historical Windows `cache_close`, earlier modal-focus failures and canonical source integration remain unresolved. No prohibited history, manifest, directory or encoded-branch route was retried, and no documentation-only PR or other remote write was attempted during this review.

## Publication-preflight evidence correction

The subsequent full staged whitespace check found one trailing space in each of three raw unittest progress lines. Root recorded the failed check and initial local, unpublished commit `bc180d6c16ee81ca0812833c509ce9892a3badf2` in [whitespace-normalization.json](regressions/whitespace-normalization.json). The reviewer independently decompressed all three adjacent `test.raw.log.gz` archives: each reproduces its recorded original SHA256, and each archive/readable-copy hash matches the normalization record. Each readable log differs from its original by exactly one trailing space; line counts and all other bytes are preserved. There is no semantic log difference.

All 21 updated regression-provenance artifact hashes match. The five retained regression result JSON files are byte-identical to the initial local commit, and the reviewed application/Qt/test hashes above are unchanged. REPORT.md and final-validation.json disclose the failed check and correction. The parent will regenerate the manifest, repeat the complete patch check and amend its unpublished commit before pushing. No test rerun or remote action was performed for this verification; the review verdict is unchanged.
