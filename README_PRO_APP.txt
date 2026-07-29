GOLFHUB PERTH v5.0.0
====================

FIRST RUN (WINDOWS)
1. Download GolfHub_Perth_Setup_v5.exe.
2. Double-click it and follow the installer.
3. Open GolfHub Perth from the desktop shortcut or Start menu.

Python is not required. There is nothing to unzip and no command window is used.

This independent build is not yet code-signed, so Windows SmartScreen may ask for confirmation on first install.

Release artifact: GolfHub_Perth_Setup_v5.exe - 123423086 bytes - SHA-256 E894C2486A8CC3D3DE0F04A7CBEB2238E363768EB999081337A940CED95AF0F9.

QUICK USE
- Open the anchored Dates dropdown beneath the search field. Its prominent TODAY banner and highlight identify the current Perth day; select any 1-28 individual dates, including nonconsecutive dates, then apply. It does not open as a separate app window. The month grid has no week-number gutter or duplicate dates from the adjacent months and stays on the month being edited while you select.
- Choose 9/18 holes, preferred time, player count and courses.
- Search the fast shared cache for every selected date. Refresh Live is available only when one date is selected.
- Results are grouped by selected date, and course names are ordered A-Z within every date.
- If an older cache request is still finishing after filters change, GolfHub queues the latest search and prevents stale player-filter results from replacing it.
- Bundled weather icons show temperature, rain chance and wind.
- Courses without an integrated availability feed open their official booking or visitor-information page.

WEMBLEY
GolfHub reports Wembley's official calendar-level Old/Tuart status as Available, Full or Not released. Available is product-level calendar availability, not an exact-row result. Wembley currently protects individual rows with an interactive CAPTCHA/browser check, so unattended caching stores only the safe status and dated official URL. GolfHub never solves, stores, replays or bypasses that check or token. Use View Wembley times to complete the check yourself and inspect exact current rows on Wembley's official page.

COLLIER PARK
Collier Park releases public tee times eight days ahead at 12:00 pm. GolfHub displays exact rows with their date-specific official links once they are released. Before release, or whenever the feed returns no public rows, it plainly says No public tee times showing, explains the eight-day/noon window and provides View official calendar. This is an official-site handoff, not an error or a claim that the course is full.

PLAYER-COUNT ASSISTANCE
On a compatible exact MiClub row with 1-4 players selected, GolfHub makes Prepare & open the focused default after a clear explanation. It proceeds only for one unambiguous row with enough spots, selects exactly the requested number, waits for MiClub's panel transition, verifies that count in player details and stops.

Before closing without continuing, use Release holds & close. If release cannot be verified, the dialog stays open for manual deselection. If you continue to checkout yourself, GolfHub does not alter or release that provider state. GolfHub never presses Confirm Booking, enters login, checkout or payment details, completes a purchase, or handles a CAPTCHA. Unsupported, changed or ambiguous provider pages open for manual selection. Any players uses the normal handoff.

WEATHER
Bundled condition icons show temperature, rain chance and wind. A clear text fallback is used if a forecast is unavailable. Weather coverage follows the provider's forecast horizon and may not extend through the full four-week booking window.

DATA AND PRIVACY
The public GitHub cache contains only public course availability, official booking or visitor-information URLs and public weather data. It is scheduled every 10 minutes and covers 28 booking days; GitHub scheduled runs are best-effort and may begin later than the nominal interval. It must never contain credentials, CAPTCHA responses or personal booking information. GolfHub keeps local cache, logs and diagnostics under %LOCALAPPDATA%\GolfHub.

RELEASE VERIFICATION
Release QA passed 93 automated tests in 9.323 seconds and a read-only audit of 41/41 configured course destinations. Coverage includes the corrected anchored Dates dropdown with no week-number gutter or duplicate adjacent-month dates, the TODAY marker and current-day highlight, arbitrary multi-date selection, latest-search queuing, four-player filtering, Collier Park exact rows and eight-day/noon fallback, Wembley protected availability, and delayed MiClub player-panel verification. The exact final installer was clean-installed and smoke-tested without creating a live booking or temporary hold. Installer size: 123423086 bytes. SHA-256: E894C2486A8CC3D3DE0F04A7CBEB2238E363768EB999081337A940CED95AF0F9.

PUBLIC CACHE
Repository: https://github.com/Jarryd22/golfhub-perth
Raw cache root: https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache
Index: https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache/index.json

If the source repository becomes private, publish the generated cache branch from a separate public repository or static host and update data/cache_config.json to its new raw base URL.

