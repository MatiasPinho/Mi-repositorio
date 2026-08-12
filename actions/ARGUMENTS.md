# Shared action argument resolution

1. Use an explicitly supplied course slug/name.
2. If omitted and exactly one real course exists (excluding `_plantilla`), use it.
3. Reuse immediate unambiguous course context when available.
4. Otherwise run `python study.py course list` and ask only for the missing course.
5. Unit-scoped actions must resolve exactly one stable `unit_id` before semantic work. Do not treat a topic name as a unit alias.
6. `aprender` accepts either one observed topic or one canonical concept. Resolve exact normalized id/name/alias values across both registries; if the same target matches both, require explicit `tema:<target>` or `concepto:<target>` disambiguation. Never fuzzy-pick.
7. `resumen` accepts optional explicit detailed/guide intent. Absence of that wording means standard depth; detailed intent changes explanatory depth, never academic scope.
8. Assessment actions use registered assessment records and never infer unknown exam scope from convention.

Use deterministic CLI/MCP for administration and canonical context. Missing canonical knowledge is `NEEDS_INGESTION`; ingestion is a separate `procesar` prerequisite, never an implicit mutation inside another active semantic run.

`guia` and `explicar` are legacy intents routed internally to `resumen` and `aprender`; they are not public commands. `auditar` is maintenance-only.
