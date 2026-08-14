# Figures, diagrams and source visuals

A figure is pedagogical content, not decoration.

## Core rule
Use a visual when it makes a spatial, structural, causal, temporal or relational concept easier to understand than prose alone. This is especially important in subjects such as computer architecture, operating systems, networking, databases, electronics, algorithms and mathematics.

Every selected figure must also belong to the shared notebook language:

> Toda figura debe integrarse al lenguaje visual del cuaderno. Las figuras pedagógicas derivadas tienden por defecto a una reinterpretación tipo notebook sketch/lápiz, salvo cuando la fidelidad del contenido requiera preservar el original.

This is a semantic treatment rule, not a blanket image filter. A notebook sketch
must be reconstructed from canonical knowledge and auditable relationships; it
is never an automatic pencil effect applied to arbitrary pixels.

Good candidates include:
- architecture/block diagrams;
- process/state diagrams;
- memory maps and hierarchies;
- timelines and scheduling diagrams;
- flowcharts;
- tables whose structure carries meaning;
- annotated screenshots when the interface itself is being learned;
- graphs, geometric figures and circuit diagrams.

Do **not** include:
- decorative illustrations;
- logos and cover art;
- screenshots that add no instructional information;
- duplicate visuals that say the same thing;
- a dense page image when a clearer source figure or small schematic is available.

## Treatment decision
After deciding that a visual is required or helpful, record exactly one
`visual_treatment` in the plan:

- `reinterpret`: the visual is a pedagogical derivation whose meaning can be
  reconstructed without loss. This is the default for `flow`, `tree`,
  `concept-map`, `relations` and `technical-schematic`, including when a source
  PNG of that diagram already exists. Source availability supplies provenance;
  it does not select the final pixels. Prefer this for flowcharts, trees,
  concept maps, concept relationships, process schematics and other
  explanatory diagrams.
  Use slightly imperfect but crisp pencil-like strokes, manual-looking arrows,
  boxes and annotations, and the current notebook grammar. Labels, direction,
  grouping, order and every academically meaningful relationship must remain
  unambiguous.
- `preserve`: use the precise original/representation because restyling could
  lose information. This is the normal choice for screenshots, dense charts,
  precision-sensitive visual tables, exact plots, formulas, geometry, circuits,
  notation-heavy figures and any visual whose pixels, scale or layout are part
  of the evidence. Every `preserve` decision records a non-empty
  `fidelity_reason` that names the detail that reconstruction could lose.
  Integrate it through placement, plate, caption and nearby handwritten
  accents; never alter the source pixels merely to make them look like pencil.
- `preserve+derived_sketch`: keep the precise source figure and add a separate,
  clearly labelled simplified notebook sketch only when the pair has more
  teaching value than either figure alone. The sketch explains a supported
  mental model; it does not replace, correct or impersonate the source.

When there is a concrete uncertainty about losing exact information, choose
`preserve` and state that uncertainty in `fidelity_reason`. The mere existence
of a source asset is not such a reason. For the five reconstructible sketch
kinds, first test whether all meaningful labels, relations, directions,
groupings and order can be declared in the structured spec; if they can,
`reinterpret` remains the default. Visual character still has lower priority
than academic fidelity and legibility. Do not use `preserve+derived_sketch`
merely to decorate a preserved figure or to satisfy a figure count.

Code, formulas and tables are not literal pencil drawings. Keep their content
exact and integrate them through the shared renderer's borders, captions,
annotations and other notebook details. A simplified diagram derived from them
is allowed only as a separate pedagogical figure with explicit provenance.

## Source-first policy
Prefer a relevant figure from the unit sources when it faithfully represents what the chair teaches. Preserve provenance internally in `unidades/<unit-id>/conocimiento/figures.json`.

`source-first` governs evidence selection, not treatment selection. It must not
automatically override a lossless `reinterpret` decision. A reconstructible
source diagram may be the `figure:<id>` provenance of a new sketch while the
final artifact uses the registered derived SVG rather than the source PNG.

If a source figure is too dense but the concept would benefit from a simpler schematic, a simplified diagram may be created only if every relationship shown is supported by canonical knowledge. Mark its origin as `derived` internally; never imply that a derived diagram came from the chair.

## Selection during PLAN
For every major concept, explicitly decide one of:
- `visual_required`: prose alone would be a poor teaching choice;
- `visual_helpful`: visual adds clear value;
- `visual_not_needed`: prose/example is better.

Do not force a fixed number of figures.

