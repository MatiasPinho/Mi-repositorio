# Portable handoff contracts

Unit-scoped semantic pipeline runs live under:
`materias/<course>/unidades/<unit-id>/.study/runs/<run-id>/`

Only genuinely course-wide runs may live under
`materias/<course>/.study/runs/<run-id>/`.

`manifest.json` records pipeline, course, scope, timestamps, status and stage files.

## Standard stage files
- `01-input.json`: resolved course/scope, relevant canonical paths/fingerprints, requested mode.
- `02-plan.json`: pedagogical/content plan. No polished prose.
- `02-sketches/<id>.json`: optional structured specs for deterministic derived diagrams selected by the plan.
- `02-visual-build.json`: materialization report binding the plan to registered figure assets before drafting.
- `03-draft.md`: first student-facing draft.
- `04-humanized.md`: Humanizer output.
- `05-review.json`: independent fidelity + pedagogy review.
- `06-final.md`: accepted candidate when the first review passes.
- `06-repair.md`: targeted repair when the first review fails.
- `07-review.json`: second and final review of the repair.
- `08-final.md`: accepted repaired candidate after the second review.
- `09-rendered.html`: deterministic rendered study surface for the accepted Markdown.
- `10-integrity.json`: deterministic pre-publication gate. Must contain `"ok": true` before the student artifact is published.

Pipelines may omit stages that do not apply, but filenames and semantics must stay stable across providers.

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
      "claim": "A representative high-risk claim from the candidate.",
      "canonical_basis": "Canonical concept/rule/evidence used to verify it.",
      "verdict": "supported"
    }
  ],
  "academic_issues": [],
  "pedagogy_issues": [],
  "visual_issues": [],
  "repair_instructions": []
}
```

Required fidelity-check keys are fixed. `status` is only `pass`, `fail` or `not_applicable`; `not_applicable` needs a concrete reason. `claim_checks` contains the high-risk assertions actually audited. Any verdict other than `supported` requires a failing review and a matching issue/repair instruction.

Handoff files are working state and are not automatically student artifacts.

## Plan visual contract
`02-plan.json` includes a `visuals` section for student-facing content. Each major concept receives one of `visual_required`, `visual_helpful`, `visual_not_needed`. A selected visual also records `visual_treatment` as exactly `reinterpret`, `preserve` or `preserve+derived_sketch` following `rules/visual/figures.md`.

`preserve` and `preserve+derived_sketch` require `source_figure_id` plus a non-empty `fidelity_reason` naming the exact information that reconstruction could lose. `source-first` selects evidence/provenance; it does not automatically select source pixels.

A derived `reinterpret` also records `visual_medium`:
- `diagram` (default for backward compatibility): exact structure is carried by a compact schema-1 deterministic sketch spec;
- `illustration`: a non-authoritative physical/conceptual likeness generated from a compact semantic spec.

`preserve+derived_sketch` always uses `visual_medium: diagram`. Source assets never become generated illustrations.

### Deterministic diagram example
```json
{
  "concept_id": "instruction-cycle",
  "need": "visual_required",
  "visual_treatment": "reinterpret",
  "visual_medium": "diagram",
  "derived_figure_id": "derived:instruction-cycle",
  "sketch_spec": "02-sketches/instruction-cycle.json",
  "based_on": ["concept:instruction-cycle"],
  "reason": "Order and feedback are easier to learn as an explicit cycle."
}
```

The referenced `sketch_spec` validates against `contracts/sketch-figure.schema.json`. The planner owns labels, node/edge identity, semantic shapes, relationships, groups, rank/order and element-level provenance. It never emits raw SVG, arbitrary pixel geometry, local colors or fonts.

### Generated illustration example
```json
{
  "concept_id": "cpu-package",
  "need": "visual_helpful",
  "visual_treatment": "reinterpret",
  "visual_medium": "illustration",
  "derived_figure_id": "derived:cpu-package",
  "based_on": ["concept:cpu-package"],
  "reason": "A recognizable physical form helps connect the abstract term to the hardware object.",
  "illustration": {
    "schema_version": 1,
    "id": "cpu-package",
    "subject": "generic computer microprocessor package",
    "view": "top-down",
    "must_show": ["square integrated-circuit package", "visible pins around the package"],
    "alt": "Dibujo a lápiz de un microprocesador visto desde arriba.",
    "caption": "Representación física simplificada de un microprocesador.",
    "based_on": ["concept:cpu-package"]
  }
}
```

Illustration constraints are structural, not suggestions:
- `need` must be `visual_helpful`;
- `visual_treatment` must be `reinterpret`;
- `illustration.id` must match `derived_figure_id`;
- `illustration.based_on` must match plan provenance;
- no `sketch_spec` is present;
- the generated pixels are not allowed to carry exact labels, arrows, counts, sequence, topology, formulas, dates or assessment-critical facts.

The provider prompt is not a handoff. Carpeta constructs it deterministically from the small semantic illustration spec plus its fixed notebook style. Credentials never appear in the plan, registry or generated artifact.

## Visual build handoff
After PLAN, `/resumen` runs the hybrid materializer:

```powershell
python scripts/venv_exec.py scripts/visual_plan_hybrid.py `
  --course <course> --unit <unit-id> `
  --plan <run-dir>/02-plan.json `
  --write <run-dir>/02-visual-build.json
```

