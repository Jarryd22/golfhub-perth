# Release and alert audit — 20 October 2026 Perth

Read-only checks at approximately 08:03–08:05 Perth in the saved Linux cloud workspace. No production workflow, Firebase authentication, alert send, installer/APK download, installation or native-device test occurred. The supplied hourly audit was not repeated.

## Distribution repositories

- `Jarryd22/golfhub-perth-android-updates`: only `main` at `cfec2bbd6205edae0f733f6931e0e535db284e48`, no open PRs, latest release [Android 0.1.19](https://github.com/Jarryd22/golfhub-perth-android-updates/releases/tag/android-v0.1.19). Six releases returned; none is a draft or prerelease.
- `Jarryd22/golfhub-perth-updates`: only `main` at `b53909b8edac42055071e01914aff7d1921a8305`, no open PRs, latest release [Windows 5.1.17](https://github.com/Jarryd22/golfhub-perth-updates/releases/tag/v5.1.17). Five releases returned; none is a draft or prerelease.
- Both current manifest downloads match current GitHub asset digests and sizes. Latest aliases byte-match versioned manifests. Decoded binary URL, size and SHA-256 agree with current GitHub asset metadata. All values remain unchanged from yesterday.
- Each manifest contains a 64-byte signature; signature verification was **not run** because this source checkout has no trusted updater public key or updater implementation. Prior signature results were not reused. Binary bytes and Android signing certificate were not independently checked.
- Windows release notes still say the upgrade on the previously affected laptop remains unconfirmed. That is published release-note context, not a new device observation.

Evidence: [repository/release metadata](release-alert-metadata.json), [current manifest checks](release-alert-manifests.json), [bounded manifest audit script](release-alert-manifest-audit.py). Metadata was obtained through the authenticated read-only GitHub connector; the local `gh` token is invalid. Manifest checks use anonymous public downloads of four small JSON files, with a 64 KiB bound each.

## Alert source and isolated runtime

The checked-in workflow `.github/workflows/check-alerts.yml` extracts and runs `.github/alerts-runtime.zip`, not the loose service files. Archive SHA-256: `63d7b944607ff8ce29f293adb64d647cbb6636f227da63971c0c1a181cfdaf30`. Both archive and workflow are byte-identical to current main `25de15b` and PR #11 `6d60354`.

The loose source tree still lacks `app/availability.py`, `app/cache_schema.py`, `service/__init__.py`, `service/catalog.py`, `service/search.py` and `service/checker_gate.py`; all are present in the archive. Shared `push_logic.py`, `push_worker.py` and `recurrence.py` bytes match the archive; archived and loose `golfhub_core.py` differ. This remains a source-completeness/reconciliation gap, not evidence of a production outage. No runtime modules were copied into application source.

**10/10 deterministic pure-logic audit cases passed**, rerunning yesterday's unchanged fixture clock in an isolated temporary extraction with socket connections and sends blocked. These cover filter validation, disabled watches, quiet initial baselines, explicitly requested existing matches, new openings/replays, stale/future/unknown data, past tee times, Perth quiet hours/TTL, recurrence, acknowledgement, and generation/event identifiers. Count these ten cases separately from desktop branch tests. The archive contains no test files; no phone or delivery tests are implied.

The root alert suites ran **zero tests** because imports remain blocked by missing source dependencies (`app.cache_schema` and `service.catalog`). Worker/delivery tests ran **zero tests** because `firebase_admin` is absent. Those are import/environment limitations, not assertion failures or automatic-approval denials. No dependency installation, credential access, Firebase client, worker main or send path was attempted. Real notification delivery remains unverified; the supplied zero-watch/zero-observation heartbeat establishes no delivery behavior.

Evidence: [reproducible offline audit](release-alert-audit.py), [results and source inventory](release-alert-service.json). Run with `python docs/qa/2026-10-20/release-alert-audit.py` from this repository.
