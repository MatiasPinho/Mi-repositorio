# Portable handoff contracts

Unit-scoped semantic pipeline runs live under:
`materias/<course>/unidades/<unit-id>/.study/runs/<run-id>/`

Only genuinely course-wide runs may live under
`materias/<course>/.study/runs/<run-id>/`.

`manifest.json` records pipeline, course, scope, timestamps, status and stage files.

## Standard stage files
- `01-input.json`: resolved course/scope, relevant canonical paths/fingerprints, requested mode.
- `02-plan.json`: pedagogical/content plan. No polished prose.
- `02-sketches/<id>.json`: legacy schema-1 structured specs for deterministic graph SVGs.
- `02-scenes/<id>.json`: schema-2 free scene graph specs for new derived figures.
- `02-visual-preflight-failures/<scene-id>/<NN>/`: run-local scene/preflight evidence for deterministic failures. These failures do not consume a vision-review attempt.
- `02-visual-attempts/<scene-id>/<NN>/`: run-local V2 normalized scene, passing preflight, wide/narrow SVGs and preview PNGs eligible for independent vision review. New summary runs create at most two reviewable attempts per scene.
- `02-visual-preview.json`: current V2 preview report bound to the current `02-plan.json`.
- `02-visual-review.json`: independent vision review bound to exact preview PNG SHA-256 values. It may contain an empty `figures` array only when the current preview set is empty after failed visuals were deliberately omitted from the final plan.
- `02-visual-build.json`: deterministic materialization report binding the final plan to registered assets before drafting. V2 build reports also bind preview/review hashes and `vision_verified: true`.
- `03-draft.md`: first student-facing draft.
- `04-humanized.md`: Humanizer output.
- `05-review.json`: independent academic fidelity + pedagogy review; `visual_support` evaluates visual selection, not V2 perceptual execution.
- `06-final.md`: accepted candidate when the first review passes.
- `06-repair.md`: targeted repair when the first review fails.
- `07-review.json`: second and final review of the repair.
- `08-final.md`: accepted repaired candidate after the second review.
- `09-rendered-base.html`: optional V2 intermediate produced by the normal Markdown renderer before responsive scene markup is applied.
- `09-rendered.html`: deterministic final rendered study surface for the accepted Markdown.
- `10-integrity.json`: deterministic pre-publication gate. Must contain `"ok": true` before publication.

Pipelines may omit stages that do not apply, but filenames and semantics must stay stable across executors.

## Review JSON minimum
```json
{
  "pass": true,
  "scores": {
    "academic_fidelity": 5,
    "clarity": 5,
    "progression": 5,
    "explanation": 5,
    "examples": 4,
    "signal_to_noise": 5,
    "naturalness": 5,
    "coverage": 5,
    "visual_support": 5
  },
  "fidelity_checks": {
    "definitions_taxonomies": {"status": "pass", "notes": "Named definitions, counts and list membership match canonical state."},
    "conditions_boundaries": {"status": "pass", "notes": "Conditions, ranges and exceptions preserve canonical meaning."},
    "relations_order": {"status": "pass", "notes": "Orders, dependencies and distinctions are preserved."},
    "certainty_conflicts": {"status": "pass", "notes": "Confirmed/likely/unknown/excluded and source conflicts are preserved."},
    "assessment_rules": {"status": "not_applicable", "notes": "No assessment/course-rule claim appears in this artifact."},
    "internal_consistency": {"status": "pass", "notes": "Repeated taxonomies, definitions and conditions stay consistent across sections."},
    "example_separation": {"status": "pass", "notes": "Illustrative assumptions remain clearly separate from official rules."}
  },
  "claim_checks": [
    {
      "claim": "Representative high-risk or central claim from the artifact.",
      "canonical_basis": "Canonical concept, rule or source-backed basis supporting that claim.",
      "verdict": "supported"
    }
  ],
  "academic_issues": [],
  "pedagogy_issues": [],
  "visual_issues": [],
  "repair_instructions": []
}
```

Required fidelity-check keys are fixed. `status` is only `pass`, `fail` or `not_applicable`; `not_applicable` needs a concrete reason. At least one representative claim check is required by the current academic evaluation policy. Any unsupported high-risk claim requires a failing review and matching issue/repair instruction.

Handoff files are working state and are not automatically student artifacts.

## Plan visual contract
`02-plan.json` includes a `visuals` section. Each major concept receives `visual_required`, `visual_helpful` or `visual_not_needed`. Every selected entry records `visual_treatment` as exactly `reinterpret`, `preserve` or `preserve+derived_sketch` following `rules/visual/figures.md`.

`source_figure_id` is required for `preserve` and `preserve+derived_sketch`; `fidelity_reason` names the exact pixel-, scale-, notation-, geometry- or layout-sensitive information that requires original pixels. `derived_figure_id` and non-empty `based_on` are required whenever a derived asset will be created. `preserve+derived_sketch` always means two distinct figures.

