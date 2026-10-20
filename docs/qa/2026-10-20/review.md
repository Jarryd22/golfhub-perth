# Independent review — 20 October 2026

No blocking defect found in the application, regression-test and test-workflow diff against PR #11. Reviewed the edited render/click paths and their callers, not only the new helper. Exact file hashes reviewed are recorded in [review-probe.json](review-probe.json).

## Context and behavior

- Single-day action names receive the submitted `self.context` date at render time; subsequently changing the date picker does not rename displayed results. Lazy multi-day sections capture each `day["date"]` in the builder default argument, avoiding the late-bound loop-variable/last-day mistake.
- Names distinguish course, tee time and round and include a date when one is known. Missing or invalid dates are omitted. Deduplicated direct links in a multi-day search do not invent a single date.
- The final action text is used after the Collier empty-state override. Wembley, error, direct-course and standard booking actions preserve their existing destinations. Show-all/show-first names update with the visible action.
- Visible booking-button text and signal connections are unchanged. Independent synthetic click checks confirm the identical result and row objects reach the handler and nested input data remains unchanged. A malformed optional date does not mutate the result or crash card construction.
- Start and End time labels have buddies and real Qt accessibility Label relationships. The updated inherited test checks those relationships and the explicit property, respecting Unix Qt's combo Name behavior rather than weakening it to an unchecked assertion.
- Only the read-only desktop test workflow gains paths/module coverage. No production workflow, cache/parser/service/update code, credentials or notification path changes are included in the reviewed implementation.

## Verification

Independently reran **8 booking-context tests and 5 time-range tests: 13 passed** on Python 3.12 / PySide6 6.12.0, Linux offscreen, in isolated `LOCALAPPDATA` directories. These repeat the branch tests and must not be added again to the main unique-test count. An initial invocation with the default Python could not import PySide6; switching to the existing `/tmp/golfhub-qa-venv` resolved that environment mismatch. No package or security-setting change was made.

An additional socket-blocked/intercepted geometry and identity probe passed. At 980×640, Start time and End time are visible, entirely within the window and 91 pixels wide versus measured text widths of 58 and 50 pixels. Visual inspection of [the compact screenshot](review-compact.png) confirms readable labels and reachable primary search actions. Existing broken date punctuation remains visible and is outside this change. Result contents scroll as before. Probe browser calls: zero.

Limits: source/offscreen checks only. Native Windows accessibility, real screen-reader announcements, high-DPI rendering, installed application behavior and Android/device delivery were not tested. Fontconfig cache and existing stylesheet `cursor` warnings occurred during Linux offscreen runs; both processes exited successfully. Final remote commit and hosted CI remain for the primary agent to verify.
