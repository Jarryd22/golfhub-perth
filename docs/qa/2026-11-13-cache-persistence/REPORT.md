# Keep valid shared data when local saving fails — 13 November 2026 (Perth)

Exact PR29 discards an already downloaded and validated shared-cache payload
when saving its local copy raises `OSError`. The caller receives `None` and
falls back to a previous saved result, an unnecessary single-date live request,
or multi-date unavailable/partial results. Controlled file-error injection
reproduces these outcomes; no production disk failure or incidence rate is
claimed.

The repair catches `OSError` only around `save_local_snapshot` and returns the
validated payload for immediate use. Download/JSON/validation handling, atomic
temp-file replacement, workers, UI, filters, booking, retries and workflows are
unchanged. Results still say **SHARED CACHE**, not saved. Fresh data is not
guaranteed available after restart/offline when saving failed; this does not
repair the filesystem or change permissions. Existing replace failures may
leave a `.tmp` file, as before.

## Baseline, inspection and scope

- Baseline PR29: `8dff803ebc6e61b1a309d7c17c5277909392f5d2`.
  Repair branch: `fix/desktop-cache-persistence-20261113`, stacked on unchanged
  `fix/desktop-cache-completion-20261112`. The original dirty checkout and all
  prior worktrees remain preserved.
- [Repository audit](context-audit.json): 33 branches, 27 drafts #3–29 and zero
  non-PR issues inspected. Main remains
  `25de15b65af6f9dcad4a4d13788fb87ab976df31`. Both update repositories still have
  README-only main trees and public Windows 5.1.17 / Android 0.1.19 releases.
  Metadata inspection is not updater/device verification.
- [Duplicate check](persistence-duplicate-audit.json): one identical
  `fetch_shared_snapshot` AST across 31 current source refs and 16 known local
  sources. No competing repair found. This is separate from PR19's validation,
  PR29's executor completion and pending canonical freshness/subset-cache work.
  Applicable instruction and .agents/skills searches found none.
- [Workflow audit](workflow-trigger-audit.json): all five workflows remain
  unchanged. Existing desktop/cache CI selects the changed test files on normal
  repair push/PR events; no production workflow chain or manual dispatch.
- Complementary result, booking and input inspection found existing repair
  coverage rather than another justified new change. No redesign was added.

## Before/after evidence

| Scenario | Exact PR29 | Repair |
| --- | --- | --- |
| Valid download, local directory/write/replace raises | Returns None | Returns validated shared payload |
| Four-player search; previous saved row has two spots, new row has four | Falls back to “0 matching times” | Displays one matching shared-cache time |
| No saved single-date data; saving new download fails | Requests live fallback | Displays shared data without live fallback |
| Two dates downloaded, only one previous local file | Zero matches across one loaded day in regression fixture | Two matching times across two days |
| Old saved file during write/replace failure | Old bytes remain intact | Same old bytes remain intact |
| Malformed payload or transport failure | Existing rejection/fallback | Unchanged |

Six added methods use real isolated cache files, mocked download bytes and
injected I/O exceptions. No chmod, actual disk exhaustion, provider request or
security change occurs. Their identical final files on exact PR29 give:

- Cache module: **14 methods, ten pass/four new fail**.
- UI startup module: **seven methods, five pass/two new fail**, three assertion
  records including saved/missing subcases.
- Combined: **21 methods, 15 pass/six fail, seven failure records**, no errors or
  skips. The repaired source passes **21/21** on its first executions.

Evidence: [cache baseline](regression/baseline-cache.json),
[cache failures](regression/baseline-cache.log),
[UI baseline](regression/baseline-ui.json), [UI failures](regression/baseline-ui.log),
[cache after](regression/after-cache.json), [UI after](regression/after-ui.json).

The independent [nine-case UI probe](journey-scope.md) shows all four save-failure
cases preserving new ten-am/four-spot results and submitted context; five
normal-save, invalid-response and transport controls are unchanged. It also
verifies older saved bytes remain intact. These diagnostics are separate from
unit-test totals. Settled compact screenshots were inspected for truthful
source/age, result and loaded-date labels, not installed-device appearance.

## Final checks and provenance

