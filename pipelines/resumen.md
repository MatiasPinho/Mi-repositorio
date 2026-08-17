# Pipeline: resumen

**Mode:** `SUMMARY`

## READ
Load the shared lifecycle first:
- `pipelines/_shared/semantic-document-lifecycle.md`

Then load only these summary-specific shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/concept-ordering.md`
- `rules/pedagogy/examples.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/visual/active-reading.md`
- `rules/writing/summary.md`
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/pedagogy-rubric.md`
- `rules/evaluation/visual-rubric.md`
- `rules/evaluation/quality-gates.md`
- `contracts/handoffs.md`

## SHARED LIFECYCLE
Execute `pipelines/_shared/semantic-document-lifecycle.md` exactly. The steps below specialize that lifecycle for summaries and add summary-only visual stages. They do not replace or weaken any shared review, gate, publication, environment or failure requirement.

## DEPTH
`resumen` is the single public long-form study-document action.
- Default depth is `standard`.
- Explicit `detallado`, `profundo`, former “guía”, or equivalent wording selects `detailed` while preserving scope and every gate.
- Detailed mode may add useful explanation/examples but cannot invent syllabus scope or become a transcript rewrite.
- Record `depth: "standard"|"detailed"` in `02-plan.json`.
- The published artifact remains the unit's canonical `resumen`; detailed mode changes depth, not the public artifact type.

## Pipeline-specific RUN specialization
1. **SCOPE + PREREQUISITE** → resolve course + scope to exactly one stable `unit_id`; summary scope is unit-only. Apply the shared **NEEDS_INGESTION** boundary before starting. If Study MCP is connected, prefer `study_get_unit_context(course, scope)` / `study_list_artifacts(course)` for canonical context. Run the figure migration command only for legacy metadata normalization; it must not reread sources.

2. **START RUN** → `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline resumen --scope "<scope>"`. The run records deterministic fingerprints of engine and canonical inputs. Figure mutation is allowed only after a reviewed visual finalization.

3. **PLAN** → write `02-plan.json`, including `depth`. Use canonical knowledge to decide ordering, examples, traps and omissions. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; for every selected visual record treatment, reason and provenance. `source-first` selects evidence, not final pixels. `preserve` / `preserve+derived_sketch` require a concrete `fidelity_reason`.

   For a **new derived pedagogical figure**, design a schema-2 scene under `<run-dir>/02-scenes/<id>.json` and reference it with `scene_spec`. The model owns composition/geometry but not SVG/CSS/colors/fonts. Academic elements are declared once and the wide/narrow layouts change geometry only. Do not write polished prose or SVG here.

   Existing schema-1 figures remain supported under `<run-dir>/02-sketches/` for backward compatibility. Their legacy contract still uses `scripts/visual_plan.py`, `figures generate-sketch` and `contracts/sketch-figure.schema.json`; never create normal diagrams with an image-generation model.

4. **VISUAL BUILD** → complete visual work **before drafting**.

   **V2 default for new derived figures:**
   - run `python scripts/venv_exec.py scripts/visual_plan_v2.py preview --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --write <run-dir>/02-visual-preview.json`;
   - stop on deterministic preflight failure and repair the scene; failed attempts remain run-local and do not touch `figures.json`;
   - a separate vision-capable reviewer must inspect every current `wide.png` and `narrow.png` against `rules/evaluation/visual-rubric.md`, then write `<run-dir>/02-visual-review.json` following `contracts/visual-review.schema.json`. The reviewer must be an independent execution/context and explicitly declare `capability: vision`, `independent: true`, `vision_verified: true`;
   - a model without image input cannot PASS. Mechanical metrics are not a substitute for rendered inspection;
   - if review fails, repair and preview again. Maximum three reviewed attempts per scene. The reviewer may require splitting an overloaded visual into multiple derived scenes, with the plan updated before a new current preview is produced;
   - after every current scene passes, run `python scripts/venv_exec.py scripts/visual_plan_v2.py finalize --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --preview <run-dir>/02-visual-preview.json --review <run-dir>/02-visual-review.json --write <run-dir>/02-visual-build.json`;
   - finalization re-renders and compares SVG hashes to the reviewed attempt before collision-safe registration. Source assets remain unchanged.

   **Legacy V1 only:** an old schema-1 run may still materialize `02-sketches` through `python scripts/venv_exec.py scripts/visual_plan.py ...` / `study_generate_sketch_figure`. Do not convert it to V2 merely for migration.

   Stop unless `02-visual-build.json -> ok: true`.

5. **DRAFT** → only after successful visual finalization, write `03-draft.md` from plan, canonical knowledge and `02-visual-build.json`. Use the exact registered `asset` returned by the build. A `reinterpret` uses its derived asset, never its source PNG. `preserve+derived_sketch` uses both members. Place each figure beside its explanation.

6. **REVIEW** → execute the shared independent academic/pedagogical review. `visual_support` here evaluates whether the selected visuals teach the right things and preserve truth; it does **not** replace the pre-draft V2 vision review. Fail if Markdown treatment differs from the plan/build.

7. **RENDER CANDIDATE** → for V2 runs render the accepted Markdown first to `<run-dir>/09-rendered-base.html`:
   `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered-base.html --kind summary --course "<course-display-name>" --scope "<scope>" --check`.
   Then run `python scripts/venv_exec.py scripts/scene_responsive.py <run-dir>/09-rendered-base.html <run-dir>/09-rendered.html --report <run-dir>/09-responsive.json` so mobile uses the reviewed narrow geometry. A legacy run with no V2 scenes may render directly to `09-rendered.html` as before.

8. **INTEGRITY GATE** → V2 runs use:
   `python scripts/venv_exec.py scripts/artifact_integrity_v2.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --plan <run-dir>/02-plan.json --preview <run-dir>/02-visual-preview.json --review <run-dir>/02-visual-review.json --build <run-dir>/02-visual-build.json --write <run-dir>/10-integrity.json`.
   This binds plan, scene, reviewed PNG hashes, registered wide/narrow SVG hashes and responsive final HTML. Legacy schema-1-only runs may continue through `study_validate_artifact(..., plan=...)` / `scripts/artifact_integrity.py`.

9. **BROWSER VISUAL GATE** → V2 runs use `python scripts/venv_exec.py scripts/visual_audit_v2.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`; legacy runs may use `scripts/visual_audit.py`. Require `audit.json -> ok: true`. Inspect document-level desktop/mobile evidence and every V2 per-scene desktop/mobile crop. The physical notebook reader can hide figures on inactive leaves, so a single screenshot is not enough.

10. **ATOMIC PUBLISH** → after all gates pass, publish the accepted Markdown and final `09-rendered.html` with `scripts/publish_artifact.py`. The publisher rebases both ordinary image refs and V2 responsive `srcset` assets while preserving immutable run-source hashes.

11. **MARK** → mark the published HTML through Study MCP when connected or the deterministic artifact-state CLI otherwise.

12. **FINISH** → `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. Shared finish requirements remain mandatory: no engine mutation during the study run, no academic/concept/topic drift, no source-figure edit/removal, no unplanned figure registration, successful `10-integrity.json`, browser evidence and atomic publication. V2 figures are append-only derived records declared by `02-plan.json` / `02-visual-build.json`; failed attempts are not canonical state.
