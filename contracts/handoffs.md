# Portable handoff contracts

Unit-scoped semantic pipeline runs live under:
`materias/<course>/unidades/<unit-id>/.study/runs/<run-id>/`

Only genuinely course-wide runs may live under
`materias/<course>/.study/runs/<run-id>/`.

`manifest.json` records pipeline, course, scope, timestamps, status and stage files.

## Standard stage files
- `01-input.json`: resolved course/scope, relevant canonical paths/fingerprints, requested mode.
- `02-plan.json`: pedagogical/content plan. No polished prose.
- `02-sketches/<id>.json`: optional structured specs for deterministic derived SVGs selected by the plan.
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
`02-plan.json` should include a `visuals` section for student-facing content. Each major concept receives one of `visual_required`, `visual_helpful`, `visual_not_needed`. Every required/helpful entry also records `visual_treatment` as exactly `reinterpret`, `preserve` or `preserve+derived_sketch`, following `rules/visual/figures.md`. Selected source visuals reference ids from `unidades/<unit-id>/conocimiento/figures.json`; derived visuals must be explicitly marked derived.

For the reconstructible kinds `flow`, `tree`, `concept-map`, `relations` and
`technical-schematic`, `reinterpret` is the default even when the canonical
source registry already contains a PNG. `source-first` selects evidence and
provenance; it never selects `preserve` by itself. A `preserve` or
`preserve+derived_sketch` entry must include a separate non-empty
`fidelity_reason` naming the exact pixel-, scale-, notation-, geometry- or
layout-sensitive information that requires the original. This keeps preserve
available for screenshots, dense charts, formulas, geometry, circuits, exact
plots and other precision-sensitive content without turning source reuse into
an automatic fallback.

Minimum shape for a selected visual:

```json
{
  "concept_id": "stable-concept-id",
  "need": "visual_required",
  "visual_treatment": "preserve+derived_sketch",
  "source_figure_id": "u2-source-process",
  "derived_figure_id": "derived:u2-process-overview",
  "sketch_spec": "02-sketches/u2-process-overview.json",
  "based_on": ["concept:stable-concept-id", "figure:u2-source-process"],
  "reason": "The pair connects the exact evidence to a simpler mental model.",
  "fidelity_reason": "The source contains scale-dependent measurements that the sketch intentionally omits."
}
```

`source_figure_id` is required for `preserve` and
`preserve+derived_sketch`; `derived_figure_id` and non-empty `based_on` are
required whenever a derived asset will be created. `preserve+derived_sketch`
means two distinct figures are retained, never one source image overwritten by
an artistic derivative. `fidelity_reason` is required whenever source pixels
are retained; the general pedagogical `reason` does not substitute for it.

A derived `reinterpret` also chooses `visual_medium`:
- `diagram` (default when omitted for backward compatibility): exact structure is carried by a compact deterministic sketch spec;
- `illustration`: a supporting physical/conceptual likeness generated from a compact semantic spec.

`preserve+derived_sketch` always uses `visual_medium: diagram`. Source assets never become generated illustrations.

For a **diagram** `reinterpret` and for `preserve+derived_sketch`, the visual entry includes
`sketch_spec`, a run-relative path under `02-sketches/`. The referenced JSON
must validate against `contracts/sketch-figure.schema.json`. The planner owns
labels, node/edge identity, semantic shapes, relationships, groups, rank/order
and element-level `based_on` references. It must not emit SVG, pixels, colors,
fonts or free-form drawing instructions. `preserve` never has a sketch spec.

Diagram example:

```json
{
  "concept_id": "stable-concept-id",
  "need": "visual_required",
  "visual_treatment": "reinterpret",
  "visual_medium": "diagram",
  "derived_figure_id": "derived:process-overview",
  "sketch_spec": "02-sketches/process-overview.json",
  "based_on": ["concept:stable-concept-id"],
  "reason": "The process can be reconstructed without losing any relation."
}
```

An **illustration** `reinterpret` is allowed only when recognition adds value while prose carries the complete academic explanation. It must use `need: visual_helpful`, must not have `sketch_spec`, and uses this compact semantic shape:

