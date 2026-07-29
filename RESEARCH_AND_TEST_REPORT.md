# GolfHub Perth v5.0.0 - research and verification report

## Product decisions implemented

- Kept the original black, charcoal and amber visual identity.
- Continued with PySide6/Qt for a native Windows interface, packaged desktop operation and an embedded official-site handoff where guarded booking assistance is supported.
- Added an anchored **Dates** dropdown that remains attached to the search field instead of creating a separate window, prominently identifies and highlights the current Perth date with a **TODAY** banner, and selects any 1-28 individual dates, including nonconsecutive dates, within the rolling four-week booking window. The corrected month grid hides week numbers and adjacent-month cells so duplicate-looking dates cannot appear, and it stays on the active month through cross-month selection.
- Grouped results chronologically by selected date and built later date sections only when opened so large multi-date searches remain responsive.
- Ordered tee-time course sections alphabetically within each result day, with official direct-link results also ordered A-Z.
- Kept date, 9/18 holes, time, players and course filters in the primary journey.
- Retained bundled weather-condition icons plus temperature, rain chance and wind, with text fallback outside the forecast horizon.
- Added explicit empty, cached, live, loading, cancellation, protected-calendar and fallback states.
- Kept Show All / Show First 12 controls so tee times are never silently hidden.
- Reworked Wembley messaging so confirmed product-level availability is not presented as a misleading zero-result failure.
- Added a Collier Park zero-row state that explains its eight-days-ahead, 12:00 pm public release window and links to the official calendar, while preserving exact rows and date-specific timesheet links after release.
- Added guarded player-count assistance for compatible exact MiClub tee-time pages, with a clear opt-in choice and reversible-hold path.
- Made **Prepare & open** the focused default booking-assist action and added delayed verification after MiClub's player-panel transition.
- Queued the latest requested search while an earlier cache request finishes, then suppressed the stale result so changed player and other filter choices cannot be overwritten.

## Coverage and architecture

- 41 unique public-access Perth, Peel and nearby courses.
- 20 integrated availability feeds.
- 21 official direct-access entries.
- Production entry: `main_qt.py`.
- UI: `app/qt_golfhub_app.py`.
- scraper/core: `app/golfhub_core.py`.
- cache transport: `app/shared_cache.py`.
- guarded provider handoff: booking-assist modules under `app/`.
- mutable cache, logs and diagnostics: `%LOCALAPPDATA%\GolfHub`.

The GitHub workflow uses stock Python 3.12 without Qt or Linux GUI packages. Its `*/10 * * * *` cron is a nominal ten-minute schedule; GitHub Actions scheduling is best-effort and runs may start late. Seven four-day jobs cover the rolling 28-day Perth booking window in parallel, producing 28 dates for both 18- and 9-hole searches: 56 validated snapshots in total. A missing first-run cache branch is tolerated; later runs can reuse prior per-course results for isolated failures. The publisher strictly validates the snapshot set, creates `index.json`, and force-pushes a fresh orphan snapshot to `cache` with retry. Weather follows the upstream provider's available forecast horizon and is not represented as 28-day weather coverage.

## Wembley research and boundary

Wembley's official public calendar can label its Old and Tuart products **Available**, **Full** or **Not released**. That provides useful calendar-level status and a correctly dated official handoff, but **Available** is not evidence that GolfHub obtained exact tee-time rows. The current individual timesheet requires an interactive CAPTCHA/browser check before rows are exposed.

GolfHub therefore never solves, replays, persists or bypasses a CAPTCHA response. While protection is enabled, the cache records only safe product-level status and a dated official URL. The user selects **View Wembley times** and completes the interactive check on Wembley's official page. The exact-row parser remains fail-safe so ordinary public rows can be used if Wembley later exposes them without protection.

## Collier Park release behavior

Collier Park's official calendar states that public tee times open eight days in advance at 12:00 pm. GolfHub retains exact public rows and their date-specific official timesheet links when those rows exist. A zero-row response is instead rendered as a deliberate course result: **No public tee times showing**, the eight-day/noon release explanation and a **View official calendar** action. This avoids presenting an unreleased date as a scraper failure or claiming that Collier Park is full.

