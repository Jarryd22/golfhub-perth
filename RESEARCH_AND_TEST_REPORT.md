# GolfHub Perth v4 - research and verification report

## Product decisions implemented

- Kept the original black, charcoal and amber visual identity.
- Rebuilt the production interface with PySide6/Qt for a native Windows application and reliable packaging.
- Simplified the primary journey to date, round, time, players, courses, cached search, live refresh and official booking.
- Added responsive two-row filters and wrapping result content for 980 x 640, 1366 x 720 and larger screens.
- Added real bundled weather-condition artwork plus temperature, rain chance and wind.
- Added explicit empty, cached, live, loading, cancellation and fallback states.
- Added Show All / Show First 12 controls so tee times are never silently hidden.

## Coverage and architecture

- 31 unique Perth and Peel courses.
- 15 integrated availability feeds.
- 16 official direct-booking entries.
- Production entry: `main_qt.py`.
- UI: `app/qt_golfhub_app.py`.
- scraper/core: `app/golfhub_core.py`.
- cache transport: `app/shared_cache.py`.
- mutable cache, logs and diagnostics: `%LOCALAPPDATA%\GolfHub`.

The GitHub workflow uses stock Python 3.12 with no Tk, CustomTkinter, Qt or Linux GUI package installation. Seven four-day jobs cover the rolling 28-day Perth booking window in parallel, then publish one cache manifest. Weather follows the upstream provider's available forecast horizon and is not represented as 28-day weather coverage.

## Verification completed

- 15/15 automated regression tests passed.
- 31/31 course and official-link audit passed.
- One-day cache integration: 28 eligible 18-hole results, 29 eligible 9-hole results, weather attached to 57/57 results, no errors and no invalid booking URLs.
- Qt construction, four-week date limit, responsive minimum-width controls, cached direct-result reuse, Show All tee times and bundled weather icon rendering are regression-tested.
- Workflow schedule, seven-shard range, write permissions and absence of GUI runtime dependencies are regression-tested.
- Native offscreen renders were visually inspected at 980 x 640, 1366 x 720 and full desktop sizes, including the course panel.
- PyInstaller one-folder build completed successfully.
- Inno Setup per-user installer compiled successfully.
- The exact installer returned exit code 0; its installed executable opened a responsive `Golf Hub Perth` window and exited cleanly with code 0.

## Public cache

Repository: `https://github.com/Jarryd22/golfhub-perth`

Raw cache: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/main/public/cache`

The release is handed off only after the workflow source is published, manually dispatched and the generated cache is verified from the public raw URL.

## Booking and privacy boundaries

GolfHub discovers availability and opens official booking pages; it does not reserve or purchase tee times. Availability may change after a cache snapshot. Public cache files must never contain tokens, credentials or personal data. Making the repository private later disables anonymous raw cache access unless the generated cache is hosted separately.
