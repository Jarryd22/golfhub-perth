# Independent review

Reviewed the application diff, eight new regression tests, and test-only workflow selection against #10. The reviewer found that adding a label buddy interprets a literal ampersand as a mnemonic. The repair escapes course-label ampersands and checks every course label through QAccessible. Review also suggested completing the round cycle; the test now covers 18→9→18.

Final independent run: all eight regressions pass on Linux offscreen, PySide6 6.12.0. No remaining code/test blocker. The existing Unix ComboBox assertion mismatch and native/device limits remain recorded in REPORT.md. The reviewer made no app edits.

[Independent test log](review-course-controls.log)
