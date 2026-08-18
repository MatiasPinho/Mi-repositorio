# Pipeline: resumen

**Mode:** `SUMMARY`

## READ
Load the shared lifecycle first:
- `pipelines/_shared/semantic-document-lifecycle.md`

Then load the summary runtime optimization contract:
- `pipelines/_shared/summary-runtime-optimization.md`

Then load only these summary-specific shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/concept-ordering.md`
- `rules/pedagogy/examples.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/writing/summary.md`
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/pedagogy-rubric.md`
- `rules/evaluation/visual-rubric.md`
- `rules/evaluation/quality-gates.md`
- `contracts/handoffs.md`

## SHARED LIFECYCLE
Execute `pipelines/_shared/semantic-document-lifecycle.md` exactly. The steps below specialize that lifecycle for summaries and add summary-only visual stages. They do not replace or weaken any shared academic review, gate, publication, environment or failure requirement.

## RUNTIME BUDGET
Quality gates protect the artifact; they must not turn normal summary generation into an unbounded visual-design session.
- A standard `resumen` should normally finish in roughly **10–20 minutes** on a capable hosted model; **30 minutes** is a performance warning and **60+ minutes is a runtime/product failure**.
- Never ask an AI reviewer to prove byte/hash facts that deterministic code can prove.
- Use one visual review batch for all new/changed scenes.
- A failed scene gets **one repair round and one final review only**. New runs may create at most **two reviewable attempts per scene**. There is no third visual review.
- If a scene still fails after that final review, omit that figure from the current summary plan and continue. A failed illustration must not block production of the textual summary.
- Unchanged PASS scenes are carried forward mechanically and are not re-reviewed.
- Post-render browser auditing is deterministic integration QA, not another open-ended figure review.

## GATE INTEGRITY
A study agent may repair run-local candidate data, but it must never repair the engine in order to make the current run pass.
- Never edit `scripts/`, `pipelines/`, `rules/`, `contracts/`, `core/`, `design/`, `study_mcp/`, tests or other protected engine files during a running study pipeline.
- Never hand-write, synthesize or patch `02-visual-build.json` as a substitute for `visual_plan_v2.py finalize`.
- Never patch validators/renderers to accommodate a candidate. A legitimate engine defect stops the run and is fixed outside that run.

## DEPTH
`resumen` is the single public long-form study-document action.
- Default depth is `standard`.
- Explicit `detallado`, `profundo`, former “guía”, or equivalent wording selects `detailed` while preserving scope and every gate.
- Detailed mode may add useful explanation/examples but cannot invent syllabus scope or become a transcript rewrite.
- Record `depth: "standard"|"detailed"` in `02-plan.json`.
- The published artifact remains the unit's canonical `resumen`; detailed mode changes depth, not the public artifact type.

## Pipeline-specific RUN specialization
1. **SCOPE + PREREQUISITE** → resolve course + scope to exactly one stable `unit_id`; summary scope is unit-only. Apply the shared **NEEDS_INGESTION** boundary before starting. Use canonical concepts plus **observed topics** from `conocimiento/topics.json` as a coverage guard. If Study MCP is connected, prefer `study_get_unit_context(course, scope)` / `study_list_artifacts(course)` for canonical context. Figure migration is legacy metadata normalization only; it must not reread sources.

2. **START RUN** → `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline resumen --scope "<scope>"`. The run records deterministic fingerprints of engine and canonical inputs. Figure mutation is allowed only after reviewed visual finalization.

3. **PLAN** → write `02-plan.json`, including `depth`. Use canonical knowledge to decide ordering, examples, traps and omissions. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; for every selected visual record treatment, reason and provenance. `source-first` selects evidence, not final pixels. `preserve` / `preserve+derived_sketch` require a concrete `fidelity_reason`.

   For a **new derived pedagogical figure**, design a schema-2 scene under `<run-dir>/02-scenes/<id>.json` and reference it with `scene_spec`. The model owns semantic composition and geometry; Carpeta owns SVG/CSS/colors/fonts, deterministic rendering and validation. Academic elements are declared once and wide/narrow layouts change geometry only. Do not write polished prose or raw SVG here.

   Registered V2 scene ids are immutable revisions. A visual-policy change invalidates an old PASS for automatic reuse, but it does **not** force a byte-identical composition to be redesigned before preview. The old scene may be judged under the current policy in the normal review batch. If an already-registered scene must actually change after a failed review, create a new scene id / `derived_figure_id`; never overwrite the old revision.

   Existing schema-1 figures remain supported under `<run-dir>/02-sketches/` for backward compatibility.

