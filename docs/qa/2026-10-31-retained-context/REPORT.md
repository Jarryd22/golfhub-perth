# Retained search context — 31 October 2026, Perth

Starting a new live refresh keeps the previous result cards visible but replaces the context they read. On exact PR19, an old **one-player** BOOK button then builds a **four-player** plan for the old date, including after refresh failure/cancellation. Expanding an old date also applies the new player/time filters, so a heading promising **1 time** can show **no matching times**. Rendered booking handlers and lazy date builders now retain a copy of their original context; the active request keeps its new context.

## Scope and prior work

Branch `fix/desktop-retained-search-context-20261031` is stacked on unchanged draft [#19](https://github.com/Jarryd22/golfhub-perth/pull/19), `ba1faeae0dc9cf3314e8dc884f79b13e2520d22c`. The [current audit](context-audit.json) checked 23 branches, 17 open drafts #3–19, no other open issues, and both update repositories before selection. All 21 non-data source refs and the preserved loose checkout had the same uncaptured booking/filter context. PR12 captures date labels, PR13 manages lifecycle and PR14 handles Perth midnight; none repairs replacement of context during a later live search. Main remains `25de15b65af6f9dcad4a4d13788fb87ab976df31`. Windows 5.1.17 and Android 0.1.19 update metadata/branches are unchanged; no new signature or installed-update test.

The saved authorized Linux executor resumed successfully. Original October 22 dirty work and completed later worktrees are preserved. No AGENTS.md or checkout `.agents/skills` instructions were found. Local tests used Python 3.12.14, PySide6/Qt 6.11.2, host UTC, isolated writable directories and offscreen scale 1. The remote desktop identifies as v5.0; newer desktop/mobile canonical-source reconciliation remains pending.

The focused repair binds a copied render context to booking handlers and captures it for lazy filtering. Optional keyword context preserves existing direct helper callers; explicit Any-player context does not fall back to a later numeric selection. The consumed filter values are scalars. Active search state, new-result rendering/saving, result/row/URL identity, direct course actions, booking consent/hold guards, cache validation, provider calls, weather, worker ownership and production workflows remain unchanged. An existing keyboard handoff test now additionally asserts the captured context. The new module joins the existing test-only desktop workflow; no assertion or timeout is weakened.

## Before and after

[Exact-PR19 booking JSON](before/booking-context-probe.json), [repaired booking JSON](after/booking-context-probe.json), [baseline lazy JSON](before/lazy-context-probe.json), [repaired lazy JSON](after/lazy-context-probe.json). Probes use actual source-widget actions, synthetic data and inert thread/worker substitutes. Pure booking plans are intercepted and cancelled; sockets, browser and real booking dialogs are blocked. No provider page, temporary hold or notification is exercised.

| Journey | Exact PR19 | Repair |
|---|---|---|
| Display Jan 2 / 1-player result; submit Jan 5 / 4-player live search; click retained BOOK | Plan asks for 4 players on Jan 2 | Plan retains 1 player on Jan 2; active request remains Jan 5/4 |
| Same old BOOK after failed/cancelled refresh | Still asks for 4 players | Still retains 1 player; cache save not invoked |
| Old Any-player result followed by new numeric selection, or vice versa | Uses the new selection's handoff mode | Keeps displayed result's original handoff mode |
| Expand old Jan 3 date with 9am/2 spots after a new 4-player Afternoon search | Heading says1 time; body says no matches | Heading and actual 9am/2-spot row agree, with original booking date/group |
| Successful new live results | New context used | New context still used for rendering, booking and saved snapshot |
| Unsubmitted control changes or direct helper calls | Existing behavior | Preserved |

[Before lazy screenshot](before/retained-lazy-context.png) and [after screenshot](after/retained-lazy-context-scrolled.png) were inspected at 1280×800. Additional settled/scrolled evidence is retained with the probes. Initial one-pass after layout compressed card labels; extra event passes settle the scroll geometry, as in the earlier October 29 diagnostic. Initial evidence is preserved; no layout rewrite was made. Today's [980×640 recovery view](compact-980x640.png) was also inspected.

## Verification

| Evidence class | Result |
|---|---|
| **Failed exact-baseline regressions** | Identical final new module on exact PR19: **3 pass / 7 fail**, zero errors/skips. [Log](new-tests-baseline.log), [metadata](new-tests-baseline.json). |
| **Passed repaired regressions** | **10/10**: live pending/failure/cancel, Any↔numeric group changes, lazy and already-built multi-date cards, successful new results/save, pending controls and direct helper compatibility. [Log](new-tests-after.log), [metadata](new-tests-after.json). |
| **Passed aggregate** | **238/238 = 121 desktop CI-selected + 80 cache/integrity + 37 additional booking/rendering**, zero failures/errors/skips. Fresh processes per module with sockets/browser blocked. [Summary](validation/summary.json), [runner](run-focused.py). PR16–19, date/midnight/keyboard/filter controls, booking guards, cache recovery and inert alert-bundle integrity are revalidated. |
| **Passed separate diagnostics** | **50 filter scenarios** across 9/18 holes, Any/1–4 players and five presets; worker launch intercepted. [JSON](journeys.json). **5 startup/fallback decision scenarios**, loader/scheduled work mocked. [JSON](startup-decisions.json). Pre-change exploration separately passed **16 course-control scenarios** on PR19, with no new course-picker defect. [Evidence](before/course-controls/probe.json). These are not additional unit tests. |
| **Static/source review** | Python compile, CRLF-aware whitespace, checksum-verified actionlint 1.7.12 and [independent review](review.md) pass. [Metadata](review-metadata.json), [journey/design scope](journey-scope.md). Current source/update metadata audit is inspection, not device validation. |
| **Not performed** | Installed/native Windows/Android, real provider/shared-network recovery, OS resume, screen readers/DPI, updater/signatures, live booking/holds, alert worker execution and notification delivery. |

Tested app SHA-256 `47e7a530a528816894e19ed3524c2c6bbab5830d0c27bf07f1eb169ab502a428`; new test SHA-256 `088d129c4b9dc998304a3d125d687fee83a4b3f6b9212889e80a8e64c7e33143`. Local pre-commit metadata identifies the checked-out PR19 parent separately from changed-file hashes, not an uncreated commit. Final remote head, all CI events/attempts and checkout/merge-tree equality are recorded on the draft after publication.

## Clarity, accessibility, speed and limits

The confirmed improvement makes retained result actions and expanded rows agree with their displayed date/count. Existing accessible date/course/round names, keyboard handoff and lazy rendering are retained and tested. Source inspection shows no eager build of collapsed days, additional worker launch or network request. This is not a measured native performance improvement or user-feedback study. Onboarding copy, stale-source clarity and a visible submitted-filter summary remain the existing review recommendations; no redesign, monetization or product-direction change was implemented.

- Today's intentional baseline failures are retained. Repaired new/aggregate tests have no failed execution; there was no fixture-date correction or manual CI rerun. The transient one-pass screenshot is preserved rather than represented as a persistent layout defect.
- **Historical Windows `cache_close` remains unresolved:** PR14 push [39524383636](https://github.com/Jarryd22/golfhub-perth/actions/runs/39524383636/job/118975503438), 76 pass/1 fail at the unchanged 30-second timeout. Later green checks and 40 Linux non-reproductions do not prove cause or repair. Exact-source Windows pairing and failing-child stack remain **pending/unavailable** in this Linux executor, not denied. Only the normal lifecycle module ran once; no repeated paired Linux diagnosis or relaxed tests. [Authoritative history](../2026-10-21-midnight/ci-followup/REPORT.md).
- Older Qt manual-event-pump stalls, WebEngine sandbox-helper blocks, obsolete cron assertion, prior fixture-write denials, interrupted October 22 work and subsequent fixture/tooling failures remain in their dated reports. No access denial or sandbox was bypassed.
- Parent monitoring already reported Quick18 recovery at 07:07 and 07:17 Perth, known Wembley classification issues and November 15 false-zero weather. This pass did not repeat the health watch or access providers. PR3 is Quick18-specific; PR5/7 and PR8 with #4→#6 remain existing unmerged work. Passing workflows do not prove live booking availability or forecast validity.
- Canonical desktop/mobile/service source, per-course freshness/subset integration and native-device QA remain pending. Alert tests here validate inert ZIP/manifest bytes; zero-watch executions do not verify worker behavior or delivery. Current public release behavior is not changed by this draft.

No merge, deployment, release publication, production/manual workflow dispatch, credential/security change, spending, third-party contact, live booking/hold or real notification occurred. No denied or uncertain write remains.
