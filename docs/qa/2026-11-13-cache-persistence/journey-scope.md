# Independent cache-persistence UI evidence

The identical final [probe](cache-write-ui-probe.py) ran on exact PR29 `8dff803ebc6e61b1a309d7c17c5277909392f5d2` and the November 13 repair. It calls the actual `shared_cache.fetch_shared_snapshot`, validator, local-cache functions and UI completion/rendering methods. Downloads are mocked `BytesIO` responses; save failures are targeted `OSError` injections at `Path.mkdir`, `Path.write_text` or `Path.replace`. Cache files are real files in isolated temporary directories. No filesystem permissions, credentials or security settings were changed.

Source hashes identify the tested code before a later documentation commit:

- Baseline `app/shared_cache.py`: `412cca2cb9fc6b2cdc734e7abcf61003ee3669b219277cd1e1d12a2ccb8772b4`.
- Repair `app/shared_cache.py`: `9a42d4156486c7000a61492d9041e11c1a68c5c84b3634037f6f600a2f90459f`.
- Unchanged `app/qt_golfhub_app.py`: `09b17e1a6a89a164d96ed6fc82413d0fa9f64d37244736b225a1150a12736ca1`.

## Before and after

[Baseline JSON](before/probe.json), [baseline log](before-ui.log), [repair JSON](after/probe.json) and [repair log](after-ui.log) retain all nine scenarios. Each downloaded valid snapshot contains an Araluen 10:00am/four-spot row and a 9:00am/two-spot row; the submitted four-player filter should display only 10:00am. Where present, the saved cache is one day old and contains 8:00am/four spots instead. The selected dates, course, round and player context remain identical throughout.

| Scenario | Exact PR29 | Repair |
| --- | --- | --- |
| Temporary-file write fails; one date has saved data | Valid download discarded; saved 8:00am row displayed with `SAVED CACHE / 24 HOURS AGO` | Downloaded 10:00am row displayed as shared cache; saved bytes unchanged |
| Directory creation fails; one date has no saved data | Valid download discarded; live fallback invoked with submitted context | Downloaded row displayed; no live fallback |
| Replacement fails for two dates; only the first has saved data | Both downloads discarded; old first date gives `1 OF 2 DAYS` | Both downloaded dates retained; `2 OF 2 DAYS` |
| Temporary-file write fails for two dates without saved data | `SHARED CACHE UNAVAILABLE`, despite valid downloads | `2 OF 2 DAYS`, with downloaded matching rows |
| Valid save, single date / multiple dates | Download displayed and stored | Unchanged |
| Invalid payload with saved data | Download rejected; saved row displayed, bytes preserved | Unchanged |
| Simulated offline transport with saved data / without multi-date data | Saved fallback / unavailable guidance | Unchanged |

The [evidence comparison](ui-comparison.json), produced by [this checker](compare-ui-evidence.py), passes all nine case comparisons: four corrected scenarios and five unchanged controls. Before and after both have zero Qt callback errors. Invalid input uses a malformed result record; offline transport uses a mocked `URLError`, not an actual network outage. Single-date live fallback is intercepted, so the baseline screenshot for that case does **not** represent the live worker's eventual UI state.

The repair does not claim that saving succeeded. Original saved bytes remain unchanged after the injected errors. A failed replacement leaves a `.tmp` file in the isolated cache directory, as it did before; temporary-file cleanup was not added to the product. The entire isolated directory is removed by the probe. No downloaded-payload mutation or persistence guarantee is inferred from displaying it in memory.

Multi-date groups remain lazy: the first date's matching row is constructed initially, while the summary counts both valid dates. These observations are diagnostic cases, not additional unittest methods.

## Fixture history and visual checks

The first baseline execution exited successfully but used an unsuitable old-cache timestamp: `2032-12-31` is in the future relative to the actual 2026 clock, despite the fixture's 2033 search dates. This made the saved age label say less than a minute. The [original script](initial-age-fixture/probe.py), log, JSON and PNGs remain under `initial-age-fixture/`. The [two-line fixture correction](initial-age-fixture/fixture-correction.diff.gz) uses actual current UTC time minus one day, and the corrected baseline was rerun before the identical-script repair replay. Behavioral failures did not change. No fixture exception, failed assertion or product-age defect is claimed.

Visually inspected 980×640 before/after screenshots show the old saved source becoming a shared source, and the multi-date unavailable state becoming an explicit `2 of 2 dates loaded` summary. The selected course and four-player controls remain visible. The first tee-time row is partly below the initial compact viewport; JSON records its time/spots. This is ordinary scroll position, not a claimed layout repair or action-reachability check. Existing date punctuation remains outside scope.

## Established diagnostics

Three scripts were copied unchanged from November 12; [provenance](journey-evidence-provenance.json) records their hashes and byte equality. All executions exit zero with no callback errors:

- [50 filter combinations](journeys.json), [log](journeys.log): actual offscreen controls submit 9/18 holes, Any/1–4 players and five time presets. Synthetic matching rows and submitted dates remain correct; worker launch is intercepted.
- [Five startup decisions](startup/startup-decisions.json), [log](startup.log): no saved data, saved empty/error data, single-date fallback and multi-date missing-cache behavior remain correct. Scheduled and live work are intercepted.
- [Eight PR29 completion controls](completion/probe.json), [log](completion.log): real QObject signals with inert thread/executor substitutes still emit exactly once after setup/iteration failure, preserve a collected snapshot and retain normal/per-future/all-future-error behavior. No real-QThread or native-close diagnostic was repeated today.

Course-count/grid runtime code is unchanged and their extra diagnostic probes were not rerun by this evidence task. The parent's aggregate covers their existing unit regressions. Source-only complementary review found no additional justified result/booking/input repair: prior row-link, retained-context, show-all, course count and calendar input fixes remain covered. No speculative app change was proposed.

## Limits

Sockets/DNS, provider/weather calls, browser navigation, booking dialogs and worker launch were blocked or intercepted. No live booking, hold, notification, production workflow or external mutation occurred. These are deliberately injected storage/transport failures, not observed production incidents or a measurement of disk-failure frequency. The probe made no application, unittest or workflow edits.

Native Windows/Android, installed packages, actual disk exhaustion/permissions, real providers, live booking/notification delivery, native accessibility and canonical source integration remain unverified. Historical Windows `cache_close` remains unresolved and is unrelated to this bounded save-error reproduction. No denied production-history route was retried or bypassed. All diagnostic processes finished; no new blocker, denied action or uncertain write remains.
