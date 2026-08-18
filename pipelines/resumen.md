# Pipeline: resumen

**Mode:** `SUMMARY`

## READ
Load the shared lifecycle first:
- `pipelines/_shared/semantic-document-lifecycle.md`

Then load the summary runtime optimization contract:
- `pipelines/_shared/summary-runtime-optimization.md`

Then load only these summary-specific rules/contracts before semantic work:
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
- `contracts/hybrid-visuals.md`

## SHARED LIFECYCLE
Execute `pipelines/_shared/semantic-document-lifecycle.md` exactly. The steps below specialize that lifecycle for summaries. They do not replace or weaken any shared academic review, gate, publication, environment or failure requirement.

## ACTIVE VISUAL ARCHITECTURE
The current `/resumen` path is hybrid. The visual and notebook improvements already present in this branch remain active; only the expensive free-composition V2 scene-authoring/review path is removed from the normal critical path.

- **Exact academic structure** → `visual_medium: diagram` → compact schema-1 structured spec → deterministic SVG through the existing `scripts/visual_plan.py` backend, dispatched by `scripts/visual_plan_hybrid.py`.
- **Physical/recognizable support** → `visual_medium: illustration` → compact semantic illustration object → one bounded generated-image provider call → deterministic crop/background removal → transparent notebook overlay.
- **Precision-sensitive source evidence** → `preserve` unchanged.
- Generated illustrations are always optional `visual_helpful`; they never carry required academic truth.
- The old schema-2 free-composition engine stays in the repository for compatibility/testing but is not required for new summary visuals.

## RUNTIME BUDGET
A standard `resumen` should normally finish in roughly **10–20 minutes** on a capable hosted model; **30 minutes** is a performance warning and **60+ minutes is a runtime/product failure**.

Runtime optimization never changes the pedagogical visual decision. Never choose `visual_not_needed` merely to save tokens, time, provider calls or implementation work.

The summary model must not author raw SVG, explicit coordinate-heavy scene graphs, separate wide/narrow scene geometry or per-image visual-review loops. Browser auditing is final integration QA, not another illustration-generation session.

## GATE INTEGRITY
A study agent may repair run-local candidate data, but it must never repair the engine in order to make the current run pass.
- Never edit `scripts/`, `pipelines/`, `rules/`, `contracts/`, `core/`, `design/`, `study_mcp/`, tests or other protected engine files during a running study pipeline.
- Never hand-write or patch `02-visual-build.json`; it must come from `scripts/visual_plan_hybrid.py`.
- Never patch validators/renderers to accommodate a candidate. A legitimate engine defect stops the run and is fixed outside that run.

## DEPTH
`resumen` is the single public long-form study-document action.
- Default depth is `standard`.
- Explicit `detallado`, `profundo`, former “guía”, or equivalent wording selects `detailed` while preserving scope and every gate.
- Detailed mode may add useful explanation/examples but cannot invent syllabus scope or become a transcript rewrite.
- Record `depth: "standard"|"detailed"` in `02-plan.json`.
- The published artifact remains the unit's canonical `resumen`; detailed mode changes depth, not the public artifact type.

## Pipeline-specific RUN specialization
1. **SCOPE + PREREQUISITE** → resolve course + scope to exactly one stable `unit_id`; summary scope is unit-only. Apply the shared **NEEDS_INGESTION** boundary before starting. Use canonical concepts plus observed topics from `conocimiento/topics.json` as a coverage guard. If Study MCP is connected, prefer `study_get_unit_context(course, scope)` / `study_list_artifacts(course)` for canonical context. Figure migration is legacy metadata normalization only; it must not reread sources.

2. **START RUN** → `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline resumen --scope "<scope>"`. The run records deterministic fingerprints of engine and canonical inputs. Figure mutation is allowed only through the planned hybrid visual build.

3. **PLAN** → write `02-plan.json`, including `depth`. Use canonical knowledge to decide ordering, examples, traps and omissions. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; for every selected visual record treatment, reason and provenance.

   Select the medium by teaching job:
   - exact flow/cycle/timeline/hierarchy/relationship/architecture/state/order/topology → `visual_medium: diagram`;
   - optional physical recognition of a CPU, RAM, disk, keyboard, monitor, printer or similar subject → `visual_medium: illustration`;
   - source pixels whose precision matters → `preserve`.

   `source-first` selects evidence, not final pixels. `preserve` / `preserve+derived_sketch` require a concrete `fidelity_reason`.

   For `diagram`, create a compact schema-1 spec under `<run-dir>/02-sketches/<id>.json`. The model supplies semantic nodes/edges/groups only; do not write raw SVG or explicit scene coordinates. **Never create normal diagrams with an image-generation model.**

   For `illustration`, write only the compact semantic object defined in `contracts/hybrid-visuals.md`. It must be `visual_helpful` + `reinterpret`. Do not write a provider prompt. Do not ask generated pixels to contain academic text, numbers, arrows, formulas, chronology or exact topology.

