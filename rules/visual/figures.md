# Figures, diagrams and source visuals

A figure is pedagogical content, not decoration.

## Core rule
Use a visual when it makes a spatial, structural, causal, temporal or relational concept easier to understand than prose alone. This is especially important in subjects such as computer architecture, operating systems, networking, databases, electronics, algorithms and mathematics.

Every selected figure must also belong to the shared notebook language:

> Toda figura debe integrarse al lenguaje visual del cuaderno. Las figuras pedagógicas derivadas tienden por defecto a una reinterpretación tipo notebook sketch/lápiz, salvo cuando la fidelidad del contenido requiera preservar el original.

This is a semantic treatment rule, not a blanket image filter. A notebook sketch must be reconstructed from canonical knowledge and auditable relationships; it is never an automatic pencil effect applied to arbitrary pixels.

Good candidates include architecture/block diagrams, process/state diagrams, memory maps, hierarchies, timelines, scheduling diagrams, flowcharts, spatial comparisons and other relationships that become clearer when seen. Do not include decorative illustrations, logos, cover art, duplicate visuals or screenshots that add no instructional information.

## Graphic explanatory density
A derived figure should prefer **visual encoding of the idea** over prose merely arranged inside containers. If the learner can understand a mechanism, component, flow, hierarchy, state change, comparison or relationship by seeing it, represent that structure graphically instead of reducing the scene to titled boxes with short paragraphs.

Use the scene graph freely to expose the concept itself: simplified objects/components, internal parts, paths, arrows, branches, cycles, layers, regions, relative position, state transitions, small worked visual examples and other supported spatial relationships. Text should normally label or clarify the visual structure rather than carry nearly all of the teaching by itself.

For comparisons, do not default mechanically to a symmetric grid of labeled boxes. Ask whether each compared item has a useful micro-diagram, internal structure, flow, example or distinctive visual relationship that can make the contrast visible. A comparison of programming paradigms, for example, may show a linear jump, structured control branches, facts/rules leading to a query, or an object split into data and actions instead of four prose cards. These are examples of visual reasoning, not required templates.

Boxes, regions and containers remain fully valid when containment, grouping, boundaries or architecture are themselves meaningful. A simple scene is also correct when the concept is genuinely simple. There is no minimum element count and no requirement to make figures busy.

Graphic richness never permits invented detail. Only visualize components and relationships supported by canonical knowledge/provenance. When the source supports only a high-level abstraction, keep the drawing high-level rather than decorating it with plausible but unsupported parts.

## Representational fit
Before composing a derived scene, choose the visual form that naturally matches the kind of concept being taught. **Do not use a generic labeled rectangle as the default stand-in for something that has a useful recognizable form, process shape or spatial structure.** The scene graph is a drawing vocabulary, not a box-diagram template.

Prefer these families when they improve understanding:

- **Physical, tangible or recognizable components** — CPU/chip, RAM module, disk, monitor, keyboard, device, bus, network node, printer and similar objects should prefer a **simplified iconic/schematic sketch** whose silhouette or small set of supported parts makes the object recognizable. It can remain extremely simple and hand-drawn; it does not need realism. For example, a CPU may read as a chip package with pins and only the supported internal labels, rather than a plain box titled `CPU`.
- **Processes, sequences and state changes** — instruction cycles, syscalls, scheduling, context switches, lifecycles and pipelines should prefer flows, cycles, transitions, paths or state structures that make movement/order visible.
- **Architectures and systems** — hardware/software architectures, layers, memory/CPU/E/S relationships and subsystem layouts should prefer meaningful spatial arrangement, boundaries, buses, connections, nesting or layers.
- **Comparisons and categories** — prefer internal visual cues, micro-diagrams, distinctive structure or relationships that make the contrast visible instead of repeating prose in parallel cards.
- **Historical progressions and staged evolution** — prefer timelines, milestones or another explicit temporal progression when chronology is the teaching point.

These are representation heuristics, **not named templates**. The model remains free to invent a different composition when it teaches the canonical concept better.

