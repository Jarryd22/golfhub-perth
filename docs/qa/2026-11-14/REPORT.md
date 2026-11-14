# Daily QA and integration checkpoint — 14 November 2026 (Perth)

No new application repair was justified by this pass. Existing drafts and
preserved local work cover the confirmed candidates; canonical desktop/mobile
source integration remains the consequential blocker. This documentation-only
follow-up depends on unchanged [PR30](https://github.com/Jarryd22/golfhub-perth/pull/30),
commit `a3e522b5e2d79856f994fb342a7c6b1253a1143d`. It changes no application,
tests, workflows or existing PRs. It is not a release or installed-device sign-off.

## Inspection and fresh execution

The original main checkout stayed clean at `25de15b65af6f9dcad4a4d13788fb87ab976df31`;
tests used a separate clean checkout of exact PR30. The newer dirty desktop/mobile
checkout was unavailable and untouched. No applicable AGENTS.md or checkout
skills were found. Before documenting, a second remote check at 08:51–08:53 Perth
found 34 branches and 28 unchanged open draft PRs (#3–30), no PR created today and
no November 14 report on the QA stack. Existing cumulative reports were read.

These are **new November 14 executions**, using Linux, Python 3.12.14 and
Qt 6.11.2. [Compact evidence](evidence.json) preserves timestamps, source hashes,
per-module results, diagnostic counts and original-log hashes. Large raw logs,
images and payload copies are omitted from this documentation change.

| Command or diagnostic | Fresh result |
|---|---|
| `python docs/qa/2026-11-13-cache-persistence/run-focused.py --root <exact-PR30-checkout> --output <isolated-evidence>/validation` | **330 passed**, zero failures/errors/skips; 28 isolated processes |
| Existing [journeys.py](../2026-11-13-cache-persistence/journeys.py), byte-identical in an isolated output layout | **50/50 passed**, zero callback errors |
| `python docs/qa/2026-11-13-cache-persistence/startup-decisions.py --root <exact-PR30-checkout> --output <isolated-evidence>/startup` | **5/5 passed**, zero callback errors |
| `python scripts/validate_alerts_runtime.py --archive .github/alerts-runtime.zip --manifest .github/alerts-runtime-manifest.json` | Archive and all **16 members match**; data-only check |

All passed first execution. The aggregate covers dates/midnight, mouse/keyboard
selection, rounds, group/time filters, intercepted booking context/guards,
empty/error/offline states, races, lifecycle and cache completion/persistence.
Its breakdown is 198 desktop CI-selected + 95 cache/integrity + 37 additional
tests. The existing lifecycle module ran once; no repeated Linux diagnosis or
timeout relaxation was performed. Existing Qt warnings remain in original logs.

The 50 diagnostic cases combine 9/18 holes, Any/1–4 players and five time ranges
with synthetic partial cache; workers are intercepted. Five startup cases cover
no saved data, saved empty/error and missing single/multiple dates. Sockets and
browser calls are guarded. These diagnostics do not exercise actual booking or
native worker completion. The alert archive was never extracted or executed.

At 980×640 logical size/scale 1, controls and recovery guidance fit and loaded-day
counts agree with unchecked dates. The documented date-button punctuation issue
remains; its existing local repair awaits integration. Synthetic 2033 timestamps
are not freshness evidence. Static configuration contains 41 unique courses
(21 direct, 17 MiClub, 3 Quick18), 37 eligible for each round; this does not verify
provider availability or geographic completeness.

## Existing CI, separate from today's tests

The following **November 13 runs were reread**, not triggered by this pass.
All events/attempts for tested code head `a3e522b5e2d79856f994fb342a7c6b1253a1143d`
returned these three successes, each attempt 1, with no failed/cancelled runs:

- [Windows push](https://github.com/Jarryd22/golfhub-perth/actions/runs/43337706548): 198 tests, Qt 6.12.0.
- [Windows PR](https://github.com/Jarryd22/golfhub-perth/actions/runs/43337787479): 198 tests, Qt 6.12.0.
- [Linux PR](https://github.com/Jarryd22/golfhub-perth/actions/runs/43337785151): 95 tests plus workflow validation.

PR checkout `ef3d078d0c73e6fa3e29f112397f197b16fe9eb0` has the expected base/head
parents and the same tree as PR30. These are source/offscreen tests. A
documentation-only head may have **no exact-head CI** because current path
filters exclude `docs/**`; do not attribute these prior runs to it. Actual
post-publication head/run verification is recorded on the new documentation PR.

## Limited published-cache observation

Observed **00:45:45 UTC / 08:45:45 Perth**, pinned to cache commit
`283141efe555ece6324e29cd1902eece240895d7`, published at **00:37:44 UTC**.
Final saved data matched remote Git blob hashes byte-for-byte.

| Immutable source | Generated timestamp, November 14 UTC | Age at observation |
|---|---|---|
| [Index](https://raw.githubusercontent.com/Jarryd22/golfhub-perth/283141efe555ece6324e29cd1902eece240895d7/public/cache/index.json) | 00:37:43 | **8m02s** |
| [Nov14 / 18 holes](https://raw.githubusercontent.com/Jarryd22/golfhub-perth/283141efe555ece6324e29cd1902eece240895d7/public/cache/2026-11-14/18.json) | 00:27:33 | **18m12s** |
| [Nov29 / 18 holes](https://raw.githubusercontent.com/Jarryd22/golfhub-perth/283141efe555ece6324e29cd1902eece240895d7/public/cache/2026-11-29/18.json) | 00:27:56 | **17m49s** |

The [configured schedule](../../../.github/workflows/refresh-cache-10min.yml)
has UTC minute opportunities 7/17/27/37/47/57; the index specifies ten minutes.
Both sampled generations exceeded that target despite the newer index. This
single observation does **not** establish sustained failure, actual workflow
cadence, per-course age or cause. No course observation timestamps were present.

Each payload had 37 records, all 37 weather values null, no forecast objects and
no stale flags. Nov14 had no course errors; Nov29 retained Wembley:
“Wembley calendar response did not contain the configured booking products”.
The prior Clear/all-zero signature was absent, but unavailable weather does not
prove forecast recovery or freshness. The other 54 payloads were not sampled.
The supplied 08:07 Perth full-cache audit is an earlier, separate observation.
PR8 already covers incomplete-weather false zeros; Wembley work remains in
PR5/7. No duplicate hourly/provider/weather repair was made.

## Remaining priorities and access limits

1. **P1 canonical source:** remote PR30 still declares desktop 5.0; its relationship
   to shipped Windows 5.1.17, Android 0.1.19 and the newer offline source is not
   established. Nominate the intended candidate, make a preserved snapshot
   accessible, then prepare a scoped integration plan for existing fixes,
   including per-course freshness/subset preservation. Do not create competing
   repairs or bulk-copy/release unreviewed source.
2. **P1 Windows lifecycle:** the historical [76-pass/one-timeout cache_close
   failure](../2026-10-21-midnight/ci-followup/REPORT.md) remains unresolved.
   Current passes do not replace same-platform paired evidence and bounded
   child stack/phase capture. Older Qt/WebEngine/cron limitations remain retained.
3. **Versioned native/updater/delivery QA:** installed Windows/Android, native
   screen readers/touch/DPI/resume, real provider/outage/booking behavior,
   updater/signatures and notification delivery were not run. Zero alert
   watches/observations and archive integrity do not establish device delivery.

Both update repositories remain README-only, with no app source/tests or open
PRs. Metadata confirms [Windows 5.1.17](https://github.com/Jarryd22/golfhub-perth-updates/releases/tag/v5.1.17)
and [Android 0.1.19](https://github.com/Jarryd22/golfhub-perth-android-updates/releases/tag/android-v0.1.19).
The [Windows manifest](https://github.com/Jarryd22/golfhub-perth-updates/releases/download/v5.1.17/update.json)
and [Android manifest](https://github.com/Jarryd22/golfhub-perth-android-updates/releases/download/android-v0.1.19/android-update.json)
each returned connector 404/NOT_FOUND, then “Failed to fetch restricted URL”
from web fallback. Retrieval stopped: no claim that public links are broken,
and no manifest-content, signature, downloaded-binary or installed-updater
verification. Windows notes still require confirmation on the affected laptop.

All five workflow trigger definitions were rechecked before publication:
production push paths require main, the alert checker is dispatch-only, and
the cache workflow_run listens to alert completion rather than test CI. A
documentation branch/PR matches neither test path filter nor production trigger.
No workflow files change. The denied production-history endpoint was not retried.
No merge, deployment, release, production dispatch, credential/security change,
booking hold, notification or third-party contact occurred.

Trustworthy availability age, usable saved/offline searches and correct official
handoffs remain the supported usability priorities. Redesign, course-guide
layout and monetization decisions require separate approval.
