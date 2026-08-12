# Internal compatibility pipeline: explicar

`explicar` is no longer a public action.

Legacy intent that asks to explain one concept must route to `pipelines/aprender.md` with that concept as the learning target. `aprender` now resolves either an observed topic or one canonical concept exactly and applies the appropriate scope.

Do not maintain a separate explanation methodology or public adapter. This wrapper exists only to preserve old references without duplicating behavior.
