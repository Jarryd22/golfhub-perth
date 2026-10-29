# Provider-error wording — 29 October 2026, Perth

A loaded provider failure was shown as **0 matching times**, and failed multi-date groups said **No matching live times**. Collier's error card additionally said **No public tee times showing**, contradicting its unavailable warning. The focused repair says **Availability incomplete**, identifies affected courses/days, and preserves the official booking handoff. It does not infer that a failed request established no availability.

## Scope and baseline

Branch `fix/desktop-provider-error-wording-20261029` is stacked on unchanged draft [#17](https://github.com/Jarryd22/golfhub-perth/pull/17), `d7da8b8b02f58b319a5db1178a49839ec2a009bd`. [Current context audit](context-audit.json): 21 branches, 15 open drafts #3–17, 19 non-cache/news source refs inspected before selecting this repair. No duplicate provider-error wording repair was found. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`. Both update repositories still have only main and no open PRs; public Windows 5.1.17 and Android 0.1.19 metadata, asset sizes and digests are unchanged. No current binary, manifest signature or installed-updater test was performed.

The saved Linux executor resumed successfully. The original dirty October 22 checkout and completed October 27/28 worktrees are preserved. No applicable AGENTS.md or checkout `.agents/skills` were found. Testing used Python 3.12.14, PySide6/Qt 6.11.2, host UTC, offscreen Qt at default scale 1 and isolated writable runtime directories. This remote desktop source identifies as v5.0; newer desktop/mobile canonical-source reconciliation remains pending.

The application diff adds error-aware summary/status/day wording and wrapped summary warnings, and prevents Collier's empty metadata from overriding an error. Positive exact-time/calendar counts, verified-empty wording, submitted filters, missing-snapshot PR16 behavior, PR17 matching-course counts, links, data fetching, caches, freshness and worker ownership are unchanged. Direct links and unselected results do not count as failed availability feeds. The test-only desktop workflow adds the new module to existing path filters and its module list; production workflows are unchanged.

## Reproduction and repair evidence

[Reusable probe](error-probe.py), [exact-PR17 before JSON](before/probe.json), [repaired JSON](after/probe.json), [before Collier image](before/collier-error.png), [after Collier image](after/collier-error.png). These use synthetic shared/saved data with socket/browser paths blocked, and no worker launch.

| Scenario | Exact PR17 | Repair |
|---|---|---|
| Loaded failed single-date feed | 0 matching times; 0 matching tee times across 0 courses | Availability incomplete; Availability could not be checked for 1 course |
| Two loaded failed dates | 0 matching times across 2 days; No matching live times in each heading | Availability incomplete across 2 days; each heading identifies unavailable courses |
| Failed date plus absent snapshot | Zero matches across 1 loaded day; failed date says no matches | Incomplete across 1 loaded day; absent date still says Availability not checked |
| Collier provider failure | No public tee times showing, plus unavailable warning | Could not read live availability, with official-calendar action preserved |
| Saved-device failed payload | Zero matches despite failed observation | Incomplete, retaining Saved on this device source |
| Valid exact rows or available calendar plus another failed course | Existing positive headline/count | Positive headline/count retained, plus a scoped warning |
| Genuine empty data, including Collier | Existing empty information | Unchanged |

## Validation

| Evidence class | Result |
|---|---|
| **Failed baseline regressions** | Final identical 11-method module on exact PR17: **2 methods pass, 9 fail**, **13 failing assertions including subtests**, zero errors/skips. [Log](new-tests-baseline.log), [metadata](new-tests-baseline.json). The failure number is assertion/subtest count, not failed-method count. Initial baseline/source are also retained before compact assertions were added. |
| **Passed repaired regressions** | **11/11**, including mixed/filtered empty data, positive rows/calendar, saved fallback, missing dates, lazy submitted context, course/day error counts, direct/unselected exclusions, Collier URL interception, and wrapped warning geometry at 980×640. [Log](new-tests-after.log), [metadata](new-tests-after.json). |
| **Passed aggregate** | **213/213 = 106 desktop CI-selected + 70 cache/integrity + 37 additional booking/rendering tests**. [Summary](validation/summary.json), [runner](run-focused.py). Fresh process per module; sockets/browser blocked; booking dialogs mocked. The initial aggregate passed, then the final provider module with added compact assertions passed separately; the other 18 modules and app were unchanged. Both results are retained, not double-counted. |
| **Passed filter matrix** | **50 separate diagnostic scenarios**: 9/18 holes × Any/1–4 players × five time presets; submitted dates, filtered rows and partial-cache state checked. Worker launch intercepted. [JSON](journeys.json), [runner](journeys.py), [log](journeys.log). |
| **Passed startup/fallback decisions** | **5 separate diagnostic scenarios**, using actual startup/callback methods with local data and scheduled/live work mocked: no saved payload, saved empty, saved error, single-date no-cache fallback with submitted context, and multi-date no-cache recovery. [Final JSON](startup-decisions.json), [script](startup-decisions.py). No worker or full network/disk startup ran. |
| **Offscreen visual checks** | Before/after Collier and settled multi-day views inspected at 1280×800; compact recovery/warning geometry checked at 980×640. The initial multi-day capture compressed card content before scroll layout settled. The [three-pass review](review.md) and [settled image](layout-review/multiday-all-error.png) show stable full card geometry on passes two/three; initial image retained. No app layout rewrite. These are source widgets, not installed-client tests. |
| **Static/source review** | Python compile and CRLF-aware whitespace check pass. [actionlint](actionlint.log), [independent diff/layout review](review.md) and [journey scope](journey-scope.md) provide separate evidence. |
| **Not performed** | Native installed Windows/Android, full network/disk cold startup, screen readers, DPI scaling, OS resume, signed updater installation, live provider requests, booking/holds and notification delivery. |

Pre-commit metadata names the checked-out parent separately from changed-file hashes. Tested application SHA-256: `bbe26b95b0c89fa9cede6a7ecbab099bef733c592b544b19ec8d6ef19339847c`; final new-test SHA-256: `31bc15c3eed75ed3aec731652a7bea6383605d7aa1b71c4df9005d2f5a5cf03e`. Exact remote commit, all-event/all-attempt CI and checkout/merge-tree verification are recorded on the draft after publication; these local results do not claim an uncreated commit was checked out.

The standard lifecycle module ran once as part of the aggregate. There was no repeated paired Linux investigation or test relaxation. The repaired regression/aggregate suites have no failed execution. The initial startup diagnostic passed four scenarios and failed one fixture assertion: it assumed January 2 although the default selected date was tomorrow, January 3. [Initial script](startup-decisions-initial.py), [JSON](startup-decisions-initial.json) and [log](startup-decisions-initial.log) are retained. Explicitly selecting January 2 made the intended pending-January-3 context scenario valid; all five passed without app changes. The intentional exact-baseline failures above remain in the evidence. An unconfigured whitespace command reported existing CRLF line endings as trailing whitespace; the CRLF-aware check passes without normalizing the source. Qt unsupported-cursor and font-cache diagnostics in source-widget logs did not cause callback errors or failed assertions.

## Remaining limits and decisions

- **Historical Windows `cache_close` timeout remains unresolved:** PR14 push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438), 76 pass / 1 fail at the unchanged 30-second limit. Later green checks and 40 Linux non-reproductions do not establish a fix or cause. The missing Windows/Python 3.12.10/Qt 6.12.0 exact-source pair and failing-child stack remain **pending/unavailable**, not denied, in this Linux-only executor. [Authoritative follow-up](../2026-10-21-midnight/ci-followup/REPORT.md).
- The older Qt manual-event-pump stall, four WebEngine sandbox-helper blocks, obsolete cron assertion, prior PR15 fixture-write denials, interrupted October 22 usage-limit task, and October 27's corrected matrix-fixture failure remain historical records. They were not reclassified or bypassed. No app/test source was changed to hide failures.
- Weather PR8 and its #4→#6 dependencies remain separate unmerged drafts; this branch does not contain their repair. Current budget/cache tests do not establish complete forecasts or truthful weather age. The parent already reported November 13's natural false-zero recovery at 07:37, 07:47 and 07:56 Perth; this pass did not repeat the watch. Wembley November 7 18-hole TUART18-only available/unreleased variation does not prove Old18 coverage; PR5/7 remain the existing work. Quick18 resilience PR3 is not a Whaleback/MiClub repair.
- Source inspection still finds publication-age rather than per-course stale display and selected-subset snapshot replacement; existing canonical-source reconciliation work must be reviewed before competing changes. Alert tests here validate inert bundle bytes, not runtime execution, delivery or production enforcement. Zero-watch runs do not prove notification delivery.
- Review the cumulative draft chain and reconcile intended desktop/mobile/service sources before integration. Native device QA and delivery tests remain separate work. No redesign or product-direction change was implemented.

No merge, deployment, release publication, production/manual workflow dispatch, credential/security change, spending, third-party contact, live booking, hold or real notification occurred. There was no denied or uncertain write in this pass.
