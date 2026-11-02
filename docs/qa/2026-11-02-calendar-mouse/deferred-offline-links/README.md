# Confirmed, deferred: direct-course links disappear when all dates lack cache

On exact PR21 `9aa16f733458db871c2452a18a247536ab348498`, select **Altone Park** and three dates. With no shared snapshots and an empty isolated local cache, `cache_finished` displays the accurate unavailable state but provides **zero official course links**. Altone Park's static configured URL is already known. Supplying one valid empty snapshot makes that same URL and **VIEW COURSE** card appear.

The five-scenario probe also verifies mixed selection: **Araluen + Altone Park + Boddington Golf Club** produces zero direct-course cards when all dates lack snapshots, compared with two deduplicated direct-course cards when one empty snapshot is loaded. Integrated-only selection has no configured direct-course links and retains the existing unavailable state. No callback errors occurred.

The reproduction uses actual configured sites, actual `cache_finished` and a real empty temporary local-cache directory. Shared-cache maps are synthetic. Socket, weather and worker access are blocked; browser calls are intercepted. The screenshots were inspected at 1280×800 logical pixels. This is not native Windows/Android or live URL-reachability testing, and no provider, booking, hold or notification action occurred.

The cause is the all-missing multi-date branch bypassing `add_direct_results` and the shared direct-link rendering used for partially loaded searches. PR16's all-missing regression selects an integrated course only and therefore does not cover this link loss. This differs from the pending canonical per-course freshness/subset-preservation work.

**Deferred, not repaired in this pass.** A future focused change should retain the existing unavailable status and retry guidance while exposing only the selected, configured static direct links once per date range. It must not imply checked availability or simply route to the current batch renderer's misleading “0 matching times across 0 loaded days” summary. Preserve submitted course/round context, partial-cache behavior and the single-date live fallback. No application or regression-test source was changed for this exploration.

Original script, JSON, log and PNGs are copied verbatim alongside this note. The JSON records the exact source hash, cases, intercepted URLs and empty local-cache evidence.