### Schema 2 selected visual
New derived figures use `scene_spec` under `02-scenes/`:

```json
{
  "concept_id": "stable-concept-id",
  "need": "visual_required",
  "visual_treatment": "reinterpret",
  "derived_figure_id": "derived:process-overview",
  "scene_spec": "02-scenes/process-overview.json",
  "based_on": ["concept:stable-concept-id"],
  "reason": "The spatial composition makes the supported relationship easier to see."
}
```

The scene validates against `contracts/scene-figure.schema.json`. Academic semantics live once in `elements`; `layouts.wide` and `layouts.narrow` may change geometry only. The planner may control composition but never SVG, CSS, exact colors, fonts or raw style properties.

### V2 preview / review / finalize handoff
After PLAN and before DRAFT:

```powershell
python scripts/venv_exec.py scripts/visual_plan_v2.py preview `
  --course <course> --unit <unit-id> `
  --plan <run-dir>/02-plan.json `
  --write <run-dir>/02-visual-preview.json
```

A deterministic preflight failure is preserved under `02-visual-preflight-failures/` and returns no review attempt number. Only scenes that pass preflight are rendered to wide/narrow PNG evidence.

A separate vision-capable reviewer inspects every current wide/narrow PNG and writes `02-visual-review.json` following `contracts/visual-review.schema.json`. The reviewer declaration must state `capability: vision` and `independent: true`. The engine mechanically proves that the review references the current PNG bytes by SHA-256.

A scene gets one initial reviewed attempt. If it fails, repair only that scene once and preview/review the changed evidence one final time. New runs allow at most two reviewable/rendered attempts per scene. There is no third review.

If a scene still fails after attempt 2, remove that visual from the current plan (`visual_not_needed` for this run and no derived scene fields), rerun preview against the updated plan, carry unchanged PASS rows mechanically, and continue. A failed pedagogical illustration is omitted rather than blocking the textual summary. If every V2 scene is omitted, the current preview/review scene sets are both empty and finalization may continue with no V2 scene entries.

After every scene still present in the final plan passes:

```powershell
python scripts/venv_exec.py scripts/visual_plan_v2.py finalize `
  --course <course> --unit <unit-id> `
  --plan <run-dir>/02-plan.json `
  --preview <run-dir>/02-visual-preview.json `
  --review <run-dir>/02-visual-review.json `
  --write <run-dir>/02-visual-build.json
```

Finalization re-renders the surviving SVGs and requires their hashes to equal the reviewed attempt before registration. It preflights every permanent destination before writing and rolls back newly created scene assets if registration fails. The V2 build report records `plan_sha256`, `preview_sha256`, `visual_review_sha256`, `vision_verified: true`, final scene hashes and responsive variant hashes.

DRAFT uses only the exact surviving assets returned by the final build report. The final renderer upgrades wide scene assets to responsive `<picture>` markup using the registered narrow companion. The prose must remain understandable when a visual was omitted.

### Legacy schema 1 handoff
Existing schema-1 specs remain under `02-sketches/` and validate against `contracts/sketch-figure.schema.json`. Legacy flows continue through `scripts/visual_plan.py`; generator identity/output are not migrated merely because V2 exists.

## Final V2 binding
For a V2 run, render accepted Markdown to `09-rendered-base.html`, then apply `scripts/scene_responsive.py` to produce `09-rendered.html`. Validate the final artifact with `scripts/artifact_integrity_v2.py`, which checks the final plan, preview, independent vision review, scene/variant hashes, registered provenance and responsive HTML. Omitted failed scenes are no longer planned visuals and therefore are not required by final integrity.

Then run `scripts/visual_audit_v2.py`, which adds per-scene desktop/mobile crops to the normal browser evidence and records which responsive variant Chromium selected. This is integration QA, not another open-ended visual redesign cycle.

`pipeline_run.py finish` requires exact preview/review hashes, V2 integrity markers and complete browser evidence for every surviving planned V2 scene.

## Plan topic coverage contract
For unit-scoped summaries, `02-plan.json` records which observed topic ids and explicitly unassigned concepts the plan covers. This is an omission check, not a section template.

## Stable unit identity
Human labels such as `U1`, `Unidad 1` and `Unidad 1: Conceptos básicos` are display aliases. Unit-scoped records use stable `unit_id`. Scope concepts/figures by that id, not fuzzy labels.

## Derived figure registration
Derived visuals remain namespaced as `derived:<id>` with `origin: derived`, stable unit ownership, non-empty provenance and collision-safe assets under `assets/figures/`. Source records/assets are never overwritten.

Schema-1 generated records keep their existing `generation` object and hashes. Schema-2 records add `scene_generation` metadata with deterministic scene renderer identity, scene SHA, wide/narrow asset hashes and the reviewed attempt. Existing schema-1 data remains valid unchanged.

`pipeline_run.py start` stores an immutable `01-figures.json` snapshot. Finish rejects source edits/removals and unplanned canonical figure mutations while permitting append-only derived records declared in the final plan/build report.