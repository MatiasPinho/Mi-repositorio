# Pipeline: repaso

**Mode:** `REVIEW`

## READ
Load the shared lifecycle first:
- `pipelines/_shared/semantic-document-lifecycle.md`

Then load only these review-specific shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/pedagogy/learning-principles.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/visual/active-reading.md`
- `rules/writing/review.md`
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/visual-rubric.md`
- `rules/evaluation/quality-gates.md`
- `contracts/handoffs.md`

## SHARED LIFECYCLE
Execute `pipelines/_shared/semantic-document-lifecycle.md` exactly. The steps below specialize that lifecycle for rapid review. They do not replace or weaken any shared review, gate, publication, environment or failure requirement.

## Pipeline-specific RUN specialization
1. **SCOPE + PREREQUISITE** → resolve course + scope to exactly one stable `unit_id`; rapid-review scope is unit-only. If Study MCP is connected, call `study_get_unit_context(course, scope)` once and `study_list_artifacts(course)`; otherwise read only `unidades/<unit-id>/` plus explicit cross-unit prerequisites and use `artifact_state.py status`. Refuse an unresolved/global pedagogical scope. Apply the shared **NEEDS_INGESTION** boundary before starting a run. Run `python scripts/venv_exec.py study.py figures migrate <course>` once to normalize legacy figure metadata.
2. **START RUN** → `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline repaso --scope "<scope>"`. The run records deterministic fingerprints of the study engine and canonical academic/concept/topic/figure inputs. Apply the shared active-run isolation rules.
3. **PLAN** → write `02-plan.json`. Use canonical knowledge, not raw transcript prose, to decide the high-yield mental model, ordering, traps, contrasts and omissions. Use observed topics as a flexible coverage audit so an entire thematic block is not silently dropped, but do not give every topic equal space or infer a fixed section count. Prioritize what is worth retrieving in a 5–10 minute review. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; for every selected visual record the treatment and provenance required by the plan visual contract. Select only figures that add instructional value.
4. **DRAFT** → write `03-draft.md` from the plan and canonical knowledge. The document must remain compact and retrieval-oriented while standing alone for a student who already learned the content. Use semantic callouts and local figure assets only where they accelerate recall.
5. **REVIEW** → in addition to the shared independent review contract, evaluate the candidate against canonical state, observed-topic coverage, figure registry/assets and all required rubrics. Write the review using `contracts/handoffs.md`.
6. **REGISTER DERIVED FIGURES** → after an accepted candidate exists, register newly derived figures through `study_register_derived_figure` when MCP is connected or `python scripts/venv_exec.py study.py figures register-derived` otherwise, always passing `visual_treatment`; `preserve+derived_sketch` also requires `source_figure_id`. Never edit `figures.json` directly.
7. **RENDER CANDIDATE** → render the shared accepted Markdown with `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered.html --kind rapid-review --course "<course-display-name>" --scope "<scope>" --check`.
8. **INTEGRITY GATE** → run `study_validate_artifact` when Study MCP is connected or `python scripts/venv_exec.py scripts/artifact_integrity.py --type rapid-review` otherwise; persist `<run-dir>/10-integrity.json` and apply the shared no-publish-until-pass rule.
9. **BROWSER VISUAL GATE** → run `python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit` and apply every shared browser-visual requirement.
10. **ATOMIC PUBLISH** → resolve `<publish-dir>` as `unidades/<unit-id>/resumenes`, then after all shared gates pass run `python scripts/venv_exec.py scripts/publish_artifact.py --markdown <accepted-md> --html <run-dir>/09-rendered.html --dest-markdown <publish-dir>/_source/<scope>-repaso.md --dest-html <publish-dir>/<scope>-repaso.html --report <run-dir>/11-publication.json`. Apply the shared immutability/hash rules.
11. **MARK** → mark the published artifact with MCP or `python scripts/venv_exec.py scripts/artifact_state.py`.
12. **FINISH** → `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. In addition to the shared finish contract, repaso finish rejects missing/corrupt publication evidence, engine mutations and changes to the canonical academic/concept/topic/figure fingerprints captured at start.
