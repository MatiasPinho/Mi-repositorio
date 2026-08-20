# Pipeline: resumen

**Mode:** `SUMMARY`

## READ
Load, in order:
- `pipelines/_shared/semantic-document-lifecycle.md`
- `pipelines/_shared/summary-runtime-optimization.md`
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

Execute the shared lifecycle exactly. This file only specializes it for summaries.

## ACTIVE VISUAL ARCHITECTURE
The active path is **Hybrid V1**:
- exact academic structure → `diagram` → schema-1 semantic sketch → deterministic notebook SVG;
- optional physical recognition → `illustration` → bounded Cloudflare Workers AI generation → deterministic crop/transparency → notebook overlay;
- source figures are provenance/evidence only, never final summary pixels;
- selected published visuals use `reinterpret` and are `origin: derived`;
- generated illustrations are always optional `visual_helpful`;
- schema-2/V2 free-composition remains compatibility/testing code, not this pipeline's critical path.

## AUTHORITATIVE RUNTIME GUARD
For `/resumen`, `scripts/resumen_guard.py` is authoritative for environment preflight, plan validation/lock, bounded provider fallback, visual build, candidate render and review binding. `scripts/resumen_finalize.py` is authoritative for finish/status.

Correctness must not depend on agent obedience.

During an active run, never:
- edit engine files (`scripts/`, `pipelines/`, `rules/`, `contracts/`, `core/`, `design/`, `study_mcp/`, tests);
- hand-write or patch `02-visual-build.json`;
- create repo-root `assets/` copies or run-local symlinks to repair image paths;
- edit `manifest.json` to claim success;
- re-lock a plan;
- edit a locked plan/spec manually;
- call legacy `pipeline_run.py finish` as the authoritative Hybrid V1 finish.

A published candidate may exist while the run is failed. Only guarded `effective_status: finished` means success.

## DEPTH + RUNTIME
Default `depth` is `standard`; explicit detailed/profound wording selects `detailed`. Record it in `02-plan.json`. A standard run should normally take about 10–20 minutes; 30 minutes is a warning and 60+ minutes is a product/runtime failure. Never weaken pedagogy to save runtime.

## PIPELINE

### 1. SCOPE + PREREQUISITE + PREFLIGHT
Resolve exactly one stable `unit_id`. Stop with **NEEDS_INGESTION** if canonical concepts are missing.

Run before starting:

`python scripts/venv_exec.py scripts/resumen_guard.py preflight --course <course>`

Missing Cloudflare credentials are a visible, non-blocking warning: text and deterministic diagrams remain available. Do not discover missing credentials deep into visual build.

### 2. START

`python scripts/venv_exec.py scripts/pipeline_run.py start --course <course> --pipeline resumen --scope "<scope>"`

### 3. PLAN + VALIDATE + LOCK
Write `<run-dir>/02-plan.json` once.

Requirements:
- assign **every canonical concept** in `concept_order`;
- include **every observed topic** in `topic_coverage`;
- `unassigned_concepts` must be empty;
- decide `visual_required`, `visual_helpful` or `visual_not_needed` for major concepts;
- record treatment, medium, reason and provenance for selected visuals;
- source figures may appear only as `figure:<id>` provenance;
- diagrams use schema-1 specs under `<run-dir>/02-sketches/`;
- physical-recognition candidates are recorded in one compact `physical_recognition_review` during this PLAN pass.

Then run exactly once:

`python scripts/venv_exec.py scripts/resumen_guard.py validate-plan --run <run-dir>`

This validates canonical coverage + hybrid schemas and writes `02-plan-lock.json`. After lock, arbitrary plan/spec edits are rejected.

### 4. FIDELITY LEDGER

`python scripts/venv_exec.py scripts/fidelity_constraints.py --course <course> --scope "<scope>" --write <run-dir>/02-fidelity-constraints.json`

### 5. GUARDED VISUAL BUILD

`python scripts/venv_exec.py scripts/resumen_guard.py build --run <run-dir>`

The guard preserves figure-registry root metadata while allowing only planned derived additions.

If and only if the build reports an unavailable optional illustration, the sole allowed post-lock mutation is:

