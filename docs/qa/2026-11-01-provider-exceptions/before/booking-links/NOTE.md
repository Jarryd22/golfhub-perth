# Independent booking-link exploration

Exact PR20 `63c910556c4f4dc210e41c3e6db665845436a8f0` passed 153 synthetic offscreen checks, with zero callback errors: 148 configured weekday/weekend card handoffs across 41 courses (72 direct, 66 MiClub and 10 Quick18), two supported-round selection guards and three row-link precedence/fallback/missing-link explanation checks.

The probe builds results from current configuration and synthetic responses, exercises source-widget actions, and records intercepted browser arguments. Sockets, browser effects and workers are blocked; no provider destination, booking availability, transaction, hold, notification or native device was tested. These are diagnostic scenarios, not 153 additional unit tests.

No reachable missing-link defect was found through these configured paths. A fabricated incomplete course-result dictionary can leave a course button with no URL, but this alone does not justify changing supported result construction. The absent exact-row URL path already explains the missing booking link. No application or test source was edited during this independent exploration.
