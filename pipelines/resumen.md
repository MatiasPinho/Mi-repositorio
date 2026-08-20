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
Execute `pipelines/_shared/semantic-document-lifecycle.md` exactly. The steps below specialize that lifecycle for summaries. They do not replace or weaken any shared academic, publication or source-truth requirement.

## ACTIVE VISUAL ARCHITECTURE
The active summary path is **Hybrid V1**.

- Exact academic structure → `visual_medium: diagram` → schema-1 semantic sketch → deterministic notebook SVG.
- Optional physical recognition → `visual_medium: illustration` → bounded Cloudflare Workers AI illustration → deterministic crop/transparency → notebook SVG overlay.
- Source figures are evidence/provenance only; raw source pixels are not published by `/resumen`.
- Every selected published visual uses `visual_treatment: reinterpret` and is registered as `origin: derived`.
- Generated illustrations are always optional `visual_helpful`; required academic truth must remain deterministic.
- Schema-2/V2 free-composition remains in the repository for compatibility/testing but is not on this pipeline's critical path.

## HARD RUNTIME BOUNDARY
For this pipeline, `scripts/resumen_guard.py` is authoritative for preflight, plan lock, hybrid build, candidate render, review binding, effective status and finish.

The guard exists specifically so correctness does not depend on agent obedience.

Hard prohibitions during an active run:
- Never edit `scripts/`, `pipelines/`, `rules/`, `contracts/`, `core/`, `design/`, `study_mcp/`, tests or other engine files.
- Never hand-write or patch `02-visual-build.json`.
- Never create repo-root `assets/` copies or run-local symlinks to make images resolve.
- Never edit `manifest.json` to mark a run finished.
- Never re-lock an already locked plan.
- Never edit `02-plan.json` after the plan lock. The only allowed post-lock mutation is the single bounded provider fallback performed by `resumen_guard.py fallback`.
- Never call legacy `pipeline_run.py finish` as the authoritative finish for this hybrid pipeline. A stored manifest status without a valid guard attestation is not a finished run.

## RUNTIME BUDGET
A standard `resumen` should normally finish in roughly **10–20 minutes** on a capable hosted model; **30 minutes** is a performance warning and **60+ minutes is a runtime/product failure**.

Runtime optimization never changes the pedagogical visual decision. Never choose `visual_not_needed` merely to save time, tokens or implementation work.

## DEPTH
`resumen` is the single public long-form study-document action.
- Default depth is `standard`.
- Explicit `detallado`, `profundo`, former “guía”, or equivalent wording selects `detailed` while preserving scope and every gate.
- Detailed mode may add useful explanation/examples but cannot invent syllabus scope or become a transcript rewrite.
- Record `depth: "standard"|"detailed"` in `02-plan.json`.

## PIPELINE

### 1. SCOPE + PREREQUISITE + ENVIRONMENT PREFLIGHT
Resolve course + scope to exactly one stable `unit_id`. Apply **NEEDS_INGESTION** before starting if canonical concepts are missing.

Before starting the run, execute:

`python scripts/venv_exec.py scripts/resumen_guard.py preflight --course <course>`

This preflight is non-blocking for optional illustrations. If Cloudflare credentials are missing, surface the warning explicitly to the user and continue with deterministic diagrams/text. Do not wait until visual build to discover missing credentials.

Use canonical concepts plus observed topics as the coverage boundary. Do not silently enrich canonical claims with unsupported model knowledge.

### 2. START RUN
Execute:

`python scripts/venv_exec.py scripts/pipeline_run.py start --course <course> --pipeline resumen --scope "<scope>"`

The run fingerprints engine and canonical inputs.

### 3. PLAN + SCHEMA VALIDATION + LOCK
Write `<run-dir>/02-plan.json` in one semantic pass.

Requirements:
- include `depth`;
- assign **every canonical concept** to `concept_order`;
- include **every observed topic** in `topic_coverage`;
- `unassigned_concepts` must be empty;
- decide `visual_required`, `visual_helpful` or `visual_not_needed` for every major concept;
- selected visuals record treatment, medium, reason and provenance;
- source figures may appear only as `figure:<id>` provenance inside `based_on`.

For physical-recognition candidates, record one compact `physical_recognition_review` in the same PLAN pass. Use `illustration` only when recognizing the physical form helps learning and no exact labels/arrows/quantities/topology need to live inside generated pixels.

For diagrams, write schema-1 specs under `<run-dir>/02-sketches/<id>.json`. Validate against the real contract before materialization; do not discover basic schema errors by repeatedly running the builder.

Then execute exactly once:

`python scripts/venv_exec.py scripts/resumen_guard.py validate-plan --run <run-dir>`

This command validates the hybrid plan/specs, checks canonical concept/topic coverage and writes `<run-dir>/02-plan-lock.json`. Once locked, arbitrary plan/spec edits are rejected.

### 4. FIDELITY LEDGER
Before prose, execute:

`python scripts/venv_exec.py scripts/fidelity_constraints.py --course <course> --scope "<scope>" --write <run-dir>/02-fidelity-constraints.json`

Use it to preserve unresolved/split-view high-risk claims exactly.

