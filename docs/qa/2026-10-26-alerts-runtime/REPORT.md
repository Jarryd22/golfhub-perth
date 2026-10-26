# Offline alert-runtime provenance — 26 October 2026

## Source and duplicate-work audit

This isolated repair follows unchanged PR #14, `55579cb135f360b114f7705516d3b21bbd8e1632`, to retain the cumulative QA record. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`. All open drafts #3–14, current remote branches and accessible task history were inspected; no competing integrity helper was found. The existing desktop and reliability fixes are not duplicated or represented as deployed. This helper has no runtime dependency on the desktop fixes, but the draft is stacked on #14 for a small cumulative diff.

The October 22 cloud task `01a16101-d07e-738a-984f-62039316201d` stopped with a usage-limit error. Its retrieved history reveals partial missing-date-cache wording changes, probes and a test-workflow edit in `/workspace/golfhub-perth`, plus `/tmp/golfhub-20261022-base`. No final report/PR was produced. Those cloud filesystem contents are not accessible through this desktop filesystem and were not recovered or modified. A bounded search found no corresponding local partial work; today's focus is separate.

The original checkout remains at `34502074736251dd5ad63cbccd69eeca600ffdff`, with 24 modified tracked files, 666 untracked, no staged changes/deletions, desktop 5.1.17 and mobile 0.1.23+24. These are current readings, not October 18's inventory. Its AGENTS release policy was read; no project `.agents/skills` was found. The final comparison against today's initial inventory preserves all 269 recorded source hashes and file counts. No reset, clean or original-source edit occurred.

## Data-only archive result

The current workflow directly extracts `.github/alerts-runtime.zip`, installs its requirements, then invokes the bundled worker. It does **not** read `.github/alerts-runtime-manifest.json`. The workflow, ZIP and manifest are identical to main and remain unchanged by this repair. Their most recent runtime update is commit `e747178f34e150cf6255e9cc865266486551289a` (28 September).

Freshly reading the manifest and ZIP as data established:

- Expected and actual archive SHA-256 both equal `63d7b944607ff8ce29f293adb64d647cbb6636f227da63971c0c1a181cfdaf30`.
- All **16 expected file members** match their freshly read SHA-256 values. No unsafe paths, duplicate members, extras, omissions or member mismatches were found.
- The manifest's Git-blob SHA-256 is `1e91d57d248b0f5b89ecb471cd5cd198b0d2a92cb620eb83b720362e83717f36`. The checked Windows file is `07f360271f9f90969e07668c32f1f50c81a6c0dd02374ddee7b10c5ea9f99c50`; checkout newline conversion changes its bytes but not its parsed keys/hashes.
- Compared with loose **Git blob bytes**, ten runtime members have no loose counterpart, and `app/golfhub_core.py` plus `data/courses.json` differ. The four other loose files match. Checkout newline differences are excluded from this comparison. Loose-source tests therefore do not establish the bundled worker's behavior. [Provenance comparison](source-provenance.json).

[Initial independent hash inventory](initial-integrity-audit.json) · [Final validator output](validator-current.json). No archive member was extracted, imported or executed. No current integrity mismatch was found; these findings make no allegation of compromise.

## Focused improvement and before/after evidence

Added `scripts/validate_alerts_runtime.py`, a standard-library-only offline checker. It reads a bounded manifest and a single bounded archive byte snapshot, validates the archive digest, exact member set and each member's digest, and returns JSON plus a nonzero exit on failure. It rejects duplicate manifest keys/members, traversal/absolute/backslash/drive paths, Windows reserved names and case/prefix aliases, directories/symlinks/nonregular entries, encrypted/unsupported compression and malformed data.

Inputs are limited to 16 MiB archive / 1 MiB manifest, 512 accepted members, 8 MiB per member and 32 MiB total uncompressed content. ZIP metadata is parsed before the member-count check; the 512 limit is not a pre-allocation cap. Portable ASCII file paths and stored/deflated compression are deliberate accepted formats. The current bundle fits this policy.

**Before:** a synthetic ZIP containing changed, inert bytes passes ordinary ZIP CRC validation, which does not compare the committed manifest. **After:** the helper rejects that same intact ZIP with both archive and member hash mismatches. [Byte-only demonstration](before-after.json). This is a synthetic regression, not a changed production bundle.

```text
python scripts/validate_alerts_runtime.py --archive .github/alerts-runtime.zip --manifest .github/alerts-runtime-manifest.json
python -m unittest discover -s tests -p test_cache_alerts_runtime_integrity.py -v
```

This is **offline QA tooling**, not a new production execution gate. No workflow/settings/credentials changed. The caller must choose a manifest from the intended reviewed revision: matching editable hashes are not an independent signature, source review, notification-delivery proof or authorization to execute the bundle. Current workflow path filters also do not trigger cache tests for ZIP/manifest-only changes. Production integration or trigger changes remain outside this authorization.

## Validation and retained limitations

- **27/27 integrity tests pass** on Windows/Python 3.12.14, with workspace-scoped TEMP/TMP and sockets/extraction mocked. Includes current bundle validation with fresh expected hashes; inert poisonous source; valid-CRC alterations; duplicate/extra/missing files; unsafe paths, aliases/types/encryption; corrupt compression; malformed/duplicate manifests; exact/over-limit boundaries; input rereading; CLI JSON and exit status. No archive code or delivery APIs were imported. [Integrity test log](integrity-tests.log).
- **70/70 aggregate cache/integrity tests pass**: 43 existing plus 27 new. [Aggregate log](cache-suite.log). The earlier 66-test run preceded four additional regressions and is not the final count. These tests use synthetic network/provider behavior; no live worker/booking/notification was run.
- Initial test-agent and independent-reviewer runs hit `PermissionError [WinError 5]` creating/cleaning fixtures in the Windows sandbox package's `AC\Temp`: respectively 23 tests/72 setup-cleanup errors and 27 tests/80 setup-cleanup errors. They yielded no passing assertion evidence. The blocked target was abandoned; tests passed in explicitly writable workspace temp directories. No repeated attempt or escalation was made against that blocked target. The independent reviewer completed source review and a separate safe corrupt-deflate probe, not a passing independent full-suite run.
- Independent source review found no remaining blocker. A corrupt-deflate fixture returns structured `ok: false`, not a traceback. Actionlint v1.7.12 and CRLF-aware whitespace validation pass. No dependency installation occurred.
- Existing cache PR CI discovers `test_cache*.py`, so this new module is included without workflow edits. Enumerate every event/attempt for the final head and verify the tested merge/tree; final remote SHA and CI links are recorded in the draft PR description after push. No push-event test is expected for this branch name under current filters. The desktop suite is not triggered by this helper-only diff.

No UI/device, installed-client, Play Console, release/update, live-provider or actual notification-delivery testing was performed in this focused pass. No merge, deployment, release, production dispatch, credential/security change, spending or third-party contact occurred. The historical #14 Windows `cache_close` timeout remains unresolved; today's data-only results do not clear it. Canonical desktop/mobile/service reconciliation and the October 22 partial task remain separate follow-ups. There is no current access or usage blocker on the completed local validation; the cloud task's earlier usage-limit failure remains historical evidence.
