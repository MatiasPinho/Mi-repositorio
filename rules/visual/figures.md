# Figures, diagrams and source visuals

A figure is pedagogical content, not decoration.

## Core rule
Use a visual when it makes a spatial, structural, causal, temporal, relational or physically recognizable concept easier to understand than prose alone. This is especially important in subjects such as computer architecture, operating systems, networking, databases, electronics, algorithms and mathematics.

Every selected figure must also belong to the shared notebook language:

> Toda figura debe integrarse al lenguaje visual del cuaderno. Las figuras pedagógicas derivadas tienden por defecto a una reinterpretación tipo notebook sketch/lápiz, salvo cuando la fidelidad del contenido requiera preservar el original.

This is a semantic treatment rule, not a blanket image filter. A notebook sketch or illustration must be reconstructed from canonical knowledge and auditable provenance; it is never an automatic pencil effect applied to arbitrary pixels.

Good candidates include:
- architecture/block diagrams;
- process/state diagrams;
- memory maps and hierarchies;
- timelines and scheduling diagrams;
- flowcharts;
- tables whose structure carries meaning;
- annotated screenshots when the interface itself is being learned;
- graphs, geometric figures and circuit diagrams;
- simple recognizable physical objects when visual recognition adds learning value.

Do **not** include:
- decorative illustrations;
- logos and cover art;
- screenshots that add no instructional information;
- duplicate visuals that say the same thing;
- a dense page image when a clearer source figure or small schematic is available;
- generated illustrations that carry exact academic relationships, labels or quantities.

## Selection during PLAN
For every major concept, explicitly decide one of:
- `visual_required`: prose alone would be a poor teaching choice;
- `visual_helpful`: visual adds clear value while the prose still carries the complete explanation;
- `visual_not_needed`: prose/example is better.

Do not force a fixed number of figures. The decision is pedagogical: `visual_not_needed` is never a shortcut for saving tokens, image calls, review work or runtime.

For every `visual_required` or `visual_helpful` decision, also record the `visual_treatment`. Identify the selected source figure when using `preserve`. For `preserve+derived_sketch`, identify both the preserved source figure and the separate derived asset/record. A decision to `reinterpret` must list the canonical concepts or source figure on which the new visual is based. `preserve` and `preserve+derived_sketch` also require `fidelity_reason`; a generic preference for the original or a source-first shortcut is invalid.

## Treatment decision
After deciding that a visual is required or helpful, record exactly one `visual_treatment` in the plan:

- `reinterpret`: the visual is a pedagogical derivation whose meaning can be reconstructed without loss. This remains the default for exact flows, trees, concept maps, relations and technical schematics. A supporting generated illustration may also use `reinterpret` only under the strict illustration boundary below.
- `preserve`: use the precise original/representation because restyling could lose information. This is the normal choice for screenshots, dense charts, precision-sensitive visual tables, exact plots, formulas, geometry, circuits, notation-heavy figures and any visual whose pixels, scale or layout are part of the evidence. Every `preserve` decision records a non-empty `fidelity_reason` naming the detail that reconstruction could lose.
- `preserve+derived_sketch`: keep the precise source figure and add a separate, clearly labelled simplified deterministic notebook sketch only when the pair has more teaching value than either figure alone. The sketch explains a supported mental model; it does not replace, correct or impersonate the source.

When there is a concrete uncertainty about losing exact information, choose `preserve` and state that uncertainty in `fidelity_reason`. The mere existence of a source asset is not such a reason. For reconstructible diagrams, first test whether all meaningful labels, relations, directions, groupings and order can be declared in the structured spec; if they can, `reinterpret` remains the default. Visual character still has lower priority than academic fidelity and legibility. Do not use `preserve+derived_sketch` merely to decorate a preserved figure or satisfy a figure count.

Code, formulas and tables are not literal pencil drawings. Keep their content exact and integrate them through the shared renderer's borders, captions, annotations and other notebook details. A simplified diagram derived from them is allowed only as a separate pedagogical figure with explicit provenance.

