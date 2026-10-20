# Controlled asynchronous smoke comparison — 20 October 2026

The same crash is reproduced on the clean PR #11 baseline and repair head. Both first alternating runs spontaneously exited with SIGSEGV; no timeout or forced termination was involved. The comparison stopped after this matching pair, within the maximum of three runs per tree.

| Source | Exact commit | Outcome | Elapsed | Python main-thread frame |
|---|---|---|---|---|
| Clean PR #11 base | `6d60354a90d7a32807a3f7867cb9180d449433ce` | SIGSEGV (`-11`) | 0.640 s | `app/qt_golfhub_app.py:1561`, `cache_thread_done` |
| Clean repair head | `93d4763451358be608bff06fd0013936af36764c` | SIGSEGV (`-11`) | 0.702 s | `app/qt_golfhub_app.py:1587`, `cache_thread_done` |

Both frames point to `self.cache_thread = None`. Both traces then show the identical harness at `search:136`, `main:140`, and module entry `265`; the crashing worker thread has no Python frame. The normalized `cache_thread_done` source is identical, SHA-256 `40d9c588250382ca5246a44d03228f5b64a3ee05368a815eb9dca0619624c2be`. The direct reproduction on the baseline is the evidence that this crash predates the repair; identical function text alone would not establish that.

The harness is an unchanged copy of `docs/qa/2026-10-20/journey-smoke.py` at repair commit `93d4763451358be608bff06fd0013936af36764c`, SHA-256 `e420a7930133b12c43454a426e11f4e271689b3cae353080674bdd2f3f2ee103`. Both runs used its same fixed path, the same phase, Python 3.12.14, PySide6/Qt 6.12.0, offscreen rendering, and a 25-second timeout. Neither synchronous-cache delivery nor wrapper retention was enabled. Dedicated application, font-cache and temporary directories were reset before each run. Both detached worktrees were clean before and after; the harness hash stayed unchanged.

Exact commands, run from `/tmp/golfhub-crash-comparison-20261020`:

```text
/tmp/golfhub-qa-venv/bin/python -X faulthandler /tmp/golfhub-crash-comparison-20261020/journey-smoke.py --root /tmp/golfhub-crash-comparison-20261020/base --output /tmp/golfhub-crash-comparison-20261020/base-1 --phase strict-crash-comparison-20261020
/tmp/golfhub-qa-venv/bin/python -X faulthandler /tmp/golfhub-crash-comparison-20261020/journey-smoke.py --root /tmp/golfhub-crash-comparison-20261020/head --output /tmp/golfhub-crash-comparison-20261020/head-1 --phase strict-crash-comparison-20261020
```

Common explicit environment: `QT_QPA_PLATFORM=offscreen`, `PYTHONHASHSEED=0`, `PYTHONUNBUFFERED=1`, and `TMP`, `TEMP`, `TMPDIR` all `/tmp/golfhub-crash-comparison-20261020/process-temp`. `DISPLAY`, `WAYLAND_DISPLAY`, `QTWEBENGINE_CHROMIUM_FLAGS` and `QTWEBENGINE_DISABLE_SANDBOX` were unset. The harness set the same isolated `LOCALAPPDATA` and `XDG_CACHE_HOME` paths for both runs. Sockets were blocked and booking opens intercepted by the unchanged harness; no provider, weather or booking network action occurred.

This pair establishes **baseline presence of the observed asynchronous offscreen crash**. It does not establish an unchanged crash rate, the underlying native cause, or Windows/Android device impact. The final asynchronous journey remains blocked; synchronous fixture results remain separate. No app, tests, workflow or repository evidence files changed during this comparison.

Evidence: `comparison.json` records full commands, environment, source/test hashes, clean status, stacks and function mappings; `base-1/process.log` and `head-1/process.log` retain complete output. `run-comparison.py` is the bounded alternating runner.
