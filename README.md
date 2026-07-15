# GolfHub Perth

GolfHub Perth is a fast, local-first Windows app for finding public golf tee times and public-access courses around Perth, Peel and nearby areas. It keeps the original charcoal, black and amber identity, then adds a simpler search flow, a four-week booking view, bundled weather icons, and direct handoff to each course's official booking or visitor-information page.

## Install on Windows

1. Download `GolfHub_Perth_Setup_v4.exe` from the latest GitHub release.
2. Double-click it and follow the installer.
3. Open **GolfHub Perth** from the Start menu or desktop shortcut.

Python is not required and there is nothing to unzip. This independent build is not yet code-signed, so Windows SmartScreen may ask you to confirm the first installation.

## What is included

- 41 public-access Perth, Peel and nearby courses in one directory.
- 20 integrated availability feeds and 21 official direct-access links.
- Date, 9/18 holes, time, player and course filters.
- A rolling 28-day tee-time cache scheduled by GitHub Actions every 10 minutes.
- Local cache first, shared public cache second, and a live refresh when required.
- Bundled weather-condition icons with temperature, rain chance and wind.
- Responsive layouts tested from 980 x 640 through normal laptop and desktop sizes.
- Every course action opens its official booking or visitor-information page.

## Using the app

1. Choose a date, round, preferred time and player count.
2. Keep every course selected or open **Courses** to narrow the search.
3. Select **Find tee times** for the fast cached view.
4. Select **Refresh live** when you want to re-check course websites.
5. Use **Book**, **Open booking page** or **View course** to continue on the course's official site or read its walk-in instructions.

Availability can change after a cache snapshot. The official course or booking page is always the final source of truth. Maylands and Joondalup now expose exact live 9- and 18-hole options. Wembley exposes trustworthy Old/Tuart Available, Full or Not released status in GolfHub; its exact slots open on the dated official page because Wembley protects them with its booking check. Embleton remains an official direct-contact course because its portal currently publishes no public online product. Yanchep National Park opens the WA Government's official online purchase page. Weather is shown only within the forecast provider's available horizon, which is shorter than the full 28-day tee-time window.

## Shared cache

The public cache is served from:

`https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache`

The workflow prepares weather once, retries transient weather-rate limits, tolerates a missing first-run cache branch, exports any healthy previous snapshot for per-course stale fallback, runs seven four-day shards in parallel, strictly validates all 56 snapshots, then force-pushes one fresh orphan commit to the dedicated `cache` branch with up to three attempts. No credentials or personal booking information belong in the cache.

If this repository is made private, anonymous `raw.githubusercontent.com` access stops. GolfHub will fall back to its saved local cache and live checks, but instant shared-cache loading will stop unless `public/cache` is moved to a separate public repository or static host.

## Runtime data

Mutable files are kept outside the installed application under `%LOCALAPPDATA%\GolfHub`, including local cache, logs and diagnostics. The installer is per-user and does not require administrator access.

## Development

```powershell
python -m pip install -r requirements.txt
python main_qt.py
```

The production entry point is `main_qt.py`. Scraping and shared logic are in `app/golfhub_core.py`; the Qt interface is in `app/qt_golfhub_app.py`.

## Tests

```powershell
python -m unittest -v tests.test_golfhub_v3 tests.test_cache_pipeline
```

Current source verification: 28/28 automated tests passed, including cache completeness, weather reuse, stale fallback, outage-gate and verified booking-route coverage. The 41/41 course and official-link audit also passed. The exact final installer is launch-tested before release.

## Windows build

Run `build_tools\build_v4.bat`. The reproducible build uses `GolfHub_v4.spec` and `build_tools\GolfHub_v4_InnoSetup.iss`; the final output is `installer\GolfHub_Perth_Setup_v4.exe`.