4. **FIDELITY LEDGER** → before prose, run:
   `python scripts/venv_exec.py scripts/fidelity_constraints.py --course <course> --scope "<scope>" --write <run-dir>/02-fidelity-constraints.json`.
   Use it to preserve unresolved/split-view high-risk claims exactly as required by `summary-runtime-optimization.md`.

5. **VISUAL BUILD** → run:
   `python scripts/venv_exec.py scripts/visual_plan_hybrid.py --course <course> --unit "<scope>" --plan <run-dir>/02-plan.json --write <run-dir>/02-visual-build.json`.

   The hybrid materializer delegates deterministic diagrams to the existing `scripts/visual_plan.py` / `study.py figures generate-sketch` implementation and generated illustrations to the bounded illustration backend.

   For a new illustration there is exactly one provider request. Exact registered spec/asset reuse makes zero provider calls. There is no independent per-illustration vision-review/regeneration loop.

   If `02-visual-build.json` reports an unavailable illustration, make at most one run-local fallback decision for that optional visual: switch it to a deterministic diagram only when the same supported meaning is naturally diagrammable; otherwise mark that optional illustration `visual_not_needed` for this run, remove its derived illustration fields and rerun the hybrid build once. A provider failure must not block the textual summary.

   Stop on a genuine deterministic diagram, registry, collision or engine failure. Continue only with a final build report whose `ok` is true.

6. **DRAFT** → write `03-draft.md` from plan, canonical knowledge, fidelity constraints and the successful `02-visual-build.json`. The draft must stand alone for a student who has not read the sources and remain fully understandable if an optional illustration was omitted. Use the exact registered `asset` returned by the build and place each figure beside its explanation. Generated illustrations supply recognition only and are never cited as exact evidence.

7. **HUMANIZE + FIDELITY GUARD** → execute the shared Humanizer stage to `04-humanized.md`, then run:
   `python scripts/venv_exec.py scripts/fidelity_guard.py --markdown <run-dir>/04-humanized.md --constraints <run-dir>/02-fidelity-constraints.json --write <run-dir>/04-fidelity-guard.json`.
   `ok: false` is a hard pre-review failure; repair only the cited wording before spending an academic-review call.

8. **REVIEW** → execute the shared independent academic/pedagogical review. `visual_support` evaluates whether the chosen medium supports learning and preserves truth. Do not start a separate generated-image aesthetics loop. If the first academic review requires `06-repair.md`, run the fidelity guard on that repair before the second/final review.

9. **RENDER CANDIDATE** → preserve the branch's notebook renderer and code-highlighting improvements. Render the accepted Markdown to `<run-dir>/09-rendered-base.html`:
   `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered-base.html --kind summary --course "<course-display-name>" --scope "<scope>" --check`.

   Then run:
   `python scripts/venv_exec.py scripts/code_highlight_v2.py <run-dir>/09-rendered-base.html <run-dir>/09-rendered.html --report <run-dir>/09-code-highlight.json`.

   Do **not** run `scene_responsive.py` for the active hybrid path; diagrams and illustration overlays are single responsive assets handled by normal document CSS.

10. **INTEGRITY GATE** → run:
   `python scripts/venv_exec.py scripts/artifact_integrity.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --plan <run-dir>/02-plan.json --write <run-dir>/10-integrity.json`.
   Integrity binds final Markdown figure usage to the hybrid plan/registry: deterministic diagrams must use their registered deterministic SVG; illustrations must use the registered generated-illustration overlay; neither may silently substitute a source asset; `preserve+derived_sketch` must use both members.

11. **BROWSER VISUAL GATE** → run `python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit` and require `audit.json -> ok: true`. Inspect desktop/mobile integration. Reject obvious clipping, broken images, misleading generated text/labels, blank illustrations or pasted opaque white cards. If an optional generated illustration is visibly invalid, omit it instead of starting an open-ended generation/review loop.

12. **ATOMIC PUBLISH** → after all gates pass, publish the accepted Markdown and final `09-rendered.html` with `scripts/publish_artifact.py` and write `<run-dir>/11-publication.json`.

13. **RUNTIME REPORT** → run `python scripts/venv_exec.py scripts/run_timing.py --run <run-dir> --write <run-dir>/12-runtime.json` so the benchmark uses measured milestone times rather than estimates.

14. **MARK** → mark the published HTML through Study MCP when connected or the deterministic artifact-state CLI otherwise.

15. **FINISH** → `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. Shared finish requirements remain mandatory: no engine mutation, no academic/concept/topic drift, no source-figure edit/removal, no unplanned figure registration, successful integrity/browser evidence and atomic publication.
