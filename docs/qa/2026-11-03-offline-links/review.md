# Independent review — offline official course links

No blocking findings in the reviewed source, regression module or desktop test workflow. The change resolves the previously recorded all-missing-cache omission while retaining the unavailable-cache warning and existing range-level link presentation. This review covers the uncommitted repair on PR22 `bddf4ff537c4e2e5d6d18ab061fa6011cba5430d`; the reviewed file hashes are recorded in `review-metadata.json`. A later commit/remote CI result must be verified separately by the parent task.

## Source and scope inspection

- Only `GolfHub.cache_finished` and `render_multi_results` change among existing methods. The new `_append_direct_course_links` method contains the existing multiday direct-link block unchanged; an AST comparison confirms equality. No single-date renderer, calendar, filtering, worker, cache format or provider implementation changes.
- The all-missing branch runs after the existing submitted-context restoration and pending-request/closing guards. `add_direct_results([])` selects configured direct courses from that submitted context, and calls `direct_result` without a date. Source inspection confirms this avoids weather/provider access and produces static official URLs rather than asserting checked availability.
- Clearing once, rendering the warning with `clear=False`, appending links and then adding one stretch keeps layout order consistent. Updating `last_results` and clearing `day_sections` removes stale display state when a prior successful range is replaced. Repeated completions do not accumulate old cards.
- The unavailable header, status and retry guidance remain unchanged. There is no zero-loaded-day matching-times summary or fabricated day section. Integrated-only selections stay unavailable without direct links. Single-date misses retain the existing live fallback. Partially loaded ranges use the extracted block with their existing cached URLs and notes.
- Desktop CI adds only the regression module to its two path filters and isolated-module list. The alerts, cache refresh, course news and cache-test workflow files are unchanged against PR22; no production trigger or permissions change appears in the diff. Source inspection of existing trigger scopes remains distinct from executing any workflow.

## Regression and offscreen evidence reviewed

The reviewer read the final ten-method regression module and the saved execution records; the reviewer did not duplicate runtime test execution. The tests exercise configured courses and real empty temporary local-cache reads, block workers/network/weather, intercept browser launches, and assert callback cleanup. Coverage includes selected static links once per range, mixed/integrated-only searches, 28 dates, 9/18-hole eligibility, submitted context versus changed controls, replacement of stale results, repeated completion, accessible course/round actions, partial snapshots with preserved URLs/notes, and unchanged single-date fallback.

The identical test module on exact PR22 has **3 passed and 7 failing methods**, with **8 failed assertion/subtest records**, zero errors and zero skips. The repaired source has **10/10 passing methods**. The final aggregate record contains **276 tests in 24 isolated module invocations**, all passing with zero errors/skips. These are Linux/offscreen source results, not native Windows or Android results.

The saved five-case before/after probe changes direct-card counts from **0/0/0/1/2 to 1/2/0/1/2** for direct-only all-missing, mixed all-missing, integrated-only all-missing, direct-only one-loaded and mixed one-loaded respectively. Both probe records contain zero callback errors. The reviewer visually inspected the 1280×800 all-missing before/after screenshots: the cache warning remains, and the configured Altone Park action is now present beneath it.

The reviewer also inspected the 980×640 scrolled screenshot and keyboard diagnostic metadata. The action buttons are visible and have course/round accessible names; actual Tab/Space events reached both actions and recorded the two expected intercepted URLs. The initial successful compact frame is preserved separately; its lower card portions were outside the scroll viewport. Later screenshot framing exposes the whole cards. This is not an additional unit-test count or a repaired execution failure. The logs retain existing Fontconfig/Qt stylesheet warnings.

## Limits and outstanding work

No native Windows/Android UI, real browser navigation, live booking/hold, provider request, notification delivery, updater/signature, native screen reader or DPI/device test was performed by this review. Static links do not establish availability, connectivity or a successful booking. The historical Windows `cache_close` timeout remains unresolved; it was not re-investigated in Linux and no tests were relaxed. Canonical desktop/mobile source reconciliation remains pending. Remote branch and exact-head CI verification remain the parent task's responsibility.

No source/test/workflow modifications were made by the reviewer. Reviewer static checks passed: CRLF-aware `git diff --check`, exact extracted-block AST comparison, reviewed-file hashes and unchanged production workflow comparison. No denied or uncertain action occurred during this review.
