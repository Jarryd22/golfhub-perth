# Mixed cache recovery journey — 21 November 2026

One controlled offscreen journey passed **43/43 recorded assertions**, with no recorded Python exception or Qt callback error. This is additional diagnostic coverage, not 43 unit-test methods or 43 independent journeys. No application or unit-test file was edited by this probe. No new defect was identified by this journey.

## Source and execution provenance

- Source checkout: `/workspace/golfhub-20261121`.
- Recorded HEAD: `4fe841359f1d0b3e4a261649c286f04d0bfbac54` (PR33).
- **Candidate source was already present before the probe started**: `app/shared_cache.py` contained the parent's cache-age metadata guard. This is not an execution against untouched PR33. Its SHA-256 was `ca42e9054d611e8368556328266479b320baf96217c8a69d5997a198a448885d` both before and after the execution.
- `app/qt_golfhub_app.py` was unchanged PR33 source, SHA-256 `bbf50a775cfbfbe8e126fac8b0fd958545d7455567fc76d72e9aac5ff0cc7403`, stable before/after.
- All synthetic snapshots used normal string timestamps. This journey does not test the malformed cache-age metadata repair.
- Original script SHA-256: `4c19edf6bce76259fd32296f626aadda25f351bc84133286c0223aae8f4ca2e4`.
- Original artifact directory: `/workspace/scratch/golfhub-20261121-recovery`.
- One process execution only, at `2026-11-21T00:20:24.949353+00:00`; no intermediate or failed probe was discarded. The initial tool response was truncated, so its launcher exit-status field was not retained. The script wrote its complete successful JSON and log, and a subsequent process check found no running probe. It was not rerun to recover a tool status.
- The existing Qt/offscreen `Unknown property cursor` messages remain in the raw log; they are not assertion or callback failures.
- Checkout instruction discovery found no `AGENTS.md` or `SKILL.md`; the two checkout `.agents` directories are absent. No relevant coding skill was available in the cloud catalog.

Exact invocation from the original artifact directory:

```sh
mkdir -p first && timeout --signal=TERM --kill-after=5s 30s /workspace/golfhub-perth/.venv/bin/python recovery_probe.py --root /workspace/golfhub-20261121 --output first > first/run.log 2>&1
```

## Observed sequence

1. Find Tee Times for three dates with Araluen and Altone Park selected. Two actual isolated saved JSON files supplied one exact matching row and one provider-error date; the third date had no file. The view reported two loaded days, one matching time, a distinct incomplete-availability date, an unchecked date and one official direct-course card.
2. Space opened the missing-date section. Its visible guidance suggested selecting the date alone and using Refresh Live. Calendar Return/Right/Return removed the other two dates, and Space on Apply committed the missing date alone.
3. Clicking Refresh Live created an inert scan owner. Clicking Stop requested cancellation; the real worker QObject's finished signal was emitted with a synthetic cancelled partial result. The earlier three-date sections and exact card remained. The two original saved files were byte-identical, and the UI save mock had zero calls.
4. Space on the retained BOOK button dispatched the earlier row with the earlier three-date/18-hole/one-player context. The booking method was intercepted before any booking-plan, dialog, hold or browser operation. Explicit mock-owner cleanup restored retry eligibility.
5. Actual course-name typing, Clear and Select visible chose Araluen alone. A mouse click selected 9 holes; setters selected four players and Afternoon. Clicking Find submitted the corrected single-date/9-hole context. A synthetic successful cache completion contained four rows; group/time filtering retained only 3:30 pm and 4:00 pm, each with four spots.
6. The successful replacement removed old date sections, provider/missing notes and the now-unselected direct-course card. Space on its BOOK button dispatched the new row and corrected context. All worker ownership was explicitly released.

Totals: **three inert QThread mocks**, **two intercepted BOOK callbacks**, **zero UI persistence calls**, two original saved files unchanged. Completion and cleanup were deliberately ordered; this does not claim a new thread-race or native lifecycle test.

## Inputs, interception and limits

- Actual Qt mouse/key events: Find, Refresh Live, Stop, round selection, course panel, name typing, Clear, Select visible, missing-date expansion, calendar date toggles and Apply, and both BOOK activations.
- Explicit anchors/setters: initial selected courses/dates/group, focus anchors for targeted key events, scrolling with `ensureWidgetVisible`, final group/preset selection, synthetic worker completion and cleanup. This is not a Tab-only accessibility or system focus-return audit.
- Actual operations: Qt widget construction/rendering, local JSON reads and byte comparison, real CacheWorker/ScanWorker QObject signals and connected UI handlers.
- Inert/intercepted operations: QThread startup/ownership, all worker bodies, UI persistence and booking dispatch. Network sockets/DNS, providers/shared fetch, weather, browser and booking dialog were blocked. No actual alerts/delivery were attempted.
- One compact **980×640** viewport. The two PNGs were visually inspected: missing-date recovery guidance is readable; the final two exact-time cards and BOOK buttons are visible. Scrolling intentionally clips unrelated content at the viewport edges. Existing date-button punctuation artifacts remain a previously deferred issue.
- No installed Windows/Android, native lifecycle timing, live provider availability, booking/holds, browser navigation, notification delivery or screen-reader behavior was tested. Historical Windows `cache_close` and canonical source reconciliation remain unresolved and were not investigated here.

## Coverage relation and evidence

Prior tests separately cover mixed cache states, retained context, cancellation, direct-course links and replacement. This diagnostic joins those operations by following the actual missing-date recovery guidance through a stopped live request and a corrected successful search. It does not repeat the full 28-day or custom-time matrices.

- `recovery_probe.py`: unchanged executed script.
- `first/probe.json`: all 43 named assertions, three stage snapshots, source hashes and callback/error counts.
- `first/run.log`: complete raw stdout/stderr.
- `first/partial-missing-guidance.png`: compact missing-date recovery instructions.
- `first/successful-corrected-retry.png`: corrected result cards and controls.
- `copy-verification.json` in the dated copy: byte-level hashes for original and copied artifacts.
