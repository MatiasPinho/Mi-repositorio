# Portable handoff contracts

Unit-scoped semantic pipeline runs live under:
`materias/<course>/unidades/<unit-id>/.study/runs/<run-id>/`

Only genuinely course-wide runs may live under
`materias/<course>/.study/runs/<run-id>/`.

`manifest.json` records pipeline, course, scope, timestamps, status and stage files.

## Standard stage files
- `01-input.json`: resolved course/scope, relevant canonical paths/fingerprints, requested mode.
- `02-plan.json`: pedagogical/content plan. No polished prose.
- `02-sketches/<id>.json`: compact schema-1 structured specs for deterministic graph SVGs.
- `02-fidelity-constraints.json`: deterministic high-risk/split-view/unresolved claim ledger for summaries.
- `02-visual-build.json`: deterministic hybrid materialization report binding the current plan to exact registered assets before drafting.
- `03-draft.md`: first student-facing draft.
- `04-humanized.md`: Humanizer output.
- `04-fidelity-guard.json`: deterministic wording guard for unresolved/split-view constraints.
- `05-review.json`: independent academic fidelity + pedagogy review; `visual_support` evaluates visual selection/fit/truth.
- `06-final.md`: accepted candidate when the first review passes.
- `06-repair.md`: targeted repair when the first review fails.
- `07-review.json`: second and final review of the repair.
- `08-final.md`: accepted repaired candidate after the second review.
- `09-rendered-base.html`: optional intermediate produced by the normal Markdown renderer before deterministic code highlighting.
- `09-code-highlight.json`: deterministic code-highlighting report when the summary contains highlighted code/pseudocode.
- `09-rendered.html`: deterministic final rendered study surface for the accepted Markdown.
- `10-integrity.json`: deterministic pre-publication gate. Must contain `"ok": true` before publication.
- `11-publication.json`: atomic publication report binding source and published Markdown/HTML.
- `12-runtime.json`: deterministic stage timing report.

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

The active summary path also records `visual_medium`:
- `diagram` for deterministic exact structure;
- `illustration` for optional generated physical/recognition support;
- `source` is inferred for `preserve`.

Full field-level rules and examples live in `contracts/hybrid-visuals.md`.

### Diagram handoff
A deterministic diagram uses a schema-1 spec under `02-sketches/` and validates against `contracts/sketch-figure.schema.json`.

```json
{
  "concept_id": "instruction-cycle",
  "need": "visual_required",
  "visual_treatment": "reinterpret",
  "visual_medium": "diagram",
  "derived_figure_id": "derived:instruction-cycle",
  "sketch_spec": "02-sketches/instruction-cycle.json",
  "based_on": ["concept:instruction-cycle"],
  "reason": "The cycle/order is part of the concept."
}
```

The existing `scripts/visual_plan.py` deterministic generator remains the diagram backend. The model supplies compact semantic nodes/edges/groups, not raw SVG or explicit free-layout coordinates.

### Illustration handoff
A generated illustration is valid only for `visual_helpful` + `reinterpret`.

```json
{
  "concept_id": "cpu",
  "need": "visual_helpful",
  "visual_treatment": "reinterpret",
  "visual_medium": "illustration",
  "derived_figure_id": "derived:cpu-package",
  "based_on": ["concept:cpu"],
  "reason": "A physical mental image helps recognition.",
  "illustration": {
    "schema_version": 1,
    "id": "cpu-package",
    "subject": "generic computer microprocessor package",
    "view": "top-down",
    "must_show": ["square integrated-circuit package", "visible pins around the package"],
    "alt": "Dibujo a lápiz de un microprocesador visto desde arriba.",
    "caption": "Representación física simplificada de un microprocesador.",
    "based_on": ["concept:cpu"]
  }
}
```

There is no free-form image-provider prompt in the handoff. Carpeta owns style, negative prompt constraints, provider/model, deterministic seed, timeout, white-canvas cleanup and transparent notebook integration.

Generated pixels never carry authoritative labels, numbers, arrows, chronology, formulas or topology. Exact academic content stays in prose, deterministic diagrams or preserved source figures.

## Hybrid materialization handoff
After PLAN/fidelity constraints and before DRAFT:

```powershell
python scripts/venv_exec.py scripts/visual_plan_hybrid.py `
  --course <course> --unit <unit-id> `
  --plan <run-dir>/02-plan.json `
  --write <run-dir>/02-visual-build.json
```

The build report must bind `plan_sha256` and every selected visual to the exact registered asset/hash. Deterministic diagrams remain collision-safe/idempotent. Generated illustrations are also collision-safe/idempotent and reuse an exact already-registered semantic spec without a provider call.

If an illustration provider is unavailable, the report does not silently continue as if the image existed. The executor may make at most one run-local fallback decision for that optional visual, update the plan, and rerun the materializer once. A deterministic/registry/engine failure remains a real run failure.

DRAFT uses only assets present in the final successful build report.

## Final hybrid binding
Render accepted Markdown with the normal Carpeta renderer so the branch's notebook typography, hand-drawn structures, figures and page styling remain intact. Apply deterministic code highlighting when required, then validate with `scripts/artifact_integrity.py --plan <run-dir>/02-plan.json`.

The integrity gate checks that `reinterpret` uses the planned derived asset, `preserve` uses the planned source, `preserve+derived_sketch` uses both, and generated illustration records carry the generated-illustration metadata expected by `scripts/visual_plan_hybrid.py`.

Run `scripts/visual_audit.py` on the final HTML for desktop/mobile integration. Generated illustrations are not given a separate review/regeneration loop; a visibly invalid optional illustration is omitted rather than repeatedly regenerated.

## Legacy V2 compatibility
Historical schema-2 scene files, preview/review/finalizer evidence and V2 scripts remain readable/testable. They are not the default or required handoff for new `/resumen` visuals. Existing registered V2 records remain immutable; the hybrid migration does not rewrite them.

## Plan topic coverage contract
For unit-scoped summaries, `02-plan.json` records which observed topic ids and explicitly unassigned concepts the plan covers. This is an omission check, not a section template.

## Stable unit identity
Human labels such as `U1`, `Unidad 1` and `Unidad 1: Conceptos básicos` are display aliases. Unit-scoped records use stable `unit_id`. Scope concepts/figures by that id, not fuzzy labels.

## Derived figure registration
Derived visuals remain namespaced as `derived:<id>` with `origin: derived`, stable unit ownership, non-empty provenance and collision-safe assets under `assets/figures/`. Source records/assets are never overwritten.

Schema-1 diagram records keep their existing `generation` object and hashes. Generated illustration records use `illustration_generation` with semantic spec/style/provider metadata and final transparent-overlay hash. Existing schema-1 and schema-2 data remains valid unchanged.

`pipeline_run.py start` stores an immutable `01-figures.json` snapshot. Finish rejects source edits/removals and unplanned canonical figure mutations while permitting append-only derived records declared in the final plan/build report.