`python scripts/venv_exec.py scripts/resumen_guard.py fallback --run <run-dir> --concept <concept-id>`

Then rerun guarded build once. The fallback command itself edits the narrow allowed fields and updates the lock. Do not edit the plan manually. Stop on deterministic diagram, registry, collision or engine failure.

### 6. DRAFT
Write `03-draft.md` only after `02-visual-build.json -> ok: true`. Use canonical knowledge, fidelity constraints and the exact derived assets returned by the build. Generated illustrations are recognition support, never exact evidence.

### 7. HUMANIZE + FIDELITY GUARD
Humanize to `04-humanized.md`, then run:

`python scripts/venv_exec.py scripts/fidelity_guard.py --markdown <run-dir>/04-humanized.md --constraints <run-dir>/02-fidelity-constraints.json --write <run-dir>/04-fidelity-guard.json`

`ok: false` is a hard pre-review failure.

### 8. BOUND REVIEW
Prepare slot 1:

`python scripts/venv_exec.py scripts/resumen_guard.py prepare-review --run <run-dir> --slot 1`

Prefer a genuinely isolated reviewer/context. If unavailable, use transparent `portable-handoff` mode and **do not claim independence**.

`05-review.json` must include the reported `handoff_sha256` plus:

```json
"reviewer": {
  "mode": "isolated",
  "independent": true
}
```

or, when isolation is unavailable:

```json
"reviewer": {
  "mode": "portable-handoff",
  "independent": false
}
```

Validate:

`python scripts/venv_exec.py scripts/resumen_guard.py validate-review --run <run-dir> --slot 1`

If the first review rejects the candidate, write `06-repair.md`, fidelity-check the repair, prepare slot 2, write `07-review.json`, and validate slot 2:

`python scripts/venv_exec.py scripts/resumen_guard.py prepare-review --run <run-dir> --slot 2`

`python scripts/venv_exec.py scripts/resumen_guard.py validate-review --run <run-dir> --slot 2`

The failed first review remains legitimate history; a passing, bound second review may accept the repair.

### 9. FINAL + GUARDED RENDER
Use `06-final.md` after an accepted first review or `08-final.md` after repair.

Render through the guard:

`python scripts/venv_exec.py scripts/resumen_guard.py render --run <run-dir> --markdown <accepted-md> --html <run-dir>/09-rendered-base.html --kind summary --course-title "<course-display-name>" --scope-title "<scope>"`

The guard resolves unit-relative images. No symlinks/copies.

Then:

`python scripts/venv_exec.py scripts/code_highlight_v2.py <run-dir>/09-rendered-base.html <run-dir>/09-rendered.html --report <run-dir>/09-code-highlight.json`

Do not run `scene_responsive.py` on Hybrid V1.

### 10. INTEGRITY

`python scripts/venv_exec.py scripts/artifact_integrity.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --plan <run-dir>/02-plan.json --write <run-dir>/10-integrity.json`

Require `ok: true` and `visual_plan_checked: true`.

### 11. BROWSER VISUAL GATE

`python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`

Require `audit.json -> ok: true`.

### 12. ATOMIC PUBLISH
Only now run `scripts/publish_artifact.py` and write `<run-dir>/11-publication.json`.

### 13. RUNTIME REPORT

`python scripts/venv_exec.py scripts/run_timing.py --run <run-dir> --write <run-dir>/12-runtime.json`

### 14. MARK
If Study MCP is connected and `study_mark_artifact` succeeds, do not run a speculative CLI fallback afterward. If no supported mark operation exists, report that limitation; never invent `study.py artifacts mark`.

### 15. AUTHORITATIVE FINISH + STATUS

`python scripts/venv_exec.py scripts/resumen_finalize.py finish --run <run-dir>`

This revalidates the locked plan, selected Hybrid V1 figure set, canonical drift, publication, review handoffs and repaired-review lifecycle before writing `13-finish.json`.

Then:

`python scripts/venv_exec.py scripts/resumen_finalize.py status --run <run-dir>`

Only `effective_status: finished` is success. Manually setting `manifest.json` to `finished` without a matching valid attestation does not create a successful run.
