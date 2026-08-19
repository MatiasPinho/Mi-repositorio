# Hybrid visual contract

This contract is the active visual handoff for `pipelines/resumen.md`.

## Responsibility boundary

Carpeta chooses the execution backend from semantic intent; the study model does not author raw SVG, page geometry or image-provider prompts.

- `diagram` = exact structure that must remain academically auditable: flows, cycles, timelines, hierarchies, state changes, architectures, buses, relationships, algorithms and other topology/order-bearing content.
- `illustration` = optional recognition support for a physical or visually recognizable subject: CPU package, RAM module, disk, keyboard, monitor, printer, generic device or similar object.
- Source figures are evidence/provenance only in `/resumen`. Their raw pixels are never a publishable summary visual.

Every selected summary visual uses `visual_treatment: "reinterpret"` and must materialize as an `origin: derived` asset. `preserve` and `preserve+derived_sketch` are not valid selected treatments for this pipeline.

Generated illustration pixels are never authoritative academic evidence. A concept that is `visual_required` must use a deterministic diagram. If exact source pixels would be required to remain truthful and the meaning cannot be reconstructed safely, select `visual_not_needed` and teach that meaning in prose instead of pasting the source image.

## Plan row

Every major concept still declares one of:

- `visual_required`
- `visual_helpful`
- `visual_not_needed`

Every selected visual declares `visual_treatment: "reinterpret"`, `reason` and provenance. A source figure may appear only as a `figure:<id>` reference inside `based_on`; `source_figure_id` is not allowed for selected summary visuals.

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

When a source figure informs the reconstruction, retain provenance without publishing the source pixels:

```json
{
  "concept_id": "architecture",
  "need": "visual_required",
  "visual_treatment": "reinterpret",
  "visual_medium": "diagram",
  "reason": "The architecture can be reconstructed without losing the relationships being taught.",
  "derived_figure_id": "architecture-overview",
  "based_on": ["concept:architecture", "figure:u1-source-architecture"],
  "sketch_spec": "02-sketches/architecture-overview.json"
}
```

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

If any of those are pedagogically necessary, use `diagram`. If a truthful diagram cannot preserve the required meaning without depending on exact source pixels, use `visual_not_needed` for the visual and preserve the supported meaning in prose.

## Runtime boundary

- One provider request per new illustration spec.
- Exact registered spec/asset reuse performs zero provider calls.
- Provider timeout is bounded by deterministic code.
- No per-illustration vision-review/regeneration loop.
- If the provider is unavailable, the planner may make at most one run-local fallback: use a deterministic diagram only when the same supported meaning is naturally diagrammable; otherwise omit that optional illustration for the current run and continue.
- Failure of an optional illustration never weakens or blocks the textual academic summary.

## Output

`scripts/visual_plan_hybrid.py` materializes all selected rows and writes `02-visual-build.json`.

Every materialized summary figure is derived: deterministic diagrams are notebook-style SVGs and generated illustrations are cropped, white-keyed to transparency and registered as SVG notebook overlays. The page, ruled paper, typography, captions, tables and code remain real Carpeta HTML/CSS; generated pixels never become a screenshot of the page. Any source-origin figure referenced by the final summary is an integrity failure.
