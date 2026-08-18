# Hybrid visual contract

This contract is the active visual handoff for `pipelines/resumen.md`.

## Responsibility boundary

Carpeta chooses the execution backend from semantic intent; the study model does not author raw SVG, page geometry or image-provider prompts.

- `diagram` = exact structure that must remain academically auditable: flows, cycles, timelines, hierarchies, state changes, architectures, buses, relationships, algorithms and other topology/order-bearing content.
- `illustration` = optional recognition support for a physical or visually recognizable subject: CPU package, RAM module, disk, keyboard, monitor, printer, generic device or similar object.
- `source` = preserve an original source figure when its precise pixels/layout carry evidence that reconstruction could lose.

Generated illustration pixels are never authoritative academic evidence. A concept that is `visual_required` must use a deterministic diagram or preserved source, never a generated illustration.

## Plan row

Every major concept still declares one of:

- `visual_required`
- `visual_helpful`
- `visual_not_needed`

Every selected visual declares `visual_treatment`, `reason` and provenance.

### Deterministic diagram

Use `visual_medium: "diagram"` and the existing compact schema-1 sketch spec under `02-sketches/`.

```json
{
  "concept_id": "instruction-cycle",
  "need": "visual_required",
  "visual_treatment": "reinterpret",
  "visual_medium": "diagram",
  "reason": "The order and loop are part of the concept.",
  "derived_figure_id": "instruction-cycle",
  "based_on": ["concept:instruction-cycle"],
  "sketch_spec": "02-sketches/instruction-cycle.json"
}
```

The existing `scripts/visual_plan.py` / deterministic SVG backend remains the diagram implementation. The model supplies compact semantic graph structure, not explicit coordinates or scene-graph geometry.

### Generated illustration

Use `visual_medium: "illustration"` only with `need: "visual_helpful"` and `visual_treatment: "reinterpret"`.

```json
{
  "concept_id": "cpu",
  "need": "visual_helpful",
  "visual_treatment": "reinterpret",
  "visual_medium": "illustration",
  "reason": "A recognizable package gives the learner a physical mental image.",
  "derived_figure_id": "cpu-package",
  "based_on": ["concept:cpu"],
  "illustration": {
    "schema_version": 1,
    "id": "cpu-package",
    "subject": "generic computer microprocessor package",
    "view": "top-down",
    "must_show": [
      "square integrated-circuit package",
      "visible pins around the package"
    ],
    "alt": "Dibujo a lápiz de un microprocesador visto desde arriba.",
    "caption": "Representación física simplificada de un microprocesador.",
    "based_on": ["concept:cpu"]
  }
}
```

Allowed illustration fields are exactly `schema_version`, `id`, `subject`, `view`, `must_show`, `alt`, `caption`, `based_on`. There is intentionally no free-form provider prompt field. Carpeta owns style, negative constraints, model selection, seed, timeout, crop and transparency.

## Generated-pixel truth boundary

An illustration must not be asked to encode or teach exact:

- labels or prose;
- numbers, dates or quantities;
- arrows or directional topology;
- formulas or notation;
- chronology;
- component relationships whose correctness matters;
- implementation internals unsupported by canonical knowledge.

If any of those are pedagogically necessary, use `diagram` or `source`.

## Runtime boundary

- One provider request per new illustration spec.
- Exact registered spec/asset reuse performs zero provider calls.
- Provider timeout is bounded by deterministic code.
- No per-illustration vision-review/regeneration loop.
- If the provider is unavailable, the planner may make at most one run-local fallback: use a deterministic diagram only when the same supported meaning is naturally diagrammable; otherwise omit that optional illustration for the current run and continue.
- Failure of an optional illustration never weakens or blocks the textual academic summary.

## Output

`scripts/visual_plan_hybrid.py` materializes all selected rows and writes `02-visual-build.json`.

Generated illustrations are cropped, white-keyed to transparency and registered as SVG notebook overlays. The page, ruled paper, typography, captions, tables and code remain real Carpeta HTML/CSS; generated pixels never become a screenshot of the page.