Object likeness must come from supported geometry and relationships, not decorative invention. A recognizable sketch may use silhouette, repeated small parts, connectors, relative position or other simple cues, but it must not hallucinate technical internals merely to look richer. If evidence only supports a high-level component, draw a high-level recognizable abstraction.

Do not solve this rule by adding more prose inside the figure. The intended improvement is **more explanatory drawing, spatial structure and visual cues**, with text kept to labels and short clarifications.

Boxes remain valid when a box is actually meaningful: containment, memory regions, layers, modules, boundaries, grouping or a genuinely rectangular physical object. The rule is to avoid **generic-box substitution**, not geometry itself.

## Treatment decision
After deciding that a visual is required or helpful, record exactly one `visual_treatment` in the plan:

- `reinterpret`: the visual is a pedagogical derivation whose meaning can be reconstructed without loss. This is the default for explanatory diagrams even when a source PNG already exists. Source availability supplies provenance; it does not select final pixels.
- `preserve`: use the precise original because reconstruction could lose evidence. This is normal for screenshots, dense charts, precision-sensitive visual tables, exact plots, formulas, geometry, circuits, notation-heavy figures and any visual whose pixels, scale or exact layout are meaningful. Record a concrete `fidelity_reason`.
- `preserve+derived_sketch`: keep the precise source and add a separate simplified notebook figure only when the pair teaches more than either member alone. The derived scene never replaces or impersonates the source.

When uncertain about losing exact information, choose `preserve`. Visual character has lower priority than academic fidelity and legibility. Code, formulas and exact tables are not literal pencil drawings; a simplified companion may exist only as a separate pedagogical figure with provenance.

## Source-first policy
Prefer relevant unit-source evidence when it faithfully represents what the chair teaches. `source-first` governs evidence selection, not treatment selection. A reconstructible source diagram may be provenance for a new derived scene while the final artifact uses the reviewed derived SVG instead of source pixels.

If a source figure is too dense but the concept would benefit from a simpler mental model, derive only relationships supported by canonical knowledge. Never imply that an AI-designed explanation came from the chair.

## Selection during PLAN
For every major concept explicitly decide one of:
- `visual_required`;
- `visual_helpful`;
- `visual_not_needed`.

Do not force a fixed number of figures. One concept may need several scenes when splitting produces a substantially clearer explanation.

`visual_not_needed` must be chosen **only because prose genuinely teaches that concept as well or better without a figure**. It must never be selected to reduce runtime, token use, review calls or implementation effort. Runtime optimization happens after this pedagogical decision. A useful `visual_required` / `visual_helpful` figure may be omitted later only when the bounded visual workflow actually fails; that failure is not a reason to classify similar future concepts as visually unnecessary.

For every selected visual record treatment, reason and provenance. `preserve` / `preserve+derived_sketch` require `source_figure_id` and `fidelity_reason`. A derived figure requires a namespaced id plus non-empty `based_on`.

## Visual System V2 — free AI composition
New pedagogical derived figures use `contracts/scene-figure.schema.json` (`schema_version: 2`). V2 changes the responsibility boundary:

> The model owns semantic composition and geometry. Carpeta owns style, safety, fidelity, responsiveness, deterministic rendering and approval.

The model may combine structured primitives such as text, shapes, lines, paths, connectors, arrows, groups, regions, braces, axes, dividers and annotations. It is not restricted to a named diagram template. A timeline, Venn-like composition, cycle, layer model, comparison or novel spatial explanation can be composed from those primitives.

The model must **not** emit raw SVG, HTML, CSS, fonts, hex colors, filters, scripts, URLs or arbitrary style values. Exact colors, typography, stroke widths, ghost traces and pencil irregularity belong to deterministic code.

Academic semantics are declared once in `elements`. Every semantic element has non-empty element-level `based_on` references included in the scene-level provenance. A text-bearing element cannot opt out by declaring itself decorative. `representation_role` distinguishes `literal`, `structural` and `pedagogical_analogy` content.

`layouts.wide` and `layouts.narrow` contain geometry only and must place the same semantic element set. Do not shrink an oversized desktop scene into mobile when a different narrow composition is clearer.

### V2 lifecycle
For each new derived scene:

