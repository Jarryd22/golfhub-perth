# Independent result and screenshot assessment

Reviewed the exact-baseline and repaired probe JSON, new regression metadata, baseline empty-state images and repaired Araluen, Wembley and worker-error screenshots at 1280×800 logical pixels.

The baseline message-less failure is presented as **0 matching times**, one successful availability feed and no course card. The repair presents **Availability incomplete**, a scoped warning, the failed course card and its **OPEN BOOKING PAGE** action. The repaired summary, card metadata, warning text and action fit without overlapping or clipped text in the inspected frames. This exercises the existing PR18 presentation; no layout redesign is introduced.

All six repaired probe scenarios have zero callback errors. The three message-less failure paths now carry `TimeoutError` and render incomplete availability. Named failures retain their original messages and presentation; the successful-empty response retains `error=None` and its zero-match state. The identical new regression file passes 9/9 after the repair; exact PR20 has four passing/five failing methods, with ten failed assertions including subtests and no errors/skips.

The new test SHA-256 is `38db58c7899a997440d836d58e83c29a0dcce013b3122b3fbabc5693ca5165e4`. Repaired probe hashes are core `9cf1a68e591357a5493f69e9df5ad7699c39b361e051531b4fda95a6d6c4ee41` and Qt `2b9a9f23efcfa4a25a4cbd9b1ca809149f6da39c34b82fc196e7bd1e607264d5`; the regression runner's `source_sha256` names the latter only. Both metadata files retain the checked-out PR20 parent separately from modified source hashes.

These are synthetic Linux offscreen rendering and fault-injection results, not native Windows/Android, live provider, booking or delivery tests. Probe screenshots retain constructor-default editable controls; submitted synthetic render context is set separately. The current partial-page success path remains covered as compatibility, without asserting complete provider coverage.