For every `visual_required` or `visual_helpful` decision, also record the
`visual_treatment`. Identify the selected source figure when using `preserve`.
For `preserve+derived_sketch`, identify both the preserved source figure and the
separate derived asset/record. A decision to `reinterpret` must list the
canonical concepts or source figure on which the new visual is based.
`preserve` and `preserve+derived_sketch` also require `fidelity_reason`; a
generic preference for the original or a source-first shortcut is invalid.

## Deterministic sketch generation

Normal pedagogical diagrams selected as `reinterpret` are generated from a
structured sketch spec, never with an image-generation model. The planner
decides what the figure means and contains; deterministic code owns the final
SVG geometry and notebook style.

Supported priorities are flows, trees, concept maps, explicit relationships and
technical schematics. For each selected derived figure:

1. write `02-sketches/<id>.json` using
   `contracts/sketch-figure.schema.json`;
2. declare every node, edge and group with non-empty element-level `based_on`
   references included in the spec's global provenance;
3. use semantic shapes, rank/order and direction only—never colors, fonts,
   pixels or arbitrary SVG;
4. materialize the whole plan with `scripts/visual_plan.py`, which validates the
   decisions and calls the collision-safe sketch generator for every derived
   entry;
5. persist `02-visual-build.json` and verify every planned SVG is registered;
6. only then draft Markdown, referencing the exact `asset` returned by the
   build report.

The command validates, renders and registers in one retry-safe operation. It
stores the normalized spec next to the SVG, records both SHA-256 fingerprints
and embeds generator/spec identity inside the SVG. Equal specs produce equal
bytes. Existing IDs or paths with different content are refused.

The generated SVG is a transparent ink overlay. It must not contain paper,
rules, a full-canvas rectangle, an outer frame, a plate or UI-like solid node
fills; the document theme owns the visible notebook sheet behind it. Nodes and
edges use deterministic double pencil traces with small curved deviations, so
the drawing reads as manual without changing endpoints, labels, direction or
semantic geometry. `sketch_figure.py audit` rejects an opaque canvas, a frame
or node/edge geometry reduced to a single perfectly clean trace.

`preserve` bypasses this generator. `preserve+derived_sketch` requires the
source figure to remain in the artifact and the spec to name the same
`source_figure_id`; the SVG is a separate simplified companion. Screenshots,
dense charts, visual tables, code, formulas, geometry, circuits, exact plots
and any pixel/scale-sensitive representation remain source assets unless a
separate supported sketch adds genuine learning value.

The integrity gate receives `02-plan.json` and fails closed when a planned
`reinterpret` is absent from the final Markdown, when its source asset is used
instead, or when the referenced derived record was not produced by the
deterministic SVG generator. `preserve+derived_sketch` must reference both
registered assets.

## Placement
Corresponding words and images belong together. Put the figure immediately after the paragraph that introduces it, followed by a short **How to read this figure** explanation when needed.

A useful figure block has:
1. a meaningful alt text/caption;
2. the visual;
3. 1–4 sentences telling the learner what relationship to notice;
4. optionally one recall prompt that asks the learner to reconstruct/explain the visual.

Do not describe every pixel. Explain the conceptual relationship the student should extract.

## Truth boundary
Never infer unlabeled components from an unreadable image. If the agent cannot confidently inspect or interpret a source visual, either omit it or state that visual interpretation is unavailable and use supported prose instead.


## On-demand discovery for migrated/older courses
If `unidades/<unit-id>/conocimiento/figures.json` has no relevant entry for the requested scope, do **not** reprocess the whole course. Instead:
1. run `python study.py figures scan <course> --write` if `.study/figure-pages.json` is missing/stale and the visual dependency is available;
2. use concept source references to identify candidate PDF pages for the requested scope;
3. inspect only those candidate pages/figures;
4. register/render only visuals that pass the pedagogical selection rule.

This is a narrow visual-indexing pass, not a reason to reread all transcripts or regenerate canonical text knowledge.


## Stable identity and derived registration
Unit matching is machine based. Use the resolved `unit_id` from `01-input.json`; do not compare strings such as `U1` and `Unidad 1` manually.

When creating a new diagram, save the asset under `assets/figures/` and register it with `python study.py figures register-derived ...`. Derived ids are automatically namespaced `derived:` and registration refuses id/asset collisions. Never directly overwrite a record whose origin is `source`.

New derived registrations should include `visual_treatment`. When the treatment
is `preserve+derived_sketch`, also record `source_figure_id` for the preserved
source companion. These fields are additive: legacy records without them remain
valid, but new plan decisions and generated figures must state the treatment
explicitly.
