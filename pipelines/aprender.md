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
1. Resolve the requested topic to exactly one observed topic and owning stable `unit_id`. With Study MCP, call `study_list_units(course)` and inspect `study_get_unit_context(course, unit)` only for candidate units; otherwise inspect each unit's `conocimiento/topics.json`. Match only an exact normalized topic `id`, `name` or `aliases` value. Never fuzzy-resolve. Zero matches means topic not found; multiple matches are ambiguous and require the unit/topic to be disambiguated.
2. Require canonical knowledge for the owning unit. If its concept registry is empty, stop with **NEEDS_INGESTION**. If the caller requested the final learning action and orchestration is available, `procesar` may be executed first as a separate prerequisite action, then `aprender` must restart from step 1. Never edit canonical knowledge inside the learning action itself.
3. Load the resolved topic's `concept_ids` plus only explicit prerequisite records from earlier units. Do not silently teach neighboring topics merely because they are in the same unit.
4. Teach progressively: mental model → simple explanation → relevant diagram/figure when it materially helps → example → precise course formulation → active recall/application.
5. Record meaningful progress in the owning unit. Use Humanizer for substantial explanatory prose, then perform a fidelity check. Do not pre-generate a large static guide unless requested.