## Guarded MiClub player-count assistance

MiClub's public page temporarily locks an available cell when it is selected, before the user reaches its player-details panel. For that reason the app treats player preselection as an explicit side effect:

1. It is offered only for an exact, supported MiClub timesheet row and a requested count of 1-4 players.
2. GolfHub explains the temporary hold before selecting anything and presents **Prepare & open** as the focused default action.
3. The helper requires one unambiguous matching row with enough currently available cells and stops if the page has changed.
4. It selects exactly the requested number of cells, waits for MiClub's asynchronous panel transition, verifies that exact count in the official player-details panel and stops before Confirm Booking.
5. **Release holds & close** targets only the cells selected by that GolfHub session and waits for the asynchronous unlock.
6. If release cannot be verified, the dialog remains open and requests manual deselection.
7. If the user manually continues to checkout, GolfHub deliberately does not alter or release that provider state.
8. GolfHub never invokes Confirm Booking, login, cart, checkout, payment or CAPTCHA controls.

Quick18, direct-link, calendar-only, changed or ambiguous pages use the exact official-page handoff without claiming automatic player selection. A player filter of **Any** also uses the normal handoff.

## Verification scope for v5

Release QA covers:

- complete automated source regression;
- the corrected anchored Dates dropdown, prominent TODAY marker and current-day highlight, hidden week numbers and adjacent-month dates, stable cross-month page, arbitrary single-date and multi-date cached searches, nonconsecutive selection, at-least-one-date enforcement and real calendar mouse-click behavior;
- latest-search queuing and stale-result suppression when a player or other filter changes during startup cache loading;
- A-Z ordering for course result sections and official direct links;
- responsive and lazy multi-day rendering;
- bundled weather-icon rendering and forecast fallback;
- Wembley protected-calendar status and safe URL handling;
- Collier Park exact-row links and the clear eight-days/noon zero-row fallback;
- booking-assist planning, focused Prepare & open default, fail-closed rules, JavaScript syntax, delayed MiClub panel verification and isolated-page selection/release behavior;
- cache workflow schedule, 28-day anchoring, 56-file validation, shared weather reuse, stale fallback and outage gating;
- 41-course link/coverage audit;
- packaged executable, same-AppId replacement configuration, fresh per-user installation, shortcuts and installed-app smoke tests.

On 16 July 2026, 93 automated tests passed in 9.323 seconds and the read-only course-route audit passed 41/41 configured destinations. The exact final installer was clean-installed and smoke-tested with the corrected anchored Dates dropdown, TODAY banner and current-day highlight, real nonconsecutive cross-month calendar clicks without week numbers or duplicate adjacent-month dates, multi-date cache loading, queued latest-search behavior, four-player filtering and dialog behavior, Collier Park exact-row and eight-day/noon fallback paths, Wembley product-level safe fallback, weather icons, A-Z ordering, shortcuts and the embedded browser runtime. No live booking or temporary hold was created. Final installer: 123423086 bytes, SHA-256 `E894C2486A8CC3D3DE0F04A7CBEB2238E363768EB999081337A940CED95AF0F9`.

No release test should create a real booking or payment. Live provider checks are read-only; the reversible player-count behavior is exercised against controlled fixtures unless a human explicitly confirms a real temporary hold.

## Public cache

Repository: `https://github.com/Jarryd22/golfhub-perth`

Raw cache root: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache`

Index: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache/index.json`

The release is handed off only after the workflow source is published and the generated cache is verified from the public raw URL.

## Booking and privacy boundaries

GolfHub discovers availability and continues on official booking or visitor-information pages. It does not confirm or purchase tee times. Availability may change after a cache snapshot. Public cache files must never contain tokens, credentials, CAPTCHA responses, temporary-hold state or personal data. Making the repository private later disables anonymous raw cache access unless the generated cache is hosted separately.

