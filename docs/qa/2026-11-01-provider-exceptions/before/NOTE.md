# Provider exception baseline evidence

The original probe, JSON, log and PNGs were copied verbatim from `/workspace/scratch/golfhub-20261101-gaps`. They identify exact PR20 and source hashes. Actual core error paths receive mocked `TimeoutError()` or a named timeout, then feed result data to real offscreen widgets. The synchronous `ScanWorker.run` case uses a Python executor with a patched fetch; no Qt worker launch or provider call occurs. Six scenarios complete with no callback errors.

Araluen, Wembley and worker escape catches turn a message-less exception into `error=""`, producing a false successful-empty heading and no error card. Named errors remain incomplete; a genuinely successful empty response has `error=None`. These are synthetic fault-injection reproductions, not evidence of a current production incident. The screenshot search controls remain at their constructor defaults; the explicitly submitted synthetic context is recorded in the probe and chosen independently for rendering.

The new regression module also preserves the current partial-page behavior: if one page fails but another supplies rows, those rows remain successful. This guard does not establish complete provider coverage or endorse the completeness of partial results.
