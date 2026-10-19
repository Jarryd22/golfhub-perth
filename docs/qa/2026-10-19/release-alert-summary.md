# Release and alert audit — 19 October 2026 Perth

Read-only checks in the saved Linux cloud workspace. No production workflow, Firebase authentication, alert send, installer/APK download, installation or native-device test occurred.

## Distribution repositories

- `Jarryd22/golfhub-perth-android-updates`: only `main` at `cfec2bbd6205edae0f733f6931e0e535db284e48`, no open PRs, latest release [Android 0.1.19](https://github.com/Jarryd22/golfhub-perth-android-updates/releases/tag/android-v0.1.19). Six releases were returned; none is a draft or prerelease.
- `Jarryd22/golfhub-perth-updates`: only `main` at `b53909b8edac42055071e01914aff7d1921a8305`, no open PRs, latest release [Windows 5.1.17](https://github.com/Jarryd22/golfhub-perth-updates/releases/tag/v5.1.17). Five releases were returned; none is a draft or prerelease.
- Both current manifest downloads match their current GitHub asset digests and sizes. Latest aliases byte-match versioned manifests. Decoded binary URL, size and SHA-256 agree with current GitHub asset metadata.
- Both manifests have a 64-byte signature, but signature verification was **not run** because this source checkout has no trusted updater public key or updater implementation. Yesterday's signature verification is not reused as today's result. Binary bytes and Android signing certificate were not independently checked.
- Windows release notes still say the upgrade on the previously affected laptop remains unconfirmed. This is a statement in the published notes, not a new device observation.

Evidence: [repository/release metadata](release-alert-metadata.json), [current manifest checks](release-alert-manifests.json).

## Alert source and isolated runtime

The checked-in workflow `.github/workflows/check-alerts.yml` extracts and runs `.github/alerts-runtime.zip`, not the loose service files. The archive SHA-256 is `63d7b944607ff8ce29f293adb64d647cbb6636f227da63971c0c1a181cfdaf30`.

The loose source tree lacks `app/availability.py`, `app/cache_schema.py`, `service/__init__.py`, `service/catalog.py`, `service/search.py` and `service/checker_gate.py`; all are present in that archive. The shared `push_logic.py`, `push_worker.py` and `recurrence.py` bytes match the archive. The archived and loose `golfhub_core.py` differ. This remains a source-completeness/reconciliation gap; it is not proof of a production outage.

The archive contains no test files. Ten new deterministic audit cases against its pure alert logic passed in an isolated temporary extraction with socket connection and send methods blocked. These exercise filter validation, disabled watches, quiet initial baselines, explicitly requested existing matches, new-opening/replay behavior, stale/future/unknown data, past tee times, Perth quiet hours/TTL, recurrence, acknowledgement and generation/event identifiers. They are audit cases, not ten existing branch tests or delivery/device tests.

The root alert suites were **not run** because module import is blocked by the absent source dependencies. Worker/delivery tests were **not run** because `firebase_admin` is absent in this Python environment; the runtime pins `firebase-admin==7.1.0` and `tzdata==2026.4`. No dependencies were installed for this audit, and no Firebase client, worker main or send path was invoked. These are import/environment blockers, not assertion failures. Real notification delivery remains unverified.

Evidence: [reproducible offline audit](release-alert-audit.py), [results and source inventory](release-alert-service.json). Run with `python docs/qa/2026-10-19/release-alert-audit.py` from this repository.
