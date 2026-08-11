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
- `rules/ingestion/topics.md`
- `rules/ingestion/figures.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
1. Resolve the course deterministically (`study.py course list` only if needed).
2. If Study MCP is connected, call `study_material_changes(course)` and `study_get_course_context(course)` once; otherwise use `python scripts/venv_exec.py study.py materials scan <course> --json` and the canonical files. Work only on new/changed sources plus the minimum existing context needed for integration.
3. Run `python scripts/venv_exec.py study.py figures preflight <course> --json`. If it reports `READY` and changed sources include PDFs, run `python scripts/venv_exec.py study.py figures scan <course> --write --json`. If it reports `DISABLED`, continue textual ingestion without attempting the scanner again.
4. Run `python scripts/venv_exec.py scripts/claim_candidates.py scan --course <course> --write`. This deterministically registers high-signal transcript/PDF evidence under `academico/academic.json -> claim_candidates` with exact page/timestamp references. `semantic_ready` means only that a candidate has a parseable shape; it does **not** mean the claim is true.
5. Interpret the changed sources and review pending claim candidates from those sources. Mark each reviewed candidate `accepted` or `rejected` with a short `review_notes`. For an accepted candidate, create/update the corresponding structured entry in `academico/academic.json -> claims`, using the candidate `evidence_ref` as provenance and correcting its hints/source type when context requires it. Never promote `teacher_transcript` to `teacher_explicit` merely because the wording sounds certain, and never create `supersedes` from a raw transcript change cue.
6. Update course-wide `academico/academic.json`/`contexto.md`, then write each unit's concepts, figures and evidence links only below `unidades/<unit-id>/`. Every unit-scoped record must carry the same stable `unit_id` as its directory. Do not create a mixed root `conocimiento/` registry.
7. After updating a unit's `concepts.json`, semantically group its concepts into observed topics. A PDF/slide heading is evidence, never an automatic topic boundary. Reconcile through `python scripts/venv_exec.py study.py topics reconcile <course> --unit <unit-id> --input <proposal.json> --write`; reuse an existing topic `id` when the semantic group persists. Any concept not defensibly grouped must remain explicit in `unassigned_concept_ids`. Keep `declared_matches` separate from, and restricted to, that unit's `academic.json -> units[].topics` values.
8. Run `python scripts/venv_exec.py study.py topics validate <course> --unit <unit-id>` for every changed unit. Unknown concept references, duplicate primary assignments and implicit/unrecorded unassigned concepts block ingestion.
9. If claims changed, run `python scripts/venv_exec.py scripts/semantic_claims.py course --course materias/<resolved-course-slug> --write`. Preserve `split-view` and `unresolved` results; do not silently reconcile them. Unresolved contradictions that affect generated artifacts must remain visible to the academic review gate.
10. Sync concepts to progress.
11. Run academic/structural audit and `python scripts/venv_exec.py study.py validate <course>`.
12. Use `study_list_artifacts(course)` when MCP is connected, otherwise `python scripts/venv_exec.py study.py artifacts <course>`, so stale derived files are visible.
13. Commit source hashes only after successful ingestion.

## Environment contract
Dependency-bearing commands must run through `scripts/venv_exec.py`, which re-executes them with this repository's `.venv`. If `.venv` is missing, stop and require the setup flow instead of falling back to global Python.

**Forbidden:** generating/regenerating summary, guide, rapid review, question bank or mock exam.
