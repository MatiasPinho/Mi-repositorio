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

## RUNTIME BOUNDARY
Visual support is secondary to producing the study document. A normal summary on a capable hosted model should remain close to the established main-pipeline cost, not become a free-form graphics session.
- The planner may choose as many visuals as pedagogy requires, but each visual uses a bounded representation.
- Exact diagrams use the compact deterministic schema-1 path; the model never authors raw SVG or explicit coordinate scenes.
- Optional illustrations use one compact semantic spec and one bounded image-provider call. There is no independent per-illustration vision-review loop.
- A provider outage never justifies repeated image retries or weaker academic prose.
- 30 minutes is a performance warning for a standard run; 60+ minutes is a product/runtime failure.

## DEPTH
`resumen` is the single public long-form study-document action.
- Default depth is `standard`: balanced, self-contained notes for normal study.
- Explicit `detallado`, `profundo`, former “guía”, or equivalent wording selects `detailed`: preserve the same academic scope and gates while allowing more explanatory scaffolding, examples, contrasts and prerequisite reminders where useful.
- Detailed mode must not invent extra syllabus scope, reread raw sources merely to add volume, impose a fixed length, or become an exhaustive transcript rewrite.
- Record `depth: "standard"|"detailed"` in `02-plan.json`. The published artifact remains the unit's canonical `resumen`.

## Pipeline-specific RUN specialization
1. **SCOPE + PREREQUISITE** → resolve course + scope to exactly one stable `unit_id`; summary scope is unit-only. Resolve optional depth intent before starting. If Study MCP is connected, call `study_get_unit_context(course, scope)` once and `study_list_artifacts(course)` instead of manually reopening/filtering canonical JSON. Otherwise use only files below `unidades/<unit-id>/` plus explicit cross-unit prerequisites. Refuse unresolved/global pedagogical scope. Apply the shared **NEEDS_INGESTION** boundary before starting. Run `python scripts/venv_exec.py study.py figures migrate <course>` once; this only normalizes legacy metadata and does not reread sources.

2. **START RUN** → `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline resumen --scope "<scope>"`. The run records deterministic fingerprints of the engine and canonical academic/concept/topic/figure inputs. Apply active-run isolation. Figure mutations are allowed only through the planned visual build.

3. **PLAN** → write `02-plan.json`, including `depth`. Use canonical knowledge, not raw transcript prose, to decide central idea, ordering, examples, traps and omissions. Use observed topics as a flexible coverage map while keeping declared syllabus topics separate.

   For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`. This is pedagogical, never a runtime shortcut. For every selected visual choose treatment/provenance and then the representation described in `rules/visual/figures.md`:
   - **exact structure/flow/cycle/timeline/hierarchy/relationship** → `visual_medium: diagram`; write a compact validated schema-1 spec under `<run-dir>/02-sketches/`;
   - **recognizable physical/conceptual likeness that only supports the prose** → `visual_medium: illustration`; use `need: visual_helpful` and write only the small inline semantic `illustration` object from `contracts/handoffs.md`;
   - **precision-sensitive source evidence** → `preserve` with concrete `fidelity_reason`;
   - `preserve+derived_sketch` remains source + deterministic `diagram` only.

   A generated illustration must never carry exact labels, arrows, quantities, chronology, topology, formulas or assessment-critical facts. Those belong in prose/HTML or deterministic diagrams. Never generate a whole page as an image. Do not write polished prose, raw SVG, coordinates or long provider prompts during PLAN.

4. **VISUAL BUILD** → before drafting run:
   `python scripts/venv_exec.py scripts/visual_plan_hybrid.py --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --write <run-dir>/02-visual-build.json`.

   The hybrid materializer validates every visual decision and delegates diagram rows to the established deterministic `scripts/visual_plan.py` / `scripts/sketch_figure.py` behavior. Diagram generation remains collision-safe, idempotent and exact. The direct compatibility command remains `python scripts/venv_exec.py study.py figures generate-sketch <course> --unit "<scope>" --spec <run-dir>/02-sketches/<id>.json`; never create normal diagrams with an image-generation model.

   Illustration rows are different: Carpeta constructs the fixed pencil-style prompt from the small semantic spec, makes one bounded provider call, crops/keys the white working canvas to transparency, wraps the raster as a notebook overlay and collision-safely registers it. Credentials and raw academic source text are never stored in the visual spec.

   Keep every `preserve` source asset unchanged. Never edit `figures.json` by hand, mutate a source record into a derived one, or overwrite an existing id/asset.

   If `02-visual-build.json` reports `illustration_unavailable`, do **not** repeatedly retry the provider. Make at most one fallback edit for each failed optional illustration: convert it to a deterministic diagram only when the same supported meaning is naturally diagrammable; otherwise make that optional illustration `visual_not_needed` for this run. Rerun the visual build once against the updated plan. A genuine deterministic diagram/build error remains an engine/run failure.

5. **DRAFT** → after `02-visual-build.json -> ok: true`, write `03-draft.md` from plan, canonical knowledge and the exact build assets. The draft stands alone for a student who has not read the sources. Use semantic callouts and place each visual beside the explanation it supports. A diagram carries exact relationships; an illustration only supplies visual recognition and must not be cited as evidence for a claim.

6. **REVIEW** → execute the shared independent academic/pedagogical review against `02-plan.json`, `02-visual-build.json`, canonical knowledge, registry/assets and all required rubrics. Academic fidelity is unchanged. Do not start a separate image-aesthetics review cycle. If a generated illustration is merely less attractive than hoped but remains relevant and non-misleading, continue; visual polish does not outrank completion. If it visibly claims unsupported information, the artifact fails the truth boundary.

7. **RENDER CANDIDATE** → render accepted Markdown with `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered.html --kind summary --course "<course-display-name>" --scope "<scope>" --check`. Generated illustration overlays use the existing transparent notebook figure treatment; the page itself remains real HTML/CSS.

8. **INTEGRITY GATE** → use `study_validate_artifact(..., plan=<run-dir>/02-plan.json)` when Study MCP is connected, otherwise `python scripts/venv_exec.py scripts/artifact_integrity.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --plan <run-dir>/02-plan.json --write <run-dir>/10-integrity.json`. Persist `<run-dir>/10-integrity.json`. The gate binds every final figure to the plan and distinguishes deterministic diagram generation from registered generated illustrations.

9. **BROWSER VISUAL GATE** → run `python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit` and apply every shared browser requirement. This is final document integration QA, not an open-ended per-figure design loop. Reject broken/decode-failed images, clipping, unreadable sizing or a generated illustration that visibly introduces misleading text/labels. Do not regenerate repeatedly for aesthetic preference.

10. **ATOMIC PUBLISH** → resolve `<publish-dir>` as `unidades/<unit-id>/resumenes`, then after all gates pass run `python scripts/venv_exec.py scripts/publish_artifact.py --markdown <accepted-md> --html <run-dir>/09-rendered.html --dest-markdown <publish-dir>/_source/<scope>-resumen.md --dest-html <publish-dir>/<scope>-resumen.html --report <run-dir>/11-publication.json`. Apply immutability/hash rules; do not publish with generic copy/edit operations.

11. **MARK** → mark the published HTML with `study_mark_artifact` when MCP is connected or `python scripts/venv_exec.py scripts/artifact_state.py mark --type summary --scope "<scope>"` otherwise.

12. **FINISH** → `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. Summary finish rejects missing/corrupt build/publication evidence, engine mutation, academic/concept/topic change, source-figure edit/removal and unplanned figure registration. Only append-only derived records whose ids/treatments match `02-plan.json` and `02-visual-build.json` are permitted.
