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
Execute `pipelines/_shared/semantic-document-lifecycle.md` exactly. The steps below specialize that lifecycle for summaries and add summary-only visual stages. They do not replace or weaken any shared review, gate, publication, environment or failure requirement.

## RUNTIME BUDGET
Quality gates exist to protect the artifact, not to make normal generation unbounded.
- A standard `resumen` run should normally finish in roughly **10–20 minutes** on a capable hosted model; **30 minutes** is a performance warning and **60+ minutes is a runtime/product failure that must be investigated**, even when the artifact eventually passes.
- This is an engineering budget, not permission to skip a required fidelity gate.
- Never ask an AI reviewer to prove a byte/hash fact that deterministic code can prove.
- Never re-review a scene whose normalized scene SHA and wide/narrow PNG SHA-256 values are unchanged from a previous visual PASS in the same run.
- Reviewers receive the **minimum evidence packet for their job**. A visual reviewer gets current PNGs, the scene spec, its pedagogical objective/provenance and the visual rubric; it does not explore the whole repository or load unrelated course state. An academic reviewer gets the accepted prose plus compact canonical claims/concepts needed for fidelity; it does not inspect visual geometry already closed by the visual gate unless the academic claim depends on it.
- Use one visual review batch for all changed scenes. On repair, review only failed/changed scenes. Copy byte-identical prior PASS rows into the current consolidated review mechanically only when the active visual-policy fingerprint is also identical; do not wake another model merely to re-approve identical hashes under an unchanged policy.
- Post-render browser auditing is deterministic integration QA. Do not perform a second open-ended vision review of figures that already passed unless the browser audit exposes a new rendered defect.

## GATE INTEGRITY
A study agent may repair run-local candidate data, but it must never repair the engine in order to make the current run pass.
- Never edit `scripts/`, `pipelines/`, `rules/`, `contracts/`, `core/`, `design/`, `study_mcp/`, tests or other protected engine files during a running study pipeline. Commands executed through `scripts/venv_exec.py` detect engine drift before the target command runs and persist a run-local violation marker; reverting the edit does not rehabilitate that run.
- Never hand-write, synthesize or patch `02-visual-build.json` as a substitute for `visual_plan_v2.py finalize`. Integrity deterministically replays the finalizer's verification path and requires exact build equivalence.
- Never patch `artifact_integrity_v2.py`, `pipeline_run.py`, renderers or validators to accommodate a candidate. A legitimate engine defect stops the study run and must be fixed outside that run, followed by a fresh run.

## DEPTH
`resumen` is the single public long-form study-document action.
- Default depth is `standard`.
- Explicit `detallado`, `profundo`, former “guía”, or equivalent wording selects `detailed` while preserving scope and every gate.
- Detailed mode may add useful explanation/examples but cannot invent syllabus scope or become a transcript rewrite.
- Record `depth: "standard"|"detailed"` in `02-plan.json`.
- The published artifact remains the unit's canonical `resumen`; detailed mode changes depth, not the public artifact type.

## Pipeline-specific RUN specialization
1. **SCOPE + PREREQUISITE** → resolve course + scope to exactly one stable `unit_id`; summary scope is unit-only. Apply the shared **NEEDS_INGESTION** boundary before starting. Use canonical concepts plus **observed topics** from `conocimiento/topics.json` as a coverage guard; observed topics organize what was actually ingested and never replace declared syllabus scope. If Study MCP is connected, prefer `study_get_unit_context(course, scope)` / `study_list_artifacts(course)` for canonical context. Run the figure migration command only for legacy metadata normalization; it must not reread sources.

2. **START RUN** → `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline resumen --scope "<scope>"`. The run records deterministic fingerprints of engine and canonical inputs. Figure mutation is allowed only after a reviewed visual finalization.

3. **PLAN** → write `02-plan.json`, including `depth`. Use canonical knowledge to decide ordering, examples, traps and omissions. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; for every selected visual record treatment, reason and provenance. `source-first` selects evidence, not final pixels. `preserve` / `preserve+derived_sketch` require a concrete `fidelity_reason`.

   For a **new derived pedagogical figure**, design a schema-2 scene under `<run-dir>/02-scenes/<id>.json` and reference it with `scene_spec`. The model owns composition/geometry but not SVG/CSS/colors/fonts. Academic elements are declared once and the wide/narrow layouts change geometry only. Do not write polished prose or SVG here.

   Registered V2 scene ids are immutable revisions. If a newer visual policy or a failed review requires changing an already-registered scene's semantics/geometry, create a **new scene id and matching `derived_figure_id`**; never overwrite the registered revision under the old id. An identical registered scene may be re-reviewed under a new policy without changing its id because its pixels/geometry remain unchanged.

   Existing schema-1 figures remain supported under `<run-dir>/02-sketches/` for backward compatibility. Their legacy contract still uses `scripts/visual_plan.py`, `figures generate-sketch` and `contracts/sketch-figure.schema.json`; never create normal diagrams with an image-generation model.

