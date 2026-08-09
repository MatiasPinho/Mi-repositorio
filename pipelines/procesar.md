# Pipeline: procesar

**Mode:** `INGEST`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/academic/assessments.md`
- `rules/ingestion/material-processing.md`
- `rules/ingestion/transcripts.md`
- `rules/ingestion/concept-graph.md`
- `rules/ingestion/figures.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
1. Resolve the course deterministically (`study.py course list` only if needed).
2. If Study MCP is connected, call `study_material_changes(course)` and `study_get_course_context(course)` once; otherwise use `python study.py materials scan <course> --json` and the canonical files. Work only on new/changed sources plus the minimum existing context needed for integration.
3. Run `python study.py figures preflight <course> --json`. If it reports `READY` and changed sources include PDFs, run `python study.py figures scan <course> --write --json`. If it reports `DISABLED`, continue textual ingestion without attempting the scanner again.
4. Interpret sources, including pedagogically meaningful figures, and update `academico/academic.json`, `contexto.md`, `conocimiento/concepts.json` and evidence links. Every unit-scoped concept/figure should carry stable `unit_id` (for example `unidad-1`) in addition to any human-readable unit label.
5. Sync concepts to progress.
6. Run academic/structural audit and `python study.py validate <course>`.
7. Use `study_list_artifacts(course)` when MCP is connected, otherwise `python study.py artifacts <course>`, so stale derived files are visible.
8. Commit source hashes only after successful ingestion.

**Forbidden:** generating/regenerating summary, guide, rapid review, question bank or mock exam.
