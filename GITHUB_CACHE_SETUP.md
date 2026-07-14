# GolfHub public-cache operation

Repository: `https://github.com/Jarryd22/golfhub-perth`

Raw cache root: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/main/public/cache`

## Operation

- `.github/workflows/refresh-cache-10min.yml` runs on `*/10 * * * *` and supports manual dispatch.
- Seven parallel jobs refresh four Perth calendar days each: offsets 0, 4, 8, 12, 16, 20 and 24.
- The publish job merges the shards, removes expired dates, builds `public/cache/index.json`, and commits 18-hole and 9-hole snapshots.
- Snapshot timestamps let the desktop app show cache age.
- The desktop app reads the cache anonymously and saves successful snapshots under `%LOCALAPPDATA%\GolfHub`.

GitHub scheduled workflows are best-effort. A run can start later than the nominal ten-minute mark when GitHub is busy. Cache availability is a fast discovery view; the official booking page remains the final source of truth.

## Privacy

The repository and every committed cache file are publicly visible and clonable. Do not commit credentials, tokens or personal information. The generated cache contains public course availability, public booking URLs and public weather data only.

If this repository is changed to private, anonymous `raw.githubusercontent.com` access stops and the shared cache will no longer load in GolfHub. The app will fall back to its local cache and live course checks. To keep the source private while retaining instant shared caching, publish only `public/cache` from a separate public repository or static host.

## Manual refresh

Open the **Actions** tab, select **Refresh four-week tee-time cache**, then select **Run workflow**. After the publish job succeeds, verify `public/cache/index.json` and a dated `18.json` or `9.json` file.