4. **VISUAL BUILD** → complete visual work **before drafting**.

   **V2 default for new derived figures:**
   - run `python scripts/venv_exec.py scripts/visual_plan_v2.py preview --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --write <run-dir>/02-visual-preview.json`;
   - `02-visual-preview.json` records `visual_policy_sha256`, the deterministic fingerprint of the exact figure-design and visual-review rules active for this preview;
   - stop on deterministic preflight failure and repair the scene; failed attempts remain run-local and do not touch `figures.json`;
   - `preview` reuses an existing attempt when the scene and its rendered evidence are byte-identical. `reused: true` means no new attempt was consumed. If that exact evidence already has a PASS in the preceding review file, carry that row forward mechanically only when its policy fingerprint is identical;
   - a separate vision-capable reviewer must inspect every **new or changed** current `wide.png` and `narrow.png` against `rules/evaluation/visual-rubric.md`, then write `<run-dir>/02-visual-review.json` following `contracts/visual-review.schema.json`. Copy the preview's exact `visual_policy_sha256` into the review. The reviewer must be an independent execution/context and explicitly declare `capability: vision`, `independent: true`, `vision_verified: true`;
   - changing only `visual_policy_sha256` on an older PASS is not review reuse. A PASS from another policy is stale even if the scene/PNG hashes are identical and must go through the current independent review;
   - give the visual reviewer only the changed screenshots, their scene specs, pedagogical objective/provenance and rubric. Do not give it the full repository, full transcript, unrelated concepts, pipeline history or designer justification;
   - a model without image input cannot PASS. Mechanical metrics are not a substitute for rendered inspection;
   - if review fails, repair only failed scenes and preview again. Maximum three reviewed attempts **per changed scene**. Unchanged PASS scenes keep their previous attempt number and hashes. The reviewer may require splitting an overloaded visual into multiple derived scenes, with the plan updated before a new current preview is produced;
   - do not use an AI call to compare hashes or to restate an existing PASS. SHA equality is a deterministic operation;
   - after every current scene passes, run `python scripts/venv_exec.py scripts/visual_plan_v2.py finalize --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --preview <run-dir>/02-visual-preview.json --review <run-dir>/02-visual-review.json --write <run-dir>/02-visual-build.json`;
   - finalization re-renders and compares SVG hashes to the reviewed attempt before collision-safe registration. It is the **only valid producer** of `02-visual-build.json`; integrity later reconstructs the expected build from canonical state and rejects a hand-authored replacement. Source assets remain unchanged.

   **Legacy V1 only:** an old schema-1 run may still materialize `02-sketches` through `python scripts/venv_exec.py scripts/visual_plan.py ...` / `study_generate_sketch_figure`. Do not convert it to V2 merely for migration.

   Stop unless the canonical finalize command itself returns success and writes `02-visual-build.json -> ok: true`. A finalize error is a run blocker; do not fabricate the build report or weaken a later gate.

5. **DRAFT** → only after successful visual finalization, write `03-draft.md` from plan, canonical knowledge and `02-visual-build.json`. Use the exact registered `asset` returned by the build. A `reinterpret` uses its derived asset, never its source PNG. `preserve+derived_sketch` uses both members. Place each figure beside its explanation.

6. **REVIEW** → execute the shared independent academic/pedagogical review. `visual_support` here evaluates whether the selected visuals teach the right things and preserve truth; it does **not** replace the pre-draft V2 vision review. Fail if Markdown treatment differs from the plan/build. Review the high-risk/uncertain claims first and do not reopen closed visual-layout work.

7. **RENDER CANDIDATE** → for V2 runs render the accepted Markdown first to `<run-dir>/09-rendered-base.html`:
   `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered-base.html --kind summary --course "<course-display-name>" --scope "<scope>" --check`.

   Complete deterministic syntax colour for explicit code languages next:
   `python scripts/venv_exec.py scripts/code_highlight_v2.py <run-dir>/09-rendered-base.html <run-dir>/09-rendered-code.html --report <run-dir>/09-code-highlight.json`.
   Java, BASIC and Prolog are supported in addition to the renderer's existing profiles. Unsupported explicit languages remain readable but are reported as warnings rather than silently pretending to be highlighted.

   Then run `python scripts/venv_exec.py scripts/scene_responsive.py <run-dir>/09-rendered-code.html <run-dir>/09-rendered.html --report <run-dir>/09-responsive.json` so mobile uses the reviewed narrow geometry. A legacy run with no V2 scenes may render directly to `09-rendered.html` as before.

8. **INTEGRITY GATE** → V2 runs use:
   `python scripts/venv_exec.py scripts/artifact_integrity_v2.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --plan <run-dir>/02-plan.json --preview <run-dir>/02-visual-preview.json --review <run-dir>/02-visual-review.json --build <run-dir>/02-visual-build.json --write <run-dir>/10-integrity.json`.
   This binds plan, active visual policy, scene, reviewed PNG hashes, deterministic finalizer replay, registered wide/narrow SVG hashes and responsive final HTML. The V2 gate explicitly disables V1 plan auto-discovery before applying its own visual contract. Legacy schema-1-only runs may continue through `study_validate_artifact(..., plan=...)` / `scripts/artifact_integrity.py`.

9. **BROWSER VISUAL GATE** → V2 runs use `python scripts/venv_exec.py scripts/visual_audit_v2.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`; legacy runs may use `scripts/visual_audit.py`. Require `audit.json -> ok: true`. Inspect document-level desktop/mobile evidence and every V2 per-scene desktop/mobile crop. The physical notebook reader can hide figures on inactive leaves, so a single screenshot is not enough. This is integration evidence, not permission to re-run an open-ended figure reviewer when the reviewed assets are unchanged.

10. **ATOMIC PUBLISH** → after all gates pass, publish the accepted Markdown and final `09-rendered.html` with `scripts/publish_artifact.py`. The publisher rebases both ordinary image refs and V2 responsive `srcset` assets while preserving immutable run-source hashes.

11. **MARK** → mark the published HTML through Study MCP when connected or the deterministic artifact-state CLI otherwise.

12. **FINISH** → `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. Shared finish requirements remain mandatory: no engine mutation during the study run (including temporary mutation later reverted), no academic/concept/topic drift, no source-figure edit/removal, no unplanned figure registration, successful `10-integrity.json`, browser evidence and atomic publication. V2 figures are append-only derived records declared by `02-plan.json` / `02-visual-build.json`; failed attempts are not canonical state.
