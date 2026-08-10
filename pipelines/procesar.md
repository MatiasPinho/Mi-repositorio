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
4. Run `python scripts/claim_candidates.py scan --course <course> --write`. This deterministically registers high-signal transcript/PDF evidence under `academico/academic.json -> claim_candidates` with exact page/timestamp references. `semantic_ready` means only that a candidate has a parseable shape; it does **not** mean the claim is true.
5. Interpret the changed sources and review pending claim candidates from those sources. Mark each reviewed candidate `accepted` or `rejected` with a short `review_notes`. For an accepted candidate, create/update the corresponding structured entry in `academico/academic.json -> claims`, using the candidate `evidence_ref` as provenance and correcting its hints/source type when context requires it. Never promote `teacher_transcript` to `teacher_explicit` merely because the wording sounds certain, and never create `supersedes` from a raw transcript change cue.
6. Update `academico/academic.json`, `contexto.md`, `conocimiento/concepts.json` and evidence links. Every unit-scoped concept/figure should carry stable `unit_id` (for example `unidad-1`) in addition to any human-readable unit label.
7. If claims changed, run `python scripts/semantic_claims.py course --course materias/<resolved-course-slug> --write`. Preserve `split-view` and `unresolved` results; do not silently reconcile them. Unresolved contradictions that affect generated artifacts must remain visible to the academic review gate.
8. Sync concepts to progress.
9. Run academic/structural audit and `python study.py validate <course>`.
10. Use `study_list_artifacts(course)` when MCP is connected, otherwise `python study.py artifacts <course>`, so stale derived files are visible.
11. Commit source hashes only after successful ingestion.

**Forbidden:** generating/regenerating summary, guide, rapid review, question bank or mock exam.
