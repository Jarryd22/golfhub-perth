# GolfHub Perth v5.0.0

GolfHub Perth is a fast, local-first Windows app for finding public golf tee times and public-access courses around Perth, Peel and nearby areas. It keeps the original charcoal, black and amber identity while making it simpler to compare one date or any combination of dates in the rolling four-week window, check the weather and continue safely on each course's official booking site.

## Install on Windows

1. Download `GolfHub_Perth_Setup_v5.exe`.
2. Double-click it and follow the installer.
3. Open **GolfHub Perth** from the Start menu or desktop shortcut.

Python is not required and there is nothing to unzip. This independent build is not yet code-signed, so Windows SmartScreen may ask you to confirm the first installation.

Release artifact: `GolfHub_Perth_Setup_v5.exe` - 123423086 bytes - SHA-256 `E894C2486A8CC3D3DE0F04A7CBEB2238E363768EB999081337A940CED95AF0F9`.

## What is included

- 41 public-access Perth, Peel and nearby courses in one directory.
- 20 integrated availability feeds and 21 official direct-access links.
- An anchored **Dates** dropdown that stays attached to the search field rather than opening as a separate window, with a prominent **TODAY** banner, a clear current-day highlight and support for any 1-28 individual dates, including nonconsecutive dates. The month grid has no week-number gutter or duplicate adjacent-month dates, and it stays on the month being edited while dates are selected.
- Date, 9/18 holes, time, player and course filters.
- Course result sections ordered alphabetically so repeated searches stay easy to scan.
- A rolling 28-day tee-time cache scheduled by GitHub Actions every 10 minutes. Scheduled runs are best-effort and can start late.
- Local cache first, shared public cache second, and a live refresh when required.
- Bundled weather-condition icons with temperature, rain chance and wind.
- Weather follows the forecast provider's available horizon; later booking dates use a clear text fallback when no forecast is available.
- Responsive layouts for compact laptop, normal desktop and larger screens.
- Guarded player-count assistance on compatible MiClub tee-time pages.
- Latest-search queuing prevents an earlier startup cache request from replacing newer date, course or player-filter choices.
- Every course action continues on its official booking or visitor-information page.

## Using the app

1. Open the anchored **Dates** dropdown. Its **TODAY** banner identifies the current Perth day; click any combination of 1-28 days to add or remove them, then apply the selection. The dropdown closes back into the search panel and never becomes a separate app window.
2. Choose 9 or 18 holes, preferred time and player count.
3. Keep every course selected or open **Courses** to narrow the search.
4. Select **Find tee times** for the fast cached view.
5. When exactly one date is selected, use **Refresh live** for a fresh direct check when available. Searches across multiple selected dates use the shared/local cache.
6. Review the alphabetically ordered course sections, weather and available times.
7. Use **Book**, **Open booking page** or **View course** to continue on the official site.

Searches across selected dates use the shared/local cache and group results chronologically by date. The first selected date with availability is expanded and later selected dates open on demand, keeping a large result set responsive. If a cache request is already finishing when filters change, GolfHub queues the latest search and discards the stale display result so the selected player count and other filters remain authoritative.

Availability can change after a cache snapshot. The official course or booking page is always the final source of truth.

### Wembley

GolfHub reports Wembley's official calendar-level Old/Tuart status as **Available**, **Full** or **Not released**. **Available** means the official calendar advertises booking availability; it does not mean GolfHub fetched exact tee-time rows. Wembley currently places individual rows behind an interactive CAPTCHA/browser check, so the unattended cache stores only the safe product-level status and dated official URL. GolfHub never solves, stores, replays or bypasses that check or its token. Select **View Wembley times** to complete the check yourself and inspect the exact current rows on Wembley's official page.

### Collier Park

Collier Park releases public tee times eight days ahead at 12:00 pm. When exact rows have been released, GolfHub displays those rows and keeps their date-specific official timesheet links. If the selected date has not opened yet or the feed returns no public rows, GolfHub shows a plain **No public tee times showing** result, explains the eight-day/noon release window and provides **View official calendar**. An empty feed is therefore a clear official-site handoff, not an error or a false claim that the course is full.

### Player-count booking assistance

On a compatible exact MiClub row with 1-4 players selected, GolfHub presents **Prepare & open** as the focused default action after a clear explanation. It proceeds only when one row matches unambiguously and enough spots remain, selects exactly the requested number, waits for MiClub's panel transition, verifies the requested player count in the official player-details panel and stops there.

Before closing without continuing, use **Release holds & close**. GolfHub attempts to unlock only the cells it selected and waits for the provider's asynchronous release. If release cannot be verified, the dialog remains open and asks you to deselect manually. If you continue to checkout yourself, GolfHub deliberately does not alter or release that provider state.

GolfHub never presses **Confirm Booking**, enters login, cart, checkout or payment details, completes a purchase, or handles a CAPTCHA. Unsupported, changed or ambiguous pages open for manual selection instead. Choosing **Any** players also uses the normal official-page handoff.

## Shared cache

The public cache is served from:

Raw cache root: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache`

Index: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache/index.json`

The workflow prepares weather once, retries transient weather-rate limits, tolerates a missing first-run cache branch, exports any healthy previous snapshot for per-course stale fallback, runs seven four-day shards in parallel, strictly validates all 56 date/round snapshots, then force-pushes one fresh orphan commit to the dedicated `cache` branch with up to three attempts. No credentials, CAPTCHA responses or personal booking information belong in the cache.

GitHub scheduled workflows are best-effort, so a run can begin later than its nominal ten-minute mark. GolfHub shows the cache age and always provides an official-site handoff for final confirmation.

If this repository is made private, anonymous `raw.githubusercontent.com` access stops. Publish the generated cache branch from a separate public repository or static host and update `data/cache_config.json` to its new raw base URL. Otherwise GolfHub falls back to its saved local cache and live checks.

## Runtime data

Mutable files are kept outside the installed application under `%LOCALAPPDATA%\GolfHub`, including local cache, logs and diagnostics. The installer is per-user and does not require administrator access.

## Development

```powershell
python -m pip install -r requirements.txt
python main_qt.py
```

The production entry point is `main_qt.py`. Scraping and shared logic are in `app/golfhub_core.py`; the Qt interface is in `app/qt_golfhub_app.py`; guarded provider handoff logic is kept in the booking-assist modules.

## Tests

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QTWEBENGINE_CHROMIUM_FLAGS='--disable-gpu'
python -m unittest discover -s tests -v
```

Release QA passed 93 automated source tests in 9.323 seconds and a read-only audit of all 41 configured course destinations. Coverage includes the corrected anchored calendar dropdown with no week-number gutter or duplicate adjacent-month dates, the **TODAY** marker and current-day highlight, arbitrary and nonconsecutive multi-date selection, latest-search queuing, A-Z result ordering, player filtering, cache completeness and fallback, weather icons, Collier Park exact-row and eight-day/noon fallback behavior, Wembley protected availability, and guarded booking assistance with delayed MiClub verification. The exact final installer was clean-installed and smoke-tested without creating a live booking or temporary hold.

## Windows build

Run `build_tools\build_v5.bat`. The v5 build uses `GolfHub_v5.spec` and `build_tools\GolfHub_v5_InnoSetup.iss`; the intended output is `installer\GolfHub_Perth_Setup_v5.exe`.

