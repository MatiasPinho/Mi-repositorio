# Pipeline: aprender

**Mode:** `LEARN`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/concept-ordering.md`
- `rules/pedagogy/examples.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/evaluation/academic-fidelity.md`

## RUN
1. Resolve the requested learning target to exactly one canonical **observed topic or concept** and its owning stable `unit_id`. With Study MCP, call `study_list_units(course)` and inspect `study_get_unit_context(course, unit)` only for candidate units; otherwise inspect each unit's `conocimiento/topics.json` and `conocimiento/concepts.json`. Match only exact normalized ids, registry keys, names or explicit aliases. Never fuzzy-resolve. If the same normalized target matches both a topic and a concept, require explicit `tema:<target>` or `concepto:<target>` disambiguation instead of guessing.
2. Require canonical knowledge for the owning unit. If its concept registry is empty, stop with **NEEDS_INGESTION**. If orchestration is available, `procesar` may run first only as a separate prerequisite action and `aprender` must then restart from step 1. Never edit canonical knowledge inside the learning action itself.
3. If the target is a **topic**, load that topic's `concept_ids` plus only explicit prerequisite records from earlier units. Do not silently teach neighboring topics merely because they are in the same unit.
4. If the target is a **concept**, load that concept plus only its explicit prerequisites. Use its observed topic as orientation when helpful, but do not expand the answer into unrelated concepts. This is the canonical replacement for the former public `explicar` action.
5. Teach progressively: mental model → simple explanation → relevant diagram/figure when it materially helps → example/contrast → precise course formulation → active recall/application. For a single concept, keep the scope compact unless the user explicitly asks for a broader lesson.
6. Record meaningful progress in the owning unit. Use Humanizer for substantial explanatory prose, then perform a fidelity check. Do not pre-generate a large static document unless requested.
