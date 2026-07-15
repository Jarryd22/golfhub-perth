# GolfHub public-cache operation

Repository: `https://github.com/Jarryd22/golfhub-perth`

Raw cache root: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache`

## Operation

- `.github/workflows/refresh-cache-10min.yml` runs on `*/10 * * * *` and supports manual dispatch.
- One prepare job anchors a single Perth calendar date, fetches one shared forecast per course with transient retry, and attempts to export the previous cache snapshot for transient fallback.
- Seven parallel jobs refresh four anchored calendar days each: offsets 0, 4, 8, 12, 16, 20 and 24.
- A strict publisher accepts only 28 dates with complete 18-hole and 9-hole files, valid schemas, the current 37 eligible entries for each round, expected course counts, and a strict live-provider majority.
- Isolated provider failures reuse the prior same-course result with stale metadata; widespread outages cannot replace a healthy snapshot.
- The generated snapshot is force-published as one fresh orphan root commit with up to three attempts on the dedicated `cache` branch. Main source history therefore does not accumulate 144 cache commits per day.
- The desktop app reads the cache anonymously and saves successful snapshots under `%LOCALAPPDATA%\GolfHub`.

GitHub scheduled workflows are best-effort and can start later than the nominal ten-minute mark. Cache availability is a fast discovery view; the official course or booking page remains the final source of truth.

## Privacy

The public `cache` branch contains public course availability, official booking or visitor-information URLs and weather only. It must not contain credentials, tokens or personal booking information.

If the repository is made private, anonymous `raw.githubusercontent.com` access to the cache branch also stops. To keep source private while retaining instant shared caching, move this same history-free cache publication to a separate public repository or static host.

## Manual refresh

Open the **Actions** tab, select **Refresh four-week tee-time cache**, then select **Run workflow**. After publishing succeeds, verify `index.json` and a dated `18.json` or `9.json` below the raw cache root above.