### 5. GUARDED HYBRID VISUAL BUILD
Execute:

`python scripts/venv_exec.py scripts/resumen_guard.py build --run <run-dir>`

The guard delegates to the hybrid materializer, preserves figure-registry root metadata and writes the real `02-visual-build.json`.

If and only if the build returns an unavailable **optional illustration**, the only permitted fallback is:

`python scripts/venv_exec.py scripts/resumen_guard.py fallback --run <run-dir> --concept <concept-id>`

Then rerun the guarded build once.

The fallback command itself performs the narrow plan mutation and updates the lock. Do not edit the plan or `physical_recognition_review` manually. Only one provider fallback is allowed per run.

Stop on deterministic diagram, registry, collision or engine failure. Continue only when the final guarded build reports `ok: true`.

### 6. DRAFT
Write `<run-dir>/03-draft.md` from the locked plan, canonical knowledge, fidelity constraints and successful build report.

The draft must stand alone for a student who has not read the source files. Use the exact derived assets returned by the build and place each figure beside its explanation.

Generated illustrations supply recognition only and are never exact academic evidence.

### 7. HUMANIZE + FIDELITY GUARD
Execute the shared Humanizer stage to `<run-dir>/04-humanized.md`, then:

`python scripts/venv_exec.py scripts/fidelity_guard.py --markdown <run-dir>/04-humanized.md --constraints <run-dir>/02-fidelity-constraints.json --write <run-dir>/04-fidelity-guard.json`

`ok: false` is a hard failure before review.

### 8. REVIEW HANDOFF + REVIEW
Before the first review, execute:

`python scripts/venv_exec.py scripts/resumen_guard.py prepare-review --run <run-dir> --slot 1`

This writes an immutable handoff bound to the candidate hash.

Prefer a genuinely isolated reviewer/context when the environment supports it. If isolation is unavailable, use `portable-handoff` mode and **do not claim independence**.

Every `05-review.json` must include:

```json
{
  "handoff_sha256": "<sha256 reported by prepare-review>",
  "reviewer": {
    "mode": "isolated|portable-handoff",
    "independent": true
  }
}
```

For `portable-handoff`, `independent` must be `false`. For `isolated`, it must be `true`.

Then execute:

`python scripts/venv_exec.py scripts/resumen_guard.py validate-review --run <run-dir> --slot 1`

If repair is required, write `06-repair.md`, run the fidelity guard on it, prepare slot 2 with:

`python scripts/venv_exec.py scripts/resumen_guard.py prepare-review --run <run-dir> --slot 2`

then write `07-review.json` and validate slot 2 with the same guard.

The review cannot award full coverage to a plan with missing/unassigned canonical concepts because the plan lock itself rejects that state before drafting.

### 9. FINAL MARKDOWN + GUARDED RENDER
Use `06-final.md` after an accepted first review, or `08-final.md` after a repaired second review.

Render through the guard, not directly through `render_study.py`:

`python scripts/venv_exec.py scripts/resumen_guard.py render --run <run-dir> --markdown <accepted-md> --html <run-dir>/09-rendered-base.html --kind summary --course-title "<course-display-name>" --scope-title "<scope>"`

The guard resolves unit-relative figure assets deterministically. Do not create copies or symlinks.

Then run:

`python scripts/venv_exec.py scripts/code_highlight_v2.py <run-dir>/09-rendered-base.html <run-dir>/09-rendered.html --report <run-dir>/09-code-highlight.json`

Do not run `scene_responsive.py` on the active Hybrid V1 path.

### 10. INTEGRITY GATE
Execute:

`python scripts/venv_exec.py scripts/artifact_integrity.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --plan <run-dir>/02-plan.json --write <run-dir>/10-integrity.json`

Require `ok: true` and `visual_plan_checked: true`.

### 11. BROWSER VISUAL GATE
Execute:

`python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`

Require `audit.json -> ok: true`. Browser audit is integration QA, not a substitute for academic review.

### 12. ATOMIC PUBLISH
Only after all prior gates pass, publish accepted Markdown + final HTML with `scripts/publish_artifact.py` and write `<run-dir>/11-publication.json`.

### 13. RUNTIME REPORT
Execute:

`python scripts/venv_exec.py scripts/run_timing.py --run <run-dir> --write <run-dir>/12-runtime.json`

### 14. MARK
If Study MCP is connected and `study_mark_artifact` succeeds, do not run a speculative CLI fallback afterward.

If no supported deterministic mark operation is available, report that limitation instead of inventing a `study.py artifacts mark` command.

### 15. GUARDED FINISH + AUTHORITATIVE STATUS
Execute:

`python scripts/venv_exec.py scripts/resumen_guard.py finish --run <run-dir>`

The guard re-runs the structural/canonical/publication checks, validates review handoffs, uses the correct selected Hybrid V1 derived set, and writes `<run-dir>/13-finish.json` only after a real pass.

Finally execute:

`python scripts/venv_exec.py scripts/resumen_guard.py status --run <run-dir>`

Only `effective_status: finished` is a successful run.

A manually edited `manifest.json` without a matching valid attestation is not finished. A published HTML can exist while the run is still failed.