## Choose the visual medium
A derived `reinterpret` must use the smallest medium that teaches the concept correctly.

### `visual_medium: diagram`
Use the deterministic notebook-sketch renderer when the visual itself carries exact academic structure. This includes:
- flows and sequences;
- cycles and state transitions;
- timelines;
- hierarchies and trees;
- concept/relationship maps;
- architecture and subsystem relationships;
- exact labels, order, direction, topology or grouping.

The planner declares labels, nodes, edges, groups, semantic shapes, rank/order and provenance. Deterministic code owns final SVG geometry and notebook style. The model must not write raw SVG, pixel coordinates, colors or fonts.

Missing `visual_medium` remains backward-compatible with `diagram` for existing plans/specs.

### `visual_medium: illustration`
Use a generated illustration only for a recognizable physical/conceptual likeness where exact topology is not the teaching payload. Good examples are a generic CPU package, RAM module, disk, monitor, keyboard or peripheral.

Illustrations are intentionally **supporting only**:
- an illustration must use `need: visual_helpful`, never `visual_required`;
- it may show only simple visual cues explicitly supported by canonical knowledge;
- it must not encode exact quantities, sequence, wiring, topology, formulas, dates, taxonomies or assessment-critical relationships;
- it must contain no requested text, letters, numbers, labels or arrows;
- all authoritative labels and explanations stay in prose/HTML or a deterministic diagram;
- never generate the whole study page as an image.

The planner supplies only a compact semantic illustration spec: subject, view, supported visible cues, alt/caption and provenance. Carpeta owns the fixed pencil-style prompt, provider call, timeout, crop, white-background removal, transparent notebook overlay and registration. The planner never writes a long image prompt.

When the same concept benefits from physical recognition **and** an exact relationship diagram, both may be used: the illustration provides recognition; the diagram carries the academic structure.

## Source-first policy
Prefer a relevant figure from the unit sources when it faithfully represents what the chair teaches. Preserve provenance internally in `unidades/<unit-id>/conocimiento/figures.json`.

`source-first` governs evidence selection, not treatment selection. It must not automatically override a lossless `reinterpret` decision. A reconstructible source diagram may be the `figure:<id>` provenance of a new sketch while the final artifact uses the registered derived SVG rather than the source PNG.

If a source figure is too dense but the concept would benefit from a simpler schematic, a simplified diagram may be created only if every relationship shown is supported by canonical knowledge. Mark its origin as `derived` internally; never imply that a derived diagram came from the chair.

## Deterministic diagram generation
Normal pedagogical diagrams selected as `reinterpret` are generated from a structured sketch spec, never with an image-generation model. The planner decides what the figure means and contains; deterministic code owns the final SVG geometry and notebook style.

Supported priorities are flows, trees, concept maps, explicit relationships and technical schematics. For each selected derived diagram:
1. write `02-sketches/<id>.json` using `contracts/sketch-figure.schema.json`;
2. declare every node, edge and group with non-empty element-level `based_on` references included in the spec's global provenance;
3. use semantic shapes, rank/order and direction only—never colors, fonts, pixels or arbitrary SVG;
4. materialize through the hybrid visual plan, which delegates diagram rows to the established deterministic sketch generator;
5. persist `02-visual-build.json` and verify every planned SVG is registered;
6. only then draft Markdown, referencing the exact `asset` returned by the build report.

The diagram generator validates, renders and registers in one retry-safe operation. It stores the normalized spec next to the SVG, records both SHA-256 fingerprints and embeds generator/spec identity inside the SVG. Equal specs produce equal bytes. Existing IDs or paths with different content are refused.

The generated SVG is a transparent ink overlay. It must not contain paper, rules, a full-canvas rectangle, an outer frame, a plate or UI-like solid node fills; the document theme owns the visible notebook sheet behind it. Nodes and edges use deterministic double pencil traces with small curved deviations, so the drawing reads as manual without changing endpoints, labels, direction or semantic geometry. `sketch_figure.py audit` rejects an opaque canvas, a frame or node/edge geometry reduced to a single perfectly clean trace.