The existing `scripts/visual_plan.py` / deterministic sketch behavior remains the diagram backend and compatibility contract; the hybrid materializer delegates diagram rows to it and adds the bounded illustration path.

`02-visual-build.json` contains `plan_sha256` plus one entry per selected visual and the exact registered asset. Derived entries record the derived id and `visual_medium`; deterministic diagrams retain generator/spec hashes, while illustrations retain the semantic-spec hash and model identity through the figure registry. DRAFT uses only assets returned by this build.

If a generated illustration provider is unavailable, the build returns `ok: false` plus `illustration_unavailable`. The executor makes at most one fallback edit for each failed optional illustration: use a deterministic diagram if the supported meaning is naturally diagrammable, otherwise make it `visual_not_needed` for that run. Do not repeatedly retry the image provider and do not weaken the academic text.

## Final visual integrity
The final integrity gate receives the same `02-plan.json` and verifies the actual registered assets used by the Markdown:
- a planned diagram reinterpretation uses a registered `deterministic-svg` figure;
- a planned illustration uses a registered `kind: illustration` figure with `illustration_generation.method: generated-illustration`;
- a planned source preservation uses the source asset;
- `preserve+derived_sketch` uses both source and derived diagram.

Generated illustrations have low semantic authority by design; normal academic review must not treat pixels as evidence for a factual claim. The final browser audit still verifies that all images decode and that placement, sizing and document integration remain readable.

## Plan topic coverage contract
For unit-scoped summaries, `02-plan.json` records which observed topic ids and explicitly unassigned concepts the plan covers. This is an omission check, not a section template: several topics may share a section, one topic may need several sections, and neither topic count nor declared syllabus count imposes a fixed length.

## Stable unit identity
Human labels such as `U1`, `Unidad 1` and `Unidad 1: Conceptos básicos` are display aliases. Unit-scoped canonical records use a stable `unit_id` such as `unidad-1`. Pipeline code scopes concepts/figures by `unit_id`, not fuzzy labels.

The stable id is also the storage boundary. A unit handoff may read explicit cross-unit prerequisite records, but it writes artifacts, assets and run state only under its own `unidades/<unit-id>/` directory.

## Derived figure registration
Derived visuals are namespaced as `derived:<id>` and include `origin: derived`, `unit_id`, `asset`, asset SHA-256 and non-empty `based_on` provenance. Registration is collision-safe; source records/assets are never overwritten.

Deterministic diagrams retain a `generation` object with `method: deterministic-svg`, generator identity/version and canonical spec hash. Generated illustrations retain a separate `illustration_generation` object with `method: generated-illustration`, generator/style version, semantic-spec hash, provider/model identity, deterministic seed, prompt hash and postprocessing metadata. Secrets are never persisted.

`pipeline_run.py start` stores an immutable `01-figures.json` snapshot. Finish rejects source-figure edit/removal or unplanned registry mutation, but permits append-only derived records whose ids and treatments match the plan and `02-visual-build.json`.
