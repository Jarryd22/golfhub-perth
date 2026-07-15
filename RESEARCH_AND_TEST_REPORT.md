# GolfHub Perth v4 - research and verification report

## Product decisions implemented

- Kept the original black, charcoal and amber visual identity.
- Rebuilt the production interface with PySide6/Qt for a native Windows application and reliable packaging.
- Simplified the primary journey to date, round, time, players, courses, cached search, live refresh and official booking.
- Added responsive two-row filters and wrapping result content for 980 x 640, 1366 x 720 and larger screens.
- Added real bundled weather-condition artwork plus temperature, rain chance and wind.
- Added explicit empty, cached, live, loading, cancellation and fallback states.
- Added Show All / Show First 12 controls so tee times are never silently hidden.
- Replaced Wembley's misleading empty scrape with official Old/Tuart product-level Available, Full or Not released status and a dated handoff for exact slots; all four current 9/18-hole fee products are covered.
- Promoted Maylands and Joondalup from generic links to verified live 9/18-hole feeds, and added Yanchep National Park's official WA Government online purchase route.

## Coverage and architecture

- 41 unique public-access Perth, Peel and nearby courses.
- 20 integrated availability feeds.
- 21 official direct-access entries.
- Production entry: `main_qt.py`.
- UI: `app/qt_golfhub_app.py`.
- scraper/core: `app/golfhub_core.py`.
- cache transport: `app/shared_cache.py`.
- mutable cache, logs and diagnostics: `%LOCALAPPDATA%\GolfHub`.

The GitHub workflow uses stock Python 3.12 with no Tk, CustomTkinter, Qt or Linux GUI package installation. Seven four-day jobs cover the rolling 28-day Perth booking window in parallel. A missing first-run cache branch is tolerated; later runs can reuse prior per-course results for isolated failures. The publisher strictly validates 56 snapshots, creates `index.json`, and force-pushes a fresh orphan snapshot to `cache` with up to three attempts. Weather follows the upstream provider's available forecast horizon and is not represented as 28-day weather coverage.

## Verification completed

- The complete automated regression suite passed: 28/28 tests.
- 41/41 course and official-link audit passed.
- Final live one-day cache integration for 15 July 2026: 37 eligible 18-hole results, 37 eligible 9-hole results, 19/19 live providers fresh for each round, 290 currently bookable tee-time rows, Wembley Old/Tuart availability status for both round types, Maylands returning 7 live 18-hole and 11 live 9-hole rows, weather attached to 74/74 course-round results, no errors and no invalid booking URLs.
- Joondalup's normal cache pipeline was separately verified on its open 19 July sheet with 19 live 18-hole rows and 31 live 9-hole rows, weather and correct dated official URLs.
- Qt construction, four-week date limit, responsive minimum-width controls, cached direct-result reuse, Show All tee times and bundled weather icon rendering are regression-tested.
- Workflow schedule, anchored seven-shard range, strict 56-file validation, shared weather reuse, stale fallback, outage gating and absence of GUI runtime dependencies are regression-tested.
- Native offscreen renders were visually inspected at 980 x 640, 1366 x 720 and full desktop sizes, including the course panel.
- PyInstaller one-folder build completed successfully.
- Inno Setup per-user installer compiled successfully.
- The exact installer returned exit code 0; its installed executable opened a responsive `Golf Hub Perth` window and exited cleanly with code 0.

## Public cache

Repository: `https://github.com/Jarryd22/golfhub-perth`

Raw cache: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache`

The release is handed off only after the workflow source is published, manually dispatched and the generated cache is verified from the public raw URL.

## Booking and privacy boundaries

GolfHub discovers availability and opens official booking or visitor-information pages; it does not reserve or purchase tee times. Availability may change after a cache snapshot. Public cache files must never contain tokens, credentials or personal data. Making the repository private later disables anonymous raw cache access unless the generated cache is hosted separately.