1. write `02-scenes/<id>.json` using `contracts/scene-figure.schema.json`;
2. run `scripts/visual_plan_v2.py preview`, which validates the scene and performs deterministic geometry preflight before producing run-local wide/narrow previews;
3. if deterministic preflight cites a concrete mechanical defect, repair only that defect. Once preflight passes, the scene creator does **not** inspect or subjectively review its own preview; hand it directly to the independent vision reviewer;
4. have a separate vision-capable reviewer inspect both PNG previews using `rules/evaluation/visual-rubric.md` and write `02-visual-review.json` bound to exact screenshot SHA-256 values;
5. on visual failure, repair the failed scene once from the review findings, run deterministic preview/preflight again, and send the changed evidence directly to one final independent review. New runs allow at most two reviewed attempts per scene;
6. if the second reviewed attempt still fails, omit that scene from the current summary plan and continue. There is no third review and a failed illustration must not block the textual summary;
7. run `scripts/visual_plan_v2.py finalize` only after every scene still present in the final plan has PASS. Finalization re-renders the SVGs, proves their hashes match the reviewed attempt and only then registers the wide/narrow assets;
8. draft student prose from the final surviving visual set;
9. after normal HTML rendering, run `scripts/scene_responsive.py` so narrow geometry is selected on mobile;
10. validate with `scripts/artifact_integrity_v2.py` and audit the final HTML with `scripts/visual_audit_v2.py`.

Failed attempts live only under the run's `02-visual-attempts/` tree. They never mutate `figures.json` or canonical assets.

The V2 renderer keeps the SVG canvas transparent. The notebook paper belongs to the document theme. Pencil geometry is scale-aware so the double trace and irregularity remain perceptible at real display size instead of disappearing after downscaling.

## Independent vision boundary
Mechanical checks are necessary but cannot establish perceptual quality. A Python report can prove geometry, hashes and file identity; it cannot prove that a model actually saw an image.

The scene creator is not its own reviewer. After a preview passes deterministic preflight, the creator must not open the PNG/SVG to run a private quality pass, score its own work, polish by eye or redesign before the independent review. The only creator-side pre-review correction is a targeted response to a deterministic preflight failure.

A visual PASS therefore requires `vision_verified: true`, reviewer `capability: vision`, `independent: true`, and exact wide/narrow screenshot hashes. A model without image input must return an incomplete visual state, never PASS. The executor assertion of vision capability is explicit; the screenshot binding is mechanically verified.

Hard perceptual failures include unreadable text, clipping, crowding, accidentally stuck elements, ambiguous connections, arrows through text, excessive density, a mobile layout that depends on zoom, or pencil style that is effectively invisible at final size.

## Legacy deterministic sketch generation (schema 1)
Schema 1 remains supported for existing figures and old runs. It uses `02-sketches/<id>.json`, `contracts/sketch-figure.schema.json`, `scripts/visual_plan.py` and the `figures generate-sketch` path. It supports the historical `flow`, `tree`, `concept-map`, `relations` and `technical-schematic` graph contract.

Never create normal diagrams with an image-generation model. Existing schema-1 generator identity and output must remain stable; do not migrate old assets merely because V2 exists.

## Placement
Put each figure immediately beside the explanation it supports. A useful figure block has meaningful alt/caption text, the visual, a short explanation of what relationship to notice and optionally one recall prompt. Do not narrate every pixel.

## Truth boundary
Never infer unlabeled components from an unreadable source image. If the agent cannot confidently inspect a source visual, omit it or state that visual interpretation is unavailable and use supported prose instead.

## On-demand discovery for migrated/older courses
If `unidades/<unit-id>/conocimiento/figures.json` has no relevant entry for the requested scope, do not reprocess the whole course. Scan/index only candidate source pages needed by the current scope and register only visuals that pass the pedagogical selection rule.

## Stable identity and derived registration
Use stable `unit_id`, not fuzzy labels. Derived ids remain namespaced `derived:` and final assets live under `assets/figures/`. Source records/assets are never overwritten. V2 derived records bind the canonical scene plus wide/narrow SVG SHA-256 values and the review attempt that approved them.

Full architecture and deterministic/perceptual boundary: `docs/visual-system-v2.md`.
