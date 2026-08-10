# Portable handoff contracts

All semantic pipeline runs live under:
`materias/<course>/.study/runs/<run-id>/`

`manifest.json` records pipeline, course, scope, timestamps, status and stage files.

## Standard stage files
- `01-input.json`: resolved course/scope, relevant canonical paths/fingerprints, requested mode.
- `02-plan.json`: pedagogical/content plan. No polished prose.
- `03-draft.md`: first student-facing draft.
- `04-humanized.md`: Humanizer output.
- `05-review.json`: independent fidelity + pedagogy review.
- `06-final.md`: accepted candidate when the first review passes.
- `06-repair.md`: targeted repair when the first review fails.
- `07-review.json`: second and final review of the repair.
- `08-final.md`: accepted repaired candidate after the second review.
- `09-rendered.html`: deterministic rendered study surface for the accepted Markdown.
- `10-integrity.json`: deterministic pre-publication gate. Must contain `"ok": true` before the student artifact is published.

Pipelines may omit stages that do not apply, but filenames and semantics must stay stable across Claude and Codex.

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

Required fidelity-check keys are fixed. `status` is only `pass`, `fail` or `not_applicable`; `not_applicable` needs a concrete reason. `claim_checks` must contain the high-risk assertions actually audited (definitions/taxonomies, conditions, relations, certainty/rules and any other risky claim present). Any verdict other than `supported` requires a failing review and a matching issue/repair instruction.

Handoff files are working state and are not automatically student artifacts.

## Plan visual contract
`02-plan.json` should include a `visuals` section for student-facing content. Each major concept receives one of `visual_required`, `visual_helpful`, `visual_not_needed`. Selected source visuals reference ids from `conocimiento/figures.json`; derived diagrams must be explicitly marked derived.

## Stable unit identity
Human labels such as `U1`, `Unidad 1` and `Unidad 1: Conceptos básicos` are display aliases. Unit-scoped canonical records use a stable `unit_id` such as `unidad-1`. Pipeline code must scope concepts/figures by `unit_id`, not by fuzzy comparison of labels.

## Derived figure registration
Derived visuals are namespaced as `derived:<id>` and must include `origin: derived`, `unit_id`, `asset`, and non-empty `based_on` provenance. Registration is collision-safe and must go through `study.py figures register-derived`; source records/assets are never overwritten.