```json
{
  "concept_id": "cpu-package",
  "need": "visual_helpful",
  "visual_treatment": "reinterpret",
  "visual_medium": "illustration",
  "derived_figure_id": "derived:cpu-package",
  "based_on": ["concept:cpu-package"],
  "reason": "A recognizable physical form helps connect the term to the hardware object.",
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

`illustration.id` must match `derived_figure_id` and illustration provenance must match the plan. Generated pixels never carry authoritative labels, arrows, counts, sequence, topology, formulas, dates or assessment-critical facts. The provider prompt is not a handoff: Carpeta constructs it from the semantic spec plus the fixed notebook style. Credentials never appear in the plan, registry or artifact.

After PLAN, run the hybrid materializer before DRAFT:

```powershell
python scripts/venv_exec.py scripts/visual_plan_hybrid.py `
  --course <course> --unit <unit-id> `
  --plan <run-dir>/02-plan.json `
  --write <run-dir>/02-visual-build.json
```

The hybrid materializer delegates diagram entries to the existing deterministic `scripts/visual_plan.py` / sketch generator and adds only the bounded illustration path.

`02-visual-build.json` contains `plan_sha256` plus one entry per selected
visual and records the exact registered `asset`; derived entries also record
the derived id and `visual_medium`. Deterministic diagram entries retain generator/spec hashes. Illustration identity is retained in the registry through its semantic-spec hash, provider/model and final asset hash. DRAFT must use these assets rather than a planned placeholder or the source companion of a `reinterpret` entry.

If an illustration provider is unavailable, do not retry repeatedly. The executor makes at most one fallback plan edit for that optional visual: switch to a deterministic diagram only when the same supported meaning is naturally diagrammable, otherwise mark that optional illustration `visual_not_needed` for the current run. Academic text quality cannot be reduced to preserve an illustration.

The final integrity gate must receive this same `02-plan.json`. It fails when a
planned diagram `reinterpret` does not use its registered deterministic SVG,
when a planned illustration does not use its registered `kind: illustration`
asset with `illustration_generation.method: generated-illustration`, when a
source asset named as reinterpret provenance appears in its place, or when a
planned `preserve+derived_sketch` does not use both figures.

## Plan topic coverage contract
For unit-scoped summaries, `02-plan.json` should record which observed topic ids
and explicitly unassigned concepts the plan covers. This is an omission check,
not a section template: several topics may share a section, one topic may need
several sections, and neither topic count nor declared syllabus count imposes a
fixed length.

## Stable unit identity
Human labels such as `U1`, `Unidad 1` and `Unidad 1: Conceptos básicos` are display aliases. Unit-scoped canonical records use a stable `unit_id` such as `unidad-1`. Pipeline code must scope concepts/figures by `unit_id`, not by fuzzy comparison of labels.

The stable id is also the storage boundary. A unit handoff may read explicit
cross-unit prerequisite records, but it writes artifacts, assets and run state
only under its own `unidades/<unit-id>/` directory.

## Derived figure registration
Derived visuals are namespaced as `derived:<id>` and must include `origin: derived`, `unit_id`, `asset`, and non-empty `based_on` provenance. Registration is collision-safe; source records/assets are never overwritten.

The registry accepts additive optional `visual_treatment` metadata with the
same three values as the plan. New generated figures should record it. A
`preserve+derived_sketch` derived record also requires `source_figure_id`, which
must identify an existing source-origin figure in the same registry. Legacy
records without either field remain valid for backward compatibility.
`reinterpret` belongs to a derived record; `preserve` belongs to a source
record; and `preserve+derived_sketch` belongs to the derived companion while
the linked source remains unchanged.

Figures produced by the deterministic sketch generator also contain a
`generation` object with `method: deterministic-svg`, generator identity and
version, the canonical `.sketch.json` asset and its SHA-256. The SVG embeds the
same spec hash. Registry verification and the artifact integrity gate reject a
modified spec, modified SVG, mismatched ID, missing generator marker or asset
outside `assets/figures/`. Exact retries are idempotent; an existing ID/path
with different bytes is never overwritten.

Generated illustrations use a separate `illustration_generation` object with `method: generated-illustration`, generator/style version, semantic-spec path/hash, provider/model identity, deterministic seed, prompt hash and postprocessing identity. The final asset SHA-256 remains on the figure record. Secrets are never persisted. This separate metadata family prevents an illustration from masquerading as a deterministic diagram.

`pipeline_run.py start` stores an immutable `01-figures.json` snapshot. Finish
still rejects any source-figure edit/removal or unplanned registry mutation,
but permits append-only derived records whose ids and treatments match the
plan and `02-visual-build.json`. This is the only canonical-input mutation a
summary run may introduce.
