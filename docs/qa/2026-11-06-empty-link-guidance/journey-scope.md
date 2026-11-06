# Independent journey and source review — 6 November 2026

The focused change is supported by a configured-course reproduction on exact
PR25 `0d09ee3dbbb16b8a2a53851b532e6e59b7c16269`: a successful Araluen row with
two spots is excluded by a submitted four-player filter. No course action is
rendered, but the empty-state sentence promises official links below. A
successful empty Araluen result has the same contradiction. With Altone Park
also selected, one official link really is rendered and the sentence is true.

## Before and after

The [original probe](probe.py) is unchanged between sources (SHA256
`10c78239bd3e14d3fc337c58e7d11bf0f824c11f6eab33030fe1d3a48d9a4c9d`).
Its [baseline JSON](before/probe.json), [baseline log](before/probe.log), four
images and [hash manifest](before/before-manifest.json) are preserved. The
[after JSON](after/probe.json) and [after log](after-probe.log) record one run on
final source SHA256
`f6e948cfe9460e861365e8bca23d48102843bd30c12bb513e2c725370bdb39e6`.

| Synthetic configured journey | Exact PR25 | Final source |
| --- | --- | --- |
| Araluen row excluded by four-player filter | Link sentence, zero result actions | Sentence omitted; zero actions unchanged |
| Araluen successful empty response | Link sentence, zero result actions | Sentence omitted; zero actions unchanged |
| Araluen row excluded, Altone also selected | Link sentence and one Altone VIEW COURSE action | Both preserved |
| Araluen row matches one-player filter | One exact row, OPEN BOOKING PAGE and BOOK, no empty sentence | Preserved |

All four final cases match expectations with zero callback errors. The probe
uses real `cache_finished`/`render_snapshot`, real selected controls and row
filtering, synthetic successful payloads for configured sites, and no provider
fetch. Actions are inspected as widgets; browser/navigation is blocked.

Before and after images were visually inspected at 980×640. The integrated
empty-state guidance fits and stops promising nonexistent actions. In the mixed
case, the summary shows one official link and the real DirectCourseCard is below
the initial viewport, requiring scrolling; its existence is established by the
widget tree, not by a claimed visible button in that top screenshot. No layout
or scrolling change is part of this repair. The unchanged probe supports compact
size only; no new ordinary-size/device screenshot is claimed.

## Additional final-source diagnostics

The two prior diagnostic scripts were copied byte-for-byte. Their
[hashes](diagnostic-script-hashes.json) preserve provenance. `journeys.py` derives
its root from its dated-directory location and has no CLI; it was kept at the
same depth. `startup-decisions.py` received explicit `--root` and `--output`.
Each final diagnostic process had a 60-second bound with retained logs, completed
once with exit 0, and records the same final source hash.

- **50/50 filter combinations passed** in [JSON](journeys.json) and
  [log](journeys.log): 9/18 holes × Any/1–4 players × five time presets, actual
  source-widget submission, a partial three-date fixture, loaded-day counts and
  missing-date labels. Worker launch is intercepted. The expanded unavailable
  date note fits in the inspected [compact image](compact-980x640.png).
- **5/5 startup decisions passed** in [JSON](startup/startup-decisions.json) and
  [log](startup-decisions.log): no saved data, saved empty/error data, single-date
  live fallback and multi-date missing-cache handling. Scheduling/live work is
  intercepted; this is not actual network startup or native worker evidence.
- **9/9 separate secondary-input checks passed on unchanged PR25**, not final
  code: [JSON](secondary-input/probe.json) and [log](secondary-input/probe.log).
  Right/middle clicks leave actual calendar/course selections unchanged and
  emit no selection signals; left-button controls toggle once. No new justified
  input defect was found. Prior keyboard/date repairs were reviewed for overlap.

The [diagnostic summary](diagnostic-summary.json) keeps these scenario counts
separate from root's seven new regressions and aggregate suite. All final
diagnostics have zero callback errors. Source hashes remained unchanged during
the filter/startup runs.

## Source inspection

The [AST and byte comparison](journey-source-scope.json) finds only
`GolfHub.render_results` changed; 50 other GolfHub methods and both worker classes
are identical to exact PR25. The same `direct_results` list controls the new
sentence suffix and the existing later card block. Row filtering, actions,
counts, provider/error/calendar precedence, persistence and lifecycle behavior
remain unchanged. Core/provider, course-result/cache and booking files, all
three production workflows, alert ZIP and its manifest are byte-identical. The
archive was compared as bytes, never extracted, imported or executed.

PR16 missing-date wording, PR18 provider-error wording, PR23 missing-cache static
links and PR24/25 terminal recovery/action eligibility cover different paths.
The preserved loose source has this same unconditional suffix; root's separate
all-ref audit establishes broader branch/PR overlap. No canonical freshness,
subset-cache or date-punctuation repair is duplicated.

## Limits and retained history

The executor initially returned pending process/read handles. The single
baseline probe completed successfully and was not restarted. One artifact read
before completion returned FileNotFound; a later read after confirmed exit 0
found all outputs. A dated-directory listing before copying evidence reported
that the target did not yet exist. These were inspection timing/setup outcomes,
not application failures or repeated uncertain writes. Original probe logs,
offscreen/font warnings and baseline findings remain preserved. Root's separate
test-fixture history belongs in the final run report.

All checks are Linux Qt offscreen source-widget work with isolated temporary
runtime paths, blocked socket/DNS/browser/provider access and no actual scan or
cache worker. No Windows/Android device, native worker timing, live provider
availability, live booking/hold, notification delivery, screen reader, touch,
DPI/resume or updater validation was performed. No new denied/uncertain external
action occurred. The denied production workflow-history route was not queried
or rerouted. Historical Windows `cache_close` and canonical reconciliation
remain unresolved; no native lifecycle investigation or timeout relaxation was
performed here.
