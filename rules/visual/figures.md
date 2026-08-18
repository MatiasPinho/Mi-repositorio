# Figures, diagrams and source visuals

A figure is pedagogical content, not decoration.

## Core rule
Use a visual when it makes a spatial, structural, causal, temporal, relational or physically recognizable concept easier to understand than prose alone. Do not force a fixed number of figures and do not remove a useful visual merely to save runtime.

Every selected figure must also belong to the shared notebook language:

> Toda figura debe integrarse al lenguaje visual del cuaderno. Las figuras pedagógicas derivadas tienden por defecto a una reinterpretación tipo notebook sketch/lápiz, salvo cuando la fidelidad del contenido requiera preservar el original.

This is a semantic treatment rule, not a blanket image filter.

## First decide the pedagogical need
For every major concept record exactly one:
- `visual_required`: prose alone is a poor teaching choice;
- `visual_helpful`: the visual improves recognition or understanding but the prose still carries the complete academic explanation;
- `visual_not_needed`: prose/example teaches the concept equally well or better.

The decision is pedagogical. `visual_not_needed` is never a shortcut for saving tokens, image calls or implementation work.

## Then choose the representation
Use the smallest representation that teaches the concept correctly.

### `visual_medium: diagram`
Use the deterministic notebook-sketch renderer when the visual itself carries exact academic structure. This includes:
- flows and sequences;
- cycles and state transitions;
- timelines;
- hierarchies and trees;
- concept/relationship maps;
- architecture and subsystem relationships;
- exact labels, order, direction, topology or grouping.

The planner declares semantic nodes, edges, groups and evidence. Carpeta computes the SVG geometry and pencil treatment. The model must not write raw SVG or pixel coordinates.

Existing schema-1 diagrams remain the canonical diagram path through `02-sketches/<id>.json`, `contracts/sketch-figure.schema.json` and `scripts/sketch_figure.py`.

### `visual_medium: illustration`
Use a generated illustration only for a recognizable physical/conceptual likeness where exact topology is not the teaching payload. Good examples are a generic CPU package, RAM module, disk, monitor, keyboard or peripheral.

Illustrations are intentionally **supporting only**:
- an illustration must use `need: visual_helpful`, never `visual_required`;
- it may show only simple visual cues explicitly supported by canonical knowledge;
- it must not encode exact quantities, sequence, wiring, topology, formulas, dates, taxonomies or exam-critical relationships;
- it must contain no requested text, letters, numbers, labels or arrows;
- all authoritative labels and explanations stay in prose/HTML or a deterministic diagram;
- never generate the whole study page as an image.

The planner supplies only a compact semantic illustration spec: subject, view, supported visible cues, alt/caption and provenance. Carpeta owns the fixed pencil-style prompt, provider call, timeout, crop, white-background removal, transparent notebook overlay and registration. The planner never writes a long image prompt.

When the same concept benefits from physical recognition **and** an exact relationship diagram, both may be used: the illustration provides recognition; the diagram carries the academic structure.

### Source figure
Use the source pixels when reconstruction risks losing evidence. Screenshots, dense charts, precision-sensitive tables, exact plots, formulas, geometry, circuits and notation-heavy figures normally stay source assets.

## Treatment decision
After selecting a visual, record exactly one `visual_treatment`:
- `reinterpret`: a derived diagram or supporting illustration reconstructed from canonical knowledge;
- `preserve`: keep the precise source representation; requires a concrete `fidelity_reason`;
- `preserve+derived_sketch`: keep the precise source and add a separate deterministic diagram when the pair teaches more than either alone. The derived companion is always `visual_medium: diagram`.

`source-first` selects evidence, not final pixels. A source diagram that can be reconstructed without loss may still use `reinterpret`. Never imply that a derived visual came from the chair.

## Hybrid materialization
The summary pipeline materializes selected visuals with `scripts/visual_plan_hybrid.py`.

For diagrams:
1. write the compact schema-1 spec under `02-sketches/`;
2. validate it;
3. generate/register the deterministic transparent SVG;
4. use the exact asset returned by `02-visual-build.json`.

For illustrations:
1. declare the compact inline `illustration` spec in `02-plan.json`;
2. make one bounded provider call;
3. deterministically crop and remove the white working canvas;
4. wrap the raster as a transparent notebook overlay and register it under `assets/figures/`;
5. use the exact asset returned by `02-visual-build.json`.

No independent per-image vision-review loop is part of this path. The speed boundary is deliberate: generated illustrations are not allowed to carry authoritative academic structure. The normal academic review, integrity gate and final browser audit still apply to the document.

If the illustration provider is unavailable, do not retry repeatedly. Make at most one plan fallback for that failed visual: switch it to a deterministic diagram when the same supported meaning is naturally diagrammable, otherwise omit that optional illustration for the current run. Do not reduce academic text quality.

## Style and integration
Derived diagrams and illustrations must look like marks made on the actual notebook page, not pasted cards. Deterministic diagrams use transparent SVG. Generated illustrations are postprocessed into transparent overlays so the real paper/rules remain visible behind them.

A generated illustration should normally be isolated, simple and recognizable. Exact annotation belongs outside the pixels. Captions explain why the visual is useful rather than narrating every pixel.

## Truth boundary
Visual character always loses to academic fidelity. Never invent internal parts merely to make a drawing richer. If the evidence supports only a high-level component, show only a high-level recognizable form. Never infer unlabeled components from an unreadable source image.

## Stable identity and provenance
Use the resolved stable `unit_id`. Derived ids remain namespaced `derived:<id>` and source figures/assets are never overwritten. Every derived visual has non-empty `based_on` provenance and collision-safe registration. Diagram records retain deterministic generator/spec hashes; generated illustrations retain provider/model, semantic-spec hash, prompt hash and final asset hash without storing credentials.