`preserve` bypasses this generator. `preserve+derived_sketch` requires the source figure to remain in the artifact and the spec to name the same `source_figure_id`; the SVG is a separate simplified companion. Screenshots, dense charts, visual tables, code, formulas, geometry, circuits, exact plots and any pixel/scale-sensitive representation remain source assets unless a separate supported sketch adds genuine learning value.

## Generated illustration materialization
A selected illustration is materialized by `scripts/visual_plan_hybrid.py` from the compact semantic spec in `02-plan.json`.

The bounded path is:
1. build the provider prompt deterministically from the semantic spec plus Carpeta's fixed notebook style;
2. make one provider call;
3. crop the white working canvas and deterministically key it to transparency;
4. wrap the raster as a transparent notebook overlay and collision-safely register it under `assets/figures/`;
5. record provider/model identity, semantic-spec hash, prompt hash, seed, final asset hash and postprocessing metadata without storing credentials;
6. use only the exact asset returned by `02-visual-build.json`.

No independent per-image vision-review loop is part of this path. The speed boundary is deliberate because generated illustrations are not allowed to carry authoritative academic structure. Normal academic review, integrity and final browser audit still apply to the document.

If the illustration provider is unavailable, do not retry repeatedly. Make at most one plan fallback for that failed visual: switch it to a deterministic diagram when the same supported meaning is naturally diagrammable, otherwise omit that optional illustration for the current run. Never reduce academic text quality to preserve a visual.

## Placement
Corresponding words and images belong together. Put the figure immediately after the paragraph that introduces it, followed by a short **How to read this figure** explanation when needed.

A useful figure block has:
1. meaningful alt text/caption;
2. the visual;
3. 1–4 sentences telling the learner what relationship to notice;
4. optionally one recall prompt that asks the learner to reconstruct/explain the visual.

Do not describe every pixel. Explain the conceptual relationship the student should extract. For generated illustrations, exact annotation belongs outside the pixels.

## Truth boundary
Never infer unlabeled components from an unreadable image. If the agent cannot confidently inspect or interpret a source visual, either omit it or state that visual interpretation is unavailable and use supported prose instead.

For a generated illustration, visual character always loses to academic fidelity. Never invent internal parts merely to make the drawing richer. If evidence supports only a high-level component, request only a high-level recognizable form. The generated pixels are never evidence for a factual claim.

## On-demand discovery for migrated/older courses
If `unidades/<unit-id>/conocimiento/figures.json` has no relevant source entry for the requested scope, do **not** reprocess the whole course. Instead:
1. run `python study.py figures scan <course> --write` if `.study/figure-pages.json` is missing/stale and the visual dependency is available;
2. use concept source references to identify candidate PDF pages for the requested scope;
3. inspect only those candidate pages/figures;
4. register/render only visuals that pass the pedagogical selection rule.

This is a narrow visual-indexing pass, not a reason to reread all transcripts or regenerate canonical text knowledge.

## Stable identity and derived registration
Unit matching is machine based. Use the resolved `unit_id` from `01-input.json`; do not compare strings such as `U1` and `Unidad 1` manually.

Derived assets live under `assets/figures/` and use namespaced `derived:<id>` records with `origin: derived`, stable `unit_id`, non-empty `based_on`, collision-safe asset paths and SHA-256 identity. Never directly overwrite a record whose origin is `source`.

Deterministic diagrams retain `generation.method: deterministic-svg`, generator/spec hashes and the established SVG integrity markers. Generated illustrations retain a separate `illustration_generation.method: generated-illustration` object with provider/model, semantic-spec hash, prompt hash, seed and postprocessing identity. These metadata families are intentionally distinct so an illustration can never masquerade as an exact deterministic diagram.

The integrity gate receives `02-plan.json` and fails closed when a planned derived asset is absent, uses the wrong medium/generator, substitutes a source asset for a `reinterpret`, or drops either member of `preserve+derived_sketch`.
