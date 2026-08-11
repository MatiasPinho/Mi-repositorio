# Pipeline: explicar

**Mode:** `EXPLAIN`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/examples.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/writing/explain.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
1. Resolve the requested concept to exactly one canonical concept and owning stable `unit_id`. With Study MCP, call `study_list_units(course)` and inspect `study_get_unit_context(course, unit)` for candidate units; otherwise inspect unit-scoped `conocimiento/concepts.json`. Match only exact normalized concept `id`, registry key, `name` or explicit aliases when present. Never fuzzy-resolve. Zero matches means concept not found; multiple matches require disambiguation.
2. If the owning unit has no canonical concepts, stop with **NEEDS_INGESTION**. If orchestration is available, `procesar` may run first only as a separate prerequisite action and `explicar` must then restart resolution; never create concepts from raw sources inside this action.
3. Explain the resolved concept and only its explicit prerequisites from canonical knowledge. Use its observed topic as orientation when helpful, without expanding the answer into unrelated concepts from the same topic.
4. Use a minimal example, contrasts and a relevant figure/diagram when that representation genuinely improves comprehension. If outside knowledge would materially improve comprehension, label it as external.
5. Apply Humanizer to substantial prose and then verify academic fidelity.
