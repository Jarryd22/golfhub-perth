# GolfHub v5 public-cache operation

Repository: `https://github.com/Jarryd22/golfhub-perth`

Raw cache root: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache`

Index: `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/cache/public/cache/index.json`

## Operation

- `.github/workflows/refresh-cache-10min.yml` listens for completion of **Check preferred-date alerts** on `main`. That workflow already receives an external `workflow_dispatch` roughly every ten minutes. Its completion triggers a cache check regardless of success, failure or cancellation; notification-test runs can also trigger a cache check. The cache workflow does not dispatch the alert checker, consume its artifacts, or alter notification behavior.
- The existing cron `7,17,27,37,47,57 * * * *` remains a best-effort fallback, alongside manual dispatch and source-change pushes. No new credentials, scheduler setup or token permissions are required.
- Automatic triggers skip provider fetching only when the prior index covers the current 28 Perth dates, all 56 snapshot files exist, and its timestamp is under five minutes old. This coalesces nearby cron/heartbeat events. Missing, invalid, future-dated or incomplete cache data triggers a refresh. Manual and source-change runs always refresh; the shared concurrency group prevents overlapping publishers.
- One prepare job anchors a single Perth calendar date, fetches one shared forecast per course within a 90-second network budget, and attempts to export the previous cache snapshot for transient fallback.
- Seven parallel jobs refresh four anchored calendar days each: offsets 0, 4, 8, 12, 16, 20 and 24.
- A strict publisher accepts only 28 dates with complete 18-hole and 9-hole files: 56 date/round snapshots in total, with valid schemas, expected course counts and a strict live-provider majority.
- Isolated provider failures reuse the prior same-course result with stale metadata; widespread outages cannot replace a healthy snapshot.
- The generated snapshot is force-published as one fresh orphan root commit with up to three attempts on the dedicated `cache` branch. Main source history therefore does not accumulate 144 cache commits per day.
- The desktop app reads the cache anonymously and saves successful snapshots under `%LOCALAPPDATA%\GolfHub`.
- GolfHub v5 can combine up to 28 individually selected cached dates, including nonconsecutive dates, in one request. Results remain grouped by date and courses are ordered A-Z within each date.

GitHub scheduled workflows are best-effort and can start later than the nominal ten-minute mark. The app displays cache age; cache availability is a fast discovery view and the official course or booking page remains the final source of truth.

### Weather isolation and bounded transport recovery

The October 3 weather outage exhausted the five-minute prepare job, so every tee-time shard was skipped despite weather being optional. Weather now runs in a child process with a 90-second deadline. Completed forecasts are checkpointed atomically; if the worker times out or fails, the parent retains completed weather and supplies empty entries for unavailable locations. All shards preload those entries, so they make no additional weather requests. The prepare summary and Actions warning expose incomplete weather. The next heartbeat provides the next attempt; there is no production retry sweep of empty forecasts (which can be rate-limit responses).

The October 4 Quick18 timeout/reset incidents persisted as stale fallback results across publications. Quick18 already has one immediate transport retry in the shared fetcher. The cache shard now permits a separate, delayed recovery attempt after the initial batch, restricted to recognized Quick18 timeout/reset failures. Attempts run serially, at most once per domain and at most three times across the entire four-day shard. Each recovery fetch can use the existing immediate retry, so this adds at most six HTTP requests per shard. HTTP errors (including 429), certificate failures, parser errors and mixed failure messages do not qualify. These limits deliberately leave some failed results for the next heartbeat instead of retrying every date and round.

Recovery is not guaranteed. The strict fresh-provider majority is still evaluated before stale fallback substitution; prior `stale_since` timestamps and the current failure reason remain visible when recovery fails or its budget is exhausted. Neither the index timestamp nor a successful workflow means all course results are fresh.

Branch CI exercises a real hung weather process, retained checkpoints, malformed/failed weather preparation, negative caching in shards, transient retry limits and exclusions, repeated stale timestamps, and the existing publication gates. After an approved merge, check weather summaries and successive publications, including per-course stale metadata. Revert only the resilience change if needed; keep the existing heartbeat and cron cadence fix. This repair does not release an Android or Windows update or change booking/notification behavior.

### Freshness and activation verification

The prepare-job summary records the trigger, upstream alert run and prior complete-cache age, with an Actions warning above 20 minutes. The publish-job summary is written only after the cache push succeeds and records the commit, index `generated_at` and 28-date/56-snapshot coverage. A duplicate skip is explicitly labelled; a green run alone does not prove a new publication. An index timestamp describes the published batch, not every provider result: inspect `health.stale_fallbacks` and per-course `stale_since` for reused results.

The October 2 investigation found successful cache runs taking about two minutes but scheduled starts hours apart, while externally dispatched alert runs were ten minutes apart. This is consistent with GitHub's documented schedule delays/drops, but the exact cause was not proven. See [GitHub's event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) and [workflow_run behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run).

Activation requires an approved merge of the fix to `main`: GitHub only enables `workflow_run` listeners from the default branch. The workflow-file change also starts one normal refresh through the existing push trigger. Do not dispatch the alert checker merely to test this change; wait for its existing external schedule. Branch CI runs offline tests and workflow lint only; it does not publish cache data or send notifications.

After activation, observe at least **three successive heartbeat-driven publications** (two intervals, approximately 20–30 minutes):

1. In Actions, pair each completed `main` alert run with a cache run whose event is `workflow_run`; check the linked heartbeat and freshness decision in the prepare summary. A close cron publication may cause an intentional duplicate skip.
2. For each publication, record the run URL, published commit and advancing `generated_at`. Verify the commit against `gh api repos/Jarryd22/golfhub-perth/commits/cache --jq .sha`. Expected publication intervals are approximately ten minutes, allowing runner duration/queue variation. Investigate any cache age over 20 minutes, even if the alert checker is green.
3. Fetch the index and first/last dates' `18.json` and `9.json` from the raw cache root above. Check the current Perth 28-day window, timestamps and stale-fallback metadata. The publisher's strict validation must still pass all 56 snapshots. If raw branch URLs lag because of CDN caching, compare `https://raw.githubusercontent.com/Jarryd22/golfhub-perth/<published-commit>/public/cache/index.json` to distinguish publication from anonymous-client visibility.