**330/330 aggregate tests pass = 198 desktop CI-selected + 95 cache/integrity +
37 additional**, in 28 isolated module processes; zero failures/errors/skips.
The aggregate passed first run. It rechecks prior date/calendar, 9/18-hole,
group/time, selection/count, grid, booking-context, cache/error/offline and
live-recovery repairs, plus safe alert-bundle integrity. The original 11-method
lifecycle module runs once, with unchanged bounds and assertions.

Separate final diagnostics: **50 filter combinations, five startup decisions
and eight inert PR29 completion cases pass**, with no callback errors. No
repeat of the historical Windows timeout investigation or real-QThread timing
probe was undertaken for this persistence change.

[Aggregate/per-module logs](validation/summary.json), [runner](run-focused.py),
[static checks](static-checks.json), [independent review](review.md),
[review metadata](review-metadata.json). Compile, CRLF-aware whitespace and
actionlint 1.7.12 pass. Existing tests/fixtures remain unchanged; six are added.

Changed cache SHA256:
`9a42d4156486c7000a61492d9041e11c1a68c5c84b3634037f6f600a2f90459f`.
Unchanged Qt source SHA256:
`09b17e1a6a89a164d96ed6fc82413d0fa9f64d37244736b225a1150a12736ca1`.
Regression hashes identify identical before/after test files. Precommit
evidence names parent HEAD plus these source hashes. The published draft records
the final commit, remote verification, merge-tree equality and all exact-head
workflow events/attempts through terminal outcomes.

## Publication sample, history and limitations

A single [Nov13/18 payload](published-sample.json) was pinned to
`a8223e7b3b7e9dc7f9de97eb2557996e34aef84e`, observed **08:21:15 Perth**.
Commit/index time was 08:17:48; payload generation 08:17:10 (4m05 old). It has
37 course records and 86 cached rows, zero truthy provider errors/stale flags;
weather is **33 null/unavailable and four objects**, with no defined false-zero
signature in those four. The cause of unavailable weather was not established.
This is not a whole-cache health finding or weather-accuracy verification.
Nominal source cron is ten-minute opportunities at UTC minutes
7/17/27/37/47/57, not proof of actual cadence, trigger origin or per-course age.
No repeated hourly watch or duplicate weather/Wembley/Quick18 repair occurred.

Expected baseline failures remain retained. The first diagnostic run used an
old-cache timestamp in 2032 while the actual clock is 2026, so its age label
was unsuitable evidence. That script, log and images are preserved under
`initial-age-fixture/`; only the fixture timestamp was changed to actual now
minus one day and the baseline rerun before unchanged after replay. This is
not a product-age fix. Candidate regression/aggregate executions passed first
attempt. Original Qt/fontconfig warnings remain in logs; assertions and callback
checks pass. Earlier failed executions remain in their dated reports.

The [historical Windows cache_close timeout](../2026-10-21-midnight/ci-followup/REPORT.md)
remains unresolved: 76 passes/one timeout, despite later green checks and 40
Linux non-reproductions. PR29's separate completion repair is preserved; neither
it nor this persistence change diagnoses a native shutdown hang. Canonical
desktop/mobile/runtime source reconciliation remains pending.

Not performed: installed/native Windows or Android, actual disk/permission
failure, real provider/outage/booking/hold, native screen-reader/touch/DPI/resume,
updater/signature, or notification runtime/delivery tests. Hosted Windows
offscreen CI is source testing; offline alert-bundle checks never run its worker.
No merge, deploy, release, production dispatch, security/credential change,
spend, outreach or live booking/notification occurred.

## Access limits

An optional read-only `rg --files` archive/source-name search including `/tmp`
was **denied** at `/tmp/codex-daemon-1000` (OS permission denied, rg exit 2).
That directory was not opened, retried or accessed through another route.
All 31 known current source refs and 16 known local sources were compared;
only optional exhaustive temporary-archive discovery remains incomplete. This
does not block the selected repair. Initial instruction lookup also found a
nonexistent checkout `.agents` directory; that lookup miss is not a test failure.

The previously denied production-history endpoint
`actions/workflows/refresh-cache-10min.yml/runs?per_page=5` remains unavailable
under the connector allow-list (HTTP 400 INVALID_ARGUMENT), with no retry or
bypass. Bounded published-file and source-schedule reads completed independently.