4. **VISUAL BUILD** → build selected visuals with a strict review budget.

   **V2 default for new derived figures:**
   - if an exact prior V2 scene has an exact PASS under the **same active visual policy**, cross-run PASS reuse may be attempted according to `summary-runtime-optimization.md`; otherwise continue normally without treating the old PASS as current evidence;
   - run `python scripts/venv_exec.py scripts/visual_plan_v2.py preview --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --write <run-dir>/02-visual-preview.json`;
   - deterministic preflight checks objective renderability/geometry before vision. Repair a cited mechanical failure surgically; do not enter an open-ended redesign loop. If a scene cannot be made mechanically renderable with a targeted repair, omit that scene from the plan and continue;
   - a separate vision-capable reviewer inspects all **new or changed** wide/narrow PNGs once, in one batch, against `rules/evaluation/visual-rubric.md`, and writes `02-visual-review.json` following `contracts/visual-review.schema.json`;
   - the reviewer receives only current screenshots, scene specs, pedagogical objective/provenance and the rubric. It does not explore the repository or pipeline history;
   - `generic-box-substitution` remains a blocking representational defect for recognizable concepts when a safe schematic depiction is available. The AI is still free to choose how to draw the concept;
   - if the first review fails any scene, repair **only those failed scenes once**. If changing an already-registered scene, use a new append-only id. Preview again; unchanged PASS scenes reuse their existing attempt/hashes;
   - run one **final** vision review only for changed repaired evidence. This is the second and last reviewable attempt for a scene;
   - if a scene still fails after the second reviewed attempt, remove that visual from the current `02-plan.json` (mark it `visual_not_needed` for this run and remove its derived scene fields), rerun preview so remaining scenes bind to the updated plan, carry unchanged PASS rows mechanically, and continue. **Do not attempt a third review.** If all V2 scenes are omitted, use an empty current review handoff bound to the empty preview set and continue;
   - after the remaining current scenes pass, run `python scripts/venv_exec.py scripts/visual_plan_v2.py finalize --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --preview <run-dir>/02-visual-preview.json --review <run-dir>/02-visual-review.json --write <run-dir>/02-visual-build.json`;
   - finalization re-renders and compares hashes before collision-safe registration. It remains the only valid producer of `02-visual-build.json`.

   **Legacy V1 only:** old schema-1 material may continue through `scripts/visual_plan.py` / `study_generate_sketch_figure` unchanged.

   A visual that exhausts its review budget is omitted; it is not a reason to abandon the summary. A genuine engine/finalizer failure remains a run blocker.

5. **DRAFT** → after the bounded visual build, write `03-draft.md` from plan, canonical knowledge and `02-visual-build.json`. The draft must remain fully understandable even when one or more optional figures were omitted. Use the exact registered `asset` returned by the build for every surviving visual. Place each figure beside its explanation.

6. **REVIEW** → execute the shared independent academic/pedagogical review. `visual_support` evaluates whether surviving visuals support learning and preserve truth; it does not reopen closed visual-layout work. Academic fidelity remains mandatory regardless of how many visuals survived.

7. **RENDER CANDIDATE** → for V2 runs render the accepted Markdown first to `<run-dir>/09-rendered-base.html`:
   `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered-base.html --kind summary --course "<course-display-name>" --scope "<scope>" --check`.

   Then run:
   `python scripts/venv_exec.py scripts/code_highlight_v2.py <run-dir>/09-rendered-base.html <run-dir>/09-rendered-code.html --report <run-dir>/09-code-highlight.json`.

   Then run:
   `python scripts/venv_exec.py scripts/scene_responsive.py <run-dir>/09-rendered-code.html <run-dir>/09-rendered.html --report <run-dir>/09-responsive.json`.
   A legacy run with no V2 scenes may render directly to `09-rendered.html`.

8. **INTEGRITY GATE** → V2 runs use:
   `python scripts/venv_exec.py scripts/artifact_integrity_v2.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --plan <run-dir>/02-plan.json --preview <run-dir>/02-visual-preview.json --review <run-dir>/02-visual-review.json --build <run-dir>/02-visual-build.json --write <run-dir>/10-integrity.json`.
   This binds the **final pruned plan**, active policy, surviving scenes, reviewed PNG hashes, deterministic finalizer replay, registered wide/narrow SVG hashes and responsive HTML. Omitted failed scenes are not planned visuals anymore and therefore are not required by integrity.

9. **BROWSER VISUAL GATE** → V2 runs use `python scripts/venv_exec.py scripts/visual_audit_v2.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`; legacy runs may use `scripts/visual_audit.py`. Require `audit.json -> ok: true`. This is deterministic integration evidence and must not trigger another open-ended visual redesign cycle.

10. **ATOMIC PUBLISH** → after all gates pass, publish the accepted Markdown and final `09-rendered.html` with `scripts/publish_artifact.py` and write `<run-dir>/11-publication.json`.

11. **MARK** → mark the published HTML through Study MCP when connected or the deterministic artifact-state CLI otherwise.

12. **FINISH** → `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. Shared finish requirements remain mandatory: no engine mutation, no academic/concept/topic drift, no source-figure edit/removal, no unplanned figure registration, successful integrity/browser evidence and atomic publication. V2 figures remain append-only derived records declared by the **final** plan/build.