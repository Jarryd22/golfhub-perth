# GolfHub v5 public-cache operation

Repository: `https://github.com/Jarryd22/golfhub-perth`

Raw cache root: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache`

Index: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache/index.json`

## Operation

- `.github/workflows/refresh-cache-10min.yml` uses the nominal cron `*/10 * * * *` and supports manual dispatch. GitHub scheduled workflows are best-effort, so runs can start later than ten minutes.
- One prepare job anchors a single Perth calendar date, fetches one shared forecast per course with transient retry, and attempts to export the previous cache snapshot for transient fallback.
- Seven parallel jobs refresh four anchored calendar days each: offsets 0, 4, 8, 12, 16, 20 and 24.
- A strict publisher accepts only 28 dates with complete 18-hole and 9-hole files: 56 date/round snapshots in total, with valid schemas, expected course counts and a strict live-provider majority.
- Isolated provider failures reuse the prior same-course result with stale metadata; widespread outages cannot replace a healthy snapshot.
- The generated snapshot is force-published as one fresh orphan root commit with up to three attempts on the dedicated `cache` branch. Main source history therefore does not accumulate 144 cache commits per day.
- The desktop app reads the cache anonymously and saves successful snapshots under `%LOCALAPPDATA%\GolfHub`.
- GolfHub v5 can combine up to 28 individually selected cached dates, including nonconsecutive dates, in one request. Results remain grouped by date and courses are ordered A-Z within each date.

GitHub scheduled workflows are best-effort and can start later than the nominal ten-minute mark. The app displays cache age; cache availability is a fast discovery view and the official course or booking page remains the final source of truth.

## Wembley protected-calendar behavior

Wembley's official public calendar exposes safe product-level Old/Tuart **Available**, **Full** or **Not released** status. **Available** does not mean the workflow obtained exact tee-time rows. Current individual rows require an interactive CAPTCHA/browser check, so the unattended workflow stores only product-level status and a dated official handoff. It never solves, stores, replays or publishes a CAPTCHA response or token.

This is an expected protected-calendar result, not a provider failure or proof of zero exact times. The desktop app labels it as product-level availability and provides **View Wembley times** for the user to complete the check and inspect exact current rows.

## Booking-assist separation

Player-count assistance is desktop-only and never runs in the cache workflow. After an explicit choice, a supported exact MiClub row may create a reversible temporary hold and open player details. The app fails closed on ambiguous or changed pages, attempts to release only its selected cells when the user closes without continuing, and keeps the page open if release cannot be verified. If the user continues to checkout manually, GolfHub does not alter that provider state. No hold state, cell identifier, personal information, login, checkout, payment or CAPTCHA action enters the GitHub cache.

## Privacy

The public `cache` branch contains public course availability, official booking or visitor-information URLs and public weather only. It must not contain credentials, tokens, CAPTCHA responses, temporary-hold state or personal booking information.

If the repository is made private, anonymous `raw.githubusercontent.com` access to the cache branch also stops. To keep source private while retaining instant shared caching, move this same history-free cache publication to a separate public repository or static host and update `data/cache_config.json` to the new raw base URL.

## Manual refresh and release verification

Open the **Actions** tab, select **Refresh four-week tee-time cache**, then select **Run workflow**. After publishing succeeds, verify `index.json` plus dated `18.json` and `9.json` snapshots below the raw cache root above.

For a v5 release, record the successful workflow conclusion and run URL/ID, fresh `generated_at`, exactly 28 indexed dates and 56 valid snapshots, Maylands and Joondalup exact-row spot checks, Wembley protected availability without a CAPTCHA token, desktop cold-start from the public cache, and the exact final installer size and SHA-256.

