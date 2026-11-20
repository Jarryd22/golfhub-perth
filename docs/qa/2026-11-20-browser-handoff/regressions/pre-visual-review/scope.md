# Browser handoff regressions — November 20

Eleven methods are added to CI-selected `tests/test_booking_context.py`, preserving the original eight-method `BookingContextTests` class AST exactly. No workflow, runtime or other test file was changed by the test author. Final test SHA256: `c254663d82f33195ab6593b692f44a9252815e54e76d445240205a933f883a90`.

Eight methods cover the eight external browser call sites: standalone tee, direct-course and result-card buttons; integrated Any-player, invalid-plan fallback, unsupported-provider, manual-choice and dialog-construction-failure fallback BOOK paths. Each method checks `True`, `False`, `OSError` and `webbrowser.Error`, giving **32 subscenarios per source**, not 32 additional unittest methods. Browser dispatch is once to the exact existing destination. Failure feedback must have the initiating card/window parent, title `Could not open browser`, the exact URL and a failure/manual-recovery explanation. True adds no browser-failure warning; existing booking information and dialog-failure warnings are preserved. No helper name or implementation is assumed.

Three further methods check cancel, missing links (four card/integrated subscenarios), and confirmed-plan handoff to a fake dialog. The latter checks pure consent/plan data and mock calls only: no temporary hold, JavaScript or WebEngine runs. Existing booking UI integration tests remain untouched for the parent's aggregate.

## Final identical-file results

- **Exact PR32 baseline:** 19 methods, 11 passed and eight matrix methods failed through **24 assertion records**; zero errors/skips. All eight original methods and three guard methods passed. All eight `True` cases passed. Eight false returns lacked feedback; 16 injected exceptions escaped into captured Qt callbacks.
- **Repair:** 19/19 methods passed, zero failures/errors/skips. All 32 matrix and four missing-link subscenarios passed; cancel and confirmed-plan controls passed separately.
- Baseline source root `/workspace/golfhub-20261119-repair`, commit `66eaf00f76e748cf6f76ef6a758574a3d996360c`, Qt SHA256 `531055544bc6cab4707d29a1293d4356e2852cb1426eb7955029b97c15d1cd35`.
- Candidate source root `/workspace/golfhub-20261120`, same starting HEAD plus uncommitted Qt SHA256 `f6692c7c46bff54027cf12012cc78e045d2381d9fa6f10f64c3f75ffaa05212e`.

The external runner imports the explicit source root and final external test file. It blocks sockets/DNS and browser access, records method/subtest outcomes separately, uses isolated writable runtime directories, and flushes Qt widgets. Each subprocess has the same 60-second outer bound. Commands and hashes are in `provenance.json`; full stdout/stderr and results are in `baseline/` and `repaired/`. Baseline exits 1 for expected assertion failures; repair exits 0. Existing Qt/offscreen stylesheet warnings are retained.

## Preserved initial fixture correction

The first execution on unchanged November 20 PR32 source ran all 32 matrix scenarios and recorded the same 24 product failures, plus three missing-link fixture errors. Repeated/starred `_` unpacking discarded the standalone card's last Python owner before its button was clicked; Qt correctly deleted the button. The one-line test-only correction retains the card owner. Initial file, complete log, result and compressed correction diff remain under `pre-review-missing-card-owner/`. The corrected test was rerun against the separate unchanged PR32 source before evaluating the repair. No assertion, app behavior or bound was relaxed.

These checks execute Qt `QPushButton.click()` signals and capture `sys.excepthook`; they are not native mouse/browser/device tests. Browser calls, modal dialogs and persistence are intercepted; native workers and provider/weather operations are blocked. Natural failure frequency, successful page loading, real bookings, notification delivery, native accessibility and historical Windows `cache_close` remain unverified. The only new code written by this agent is the regression class/imports and this scratch evidence.