If no cache run follows a heartbeat, check the exact alert workflow name, `main` branch, upstream event and default-branch listener. If both heartbeat and cron stop, no workflow can emit its own warning; the published index age is still the evidence of staleness. This change improves triggering but does not promise an exact delivery time or add an independent monitoring service.

Cadence rollback (PR #1 only): reverting the heartbeat change restores the previous cron/manual refresh behavior. This is separate from reverting the resilience repair; keep the heartbeat for a resilience-only rollback. Do not disable the alert checker or change its external scheduler.

## Wembley rendered-calendar collection

The Linux refresh workflow installs the optional pinned `requirements-browser.txt` and Playwright Chromium in the three shards that overlap Wembley's ten-day booking window. Only a successful installation enables `GOLFHUB_WEMBLEY_BROWSER=1`. Other shards and desktop live checks keep the calendar path. Installation has a three-minute step limit; failure leaves browser collection disabled so other providers can refresh.

After the public calendar advertises availability, the collector opens that same dated calendar and clicks the matching course/date cell. The official page may complete its own silent check. GolfHub reads rendered tee-time rows only after verifying the requested date, product and resource; it never extracts/replays a CAPTCHA response, handles an interactive challenge, selects a booking cell, logs a rendered URL or saves full browser HTML. Published row links are rebuilt from configured date/product/resource values.

Each browser collection has a 45-second browser budget with bounded descendant cleanup, at most two product calendar loads and two availability clicks, and no retries. A challenge, denial, timeout, browser failure or unexpected page stops the remaining products and later browser attempts in that shard invocation. A new invocation can try again. Full and unreleased calendar results do not start Chromium. The initial calendar HTTP read retains its separate 25-second socket timeout and remains one per date/round as before; browser traffic is additional and bounded by the available products within the release window.

Results include `wembley_collection` (`complete`, `partial`, or `calendar_only`), completed product IDs, per-product calendar status and a fixed `wembley_stop_reason` when needed. Partial results retain successfully read rows with a desktop notice. If no exact rows can be read, the current product-level calendar result remains authoritative and cannot be replaced with stale exact rows. **Available** still means the calendar advertises bookings; it is not proof of exact row coverage or zero times.

Short/full month headings and the 6 am Perth release boundary are covered by deterministic tests. An official “No rows meeting selected criteria” response with no products before release is **unreleased**. Missing configured products or the requested date within the open window remains **unknown**, with no historical substitution. A present product can still advertise its own availability; partial product lists cannot establish that the whole round is full.

Offline browser tests intercept every request with local fixtures and exercise normal navigation, row parsing, challenge/denial stops and safe output. A previous ordinary cloud-browser visit displayed Old 18-hole times for October 8, 2026 without an interactive challenge, but that does not establish unattended reliability. This development environment's outbound proxy denies Wembley before reaching the provider, so the new collector has not been validated live here. After an approved merge, inspect naturally scheduled publications for exact rows across Old/Tuart and 9/18 holes, collection coverage, stop reasons and clean handoff URLs before calling production recovery confirmed.

Other isolated Wembley lookup failures can reuse a prior good result for at most **30 minutes** (roughly three scheduled cache intervals), retaining its original `stale_since` and the latest failure reason. Repeated publications and Perth midnight do not renew that age; missing, invalid, timezone-free or future source timestamps disable reuse. Once expired, the current error remains visible rather than claiming old availability. Fresh weather and the current official handoff remain attached to the attempt. This limit is Wembley-specific; other providers and the strict fresh-provider majority gate are unchanged.

## Booking-assist separation

Player-count assistance is desktop-only and never runs in the cache workflow. After an explicit choice, a supported exact MiClub row may create a reversible temporary hold and open player details. The app fails closed on ambiguous or changed pages, attempts to release only its selected cells when the user closes without continuing, and keeps the page open if release cannot be verified. If the user continues to checkout manually, GolfHub does not alter that provider state. No hold state, cell identifier, personal information, login, checkout, payment or CAPTCHA action enters the GitHub cache.

## Privacy

The public `cache` branch contains public course availability, official booking or visitor-information URLs and public weather only. It must not contain credentials, tokens, CAPTCHA responses, temporary-hold state or personal booking information.

If the repository is made private, anonymous `raw.githubusercontent.com` access to the cache branch also stops. To keep source private while retaining instant shared caching, move this same history-free cache publication to a separate public repository or static host and update `data/cache_config.json` to the new raw base URL.

## Manual refresh and release verification

Open the **Actions** tab, select **Refresh four-week tee-time cache**, then select **Run workflow**. After publishing succeeds, verify `index.json` plus dated `18.json` and `9.json` snapshots below the raw cache root above.

For a v5 release, record the successful workflow conclusion and run URL/ID, fresh `generated_at`, exactly 28 indexed dates and 56 valid snapshots, Maylands and Joondalup exact-row spot checks, Wembley exact/calendar coverage with clean URLs and no CAPTCHA token, desktop cold-start from the public cache, and the exact final installer size and SHA-256.

