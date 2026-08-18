# Figures, diagrams and source visuals

A figure is pedagogical content, not decoration.

## Core rule
Use a visual when it makes a spatial, structural, causal, temporal, relational or physically recognizable concept easier to understand than prose alone. This is especially important in subjects such as computer architecture, operating systems, networking, databases, electronics, algorithms and mathematics.

Every selected figure must also belong to the shared notebook language:

> Toda figura debe integrarse al lenguaje visual del cuaderno. Las figuras pedagógicas derivadas tienden por defecto a una reinterpretación tipo notebook sketch/lápiz, salvo cuando la fidelidad del contenido requiera preservar el original.

This is a semantic treatment rule, not a blanket image filter. A notebook visual must be reconstructed from canonical knowledge and auditable provenance; it is never an automatic pencil effect applied to arbitrary source pixels.

Good candidates include architecture/block diagrams, process/state diagrams, memory maps, hierarchies, timelines, scheduling diagrams, flowcharts, spatial comparisons and simplified recognizable hardware/device illustrations. Do not include logos, cover art, duplicate visuals or decorative images that add no instructional information.

## Graphic explanatory density
A derived figure should prefer **visual encoding of the idea** over prose merely arranged inside containers. If the learner can understand a mechanism, component, flow, hierarchy, state change, comparison or relationship by seeing it, represent that structure graphically instead of reducing the visual to titled boxes with short paragraphs.

Use the appropriate medium to expose the concept itself: simplified recognizable objects, internal parts only when supported, paths, arrows, branches, cycles, layers, regions, relative position, state transitions, small worked visual examples and other supported spatial relationships. Text should normally label or clarify exact diagram structure rather than carry nearly all of the teaching by itself.

For comparisons, do not default mechanically to a symmetric grid of labeled boxes. Ask whether each compared item has a useful micro-diagram, internal structure, flow, example or distinctive visual relationship that can make the contrast visible. These are examples of visual reasoning, not required templates.

Boxes, regions and containers remain fully valid when containment, grouping, boundaries or architecture are themselves meaningful. A simple visual is also correct when the concept is genuinely simple. There is no minimum element count and no requirement to make figures busy.

Graphic richness never permits invented detail. Only visualize components and relationships supported by canonical knowledge/provenance. When the source supports only a high-level abstraction, keep the visual high-level rather than decorating it with plausible but unsupported parts.

## Representational fit
Before creating a derived visual, choose the medium and form that naturally match the concept. **Do not use a generic labeled rectangle as the default stand-in for something that has a useful recognizable form, process shape or spatial structure.**

Prefer these families when they improve understanding:

- **Physical, tangible or recognizable components** — CPU/chip, RAM module, disk, monitor, keyboard, printer and similar objects should normally use a **simplified generated pencil illustration** when physical recognition is the teaching value. For example, a CPU may read as a chip package with pins rather than a plain box titled `CPU`.
- **Processes, sequences and state changes** — instruction cycles, syscalls, scheduling, context switches, lifecycles and pipelines use deterministic flows, cycles, transitions, paths or state structures that make movement/order visible.
- **Architectures and systems** — hardware/software architectures, layers, memory/CPU/E/S relationships and subsystem layouts use deterministic spatial arrangement, boundaries, buses, connections, nesting or layers.
- **Comparisons and categories** — prefer internal visual cues, micro-diagrams or exact relationships that make distinctions visible instead of repeating prose in parallel cards.
- **Historical progressions and staged evolution** — use deterministic timelines, milestones or another explicit temporal progression when chronology is the teaching point.

These are representation heuristics, **not named templates**. The planner may choose another supported form when it teaches the canonical concept better.

Object likeness must come from supported visual cues, not decorative invention. A recognizable illustration may use silhouette and a small set of visible parts, but it must not hallucinate technical internals merely to look richer. If evidence only supports a high-level component, request only a high-level recognizable abstraction.

Do not solve this rule by adding more prose inside a figure. The intended improvement is **more explanatory drawing, spatial structure and visual cues**, with text kept outside generated pixels and concise inside deterministic diagrams.

Boxes remain valid when a box is actually meaningful: containment, memory regions, layers, modules, boundaries, grouping or a genuinely rectangular physical object. The rule is to avoid **generic-box substitution**, not geometry itself.

## Treatment decision
After deciding that a visual is required or helpful, record exactly one `visual_treatment` in the plan:

- `reinterpret`: the visual is a pedagogical derivation whose meaning can be reconstructed without loss. This is the default for explanatory diagrams and optional recognizable illustrations even when a source PNG already exists. Source availability supplies provenance; it does not select final pixels.
- `preserve`: use the precise original because reconstruction could lose evidence. This is normal for screenshots, dense charts, precision-sensitive visual tables, exact plots, formulas, geometry, circuits, notation-heavy figures and any visual whose pixels, scale or exact layout are meaningful. Record a concrete `fidelity_reason`.
- `preserve+derived_sketch`: keep the precise source and add a separate simplified deterministic notebook diagram only when the pair teaches more than either member alone. The derived visual never replaces or impersonates the source.

When uncertain about losing exact information, choose `preserve`. Visual character has lower priority than academic fidelity and legibility. Code, formulas and exact tables are not literal pencil drawings.

## Source-first policy
Prefer relevant unit-source evidence when it faithfully represents what the chair teaches. `source-first` governs evidence selection, not treatment selection. A reconstructible source diagram may be provenance for a new derived diagram while the final artifact uses the deterministic notebook SVG instead of source pixels.

If a source figure is too dense but the concept would benefit from a simpler mental model, derive only relationships supported by canonical knowledge. Never imply that an AI-designed explanation came from the chair.

## Selection during PLAN
For every major concept explicitly decide one of:
- `visual_required`;
- `visual_helpful`;
- `visual_not_needed`.

Do not force a fixed number of figures. One concept may need several visuals when splitting produces a substantially clearer explanation.

`visual_not_needed` must be chosen **only because prose genuinely teaches that concept as well or better without a figure**. It must never be selected to reduce runtime, token use, provider calls or implementation effort. Runtime optimization happens after this pedagogical decision. A useful visual may be omitted later only when the bounded visual workflow actually fails; that failure is not a reason to classify similar future concepts as visually unnecessary.

For every selected visual record treatment, reason and provenance. `preserve` / `preserve+derived_sketch` require `source_figure_id` and `fidelity_reason`. A derived figure requires a namespaced id plus non-empty `based_on`.

## Active hybrid visual system
`pipelines/resumen.md` uses the hybrid contract in `contracts/hybrid-visuals.md`.

The responsibility boundary is:

> Carpeta decides the execution medium from semantic intent. Exact academic structure uses deterministic diagrams; optional physical recognition may use generated pencil illustrations; precision-sensitive source evidence stays preserved.

### `visual_medium: diagram`
Use for any visual where exact relationship, order, topology, direction, chronology, label, quantity or structure is part of what the student must learn.

The active diagram backend is the existing compact schema-1 path:
- `02-sketches/<id>.json`;
- `contracts/sketch-figure.schema.json`;
- `scripts/visual_plan.py` / `scripts/visual_plan_hybrid.py`;
- deterministic notebook SVG generation and collision-safe registration.

The model writes compact semantic graph structure. It does **not** write raw SVG, explicit coordinate-heavy scene graphs, responsive wide/narrow geometry or provider-specific drawing code.

### `visual_medium: illustration`
Use only for `visual_helpful` recognition support: a CPU package, RAM module, disk, keyboard, monitor, printer, generic physical device or similarly recognizable subject.

The planner writes a compact semantic object with `subject`, `view`, `must_show`, `alt`, `caption` and `based_on`. It does not write the image-provider prompt. Carpeta owns the pencil style, negative constraints, provider adapter, deterministic seed, timeout, crop and transparency.

Generated image pixels must contain **no academic text, numbers, labels, arrows, formulas, chronology or exact topology**. If those are necessary, use a deterministic diagram or preserved source instead.

Illustrations are always `visual_helpful`, never `visual_required`, because generated pixels are not authoritative evidence. The textual summary must remain complete without them.

The current provider adapter may use Cloudflare Workers AI / FLUX, but provider identity is infrastructure, not part of the semantic contract. A future provider can replace it without changing the plan format.

### `visual_medium: source`
`preserve` keeps the exact registered source asset unchanged. `preserve+derived_sketch` pairs it with a deterministic diagram; it never pairs a precision-sensitive source with a generated illustration.

## Runtime and review boundary
Visual support must not recreate the old open-ended graphic-design pipeline.

- One semantic plan pass chooses the medium.
- Deterministic diagrams are generated directly from compact specs.
- A new generated illustration gets one bounded provider request.
- Exact registered illustration/spec reuse makes zero provider calls.
- There is no independent per-illustration vision-review/regeneration loop.
- If the image provider is unavailable, allow at most one run-local fallback decision: use a deterministic diagram only when the same meaning is naturally diagrammable; otherwise omit that optional illustration for the current run and continue.
- Browser visual audit remains final integration QA. It may reject a visibly broken/misleading generated illustration, but it must not trigger an open-ended regeneration session.
- Academic review remains strict and independent of visual runtime optimization.

The old schema-2 free-composition scene engine may remain in the repository for compatibility, experiments and historical evidence, but it is **not the default or required path for new `/resumen` visuals**.

## Placement
Put each figure immediately beside the explanation it supports. A useful figure block has meaningful alt/caption text, the visual, a short explanation of what relationship or recognition cue to notice and optionally one recall prompt. Do not narrate every pixel.

## Truth boundary
Never infer unlabeled components from an unreadable source image. Never treat generated illustration pixels as evidence for an exact academic claim. If exact structure matters, encode it deterministically from canonical knowledge or preserve the exact source.

## On-demand discovery for migrated/older courses
If `unidades/<unit-id>/conocimiento/figures.json` has no relevant entry for the requested scope, do not reprocess the whole course. Scan/index only candidate source pages needed by the current scope and register only visuals that pass the pedagogical selection rule.

## Stable identity and derived registration
Use stable `unit_id`, not fuzzy labels. Derived ids remain namespaced `derived:` and final assets live under `assets/figures/`. Source records/assets are never overwritten. Deterministic diagrams bind their exact spec and asset hashes. Generated illustrations bind their compact semantic spec, style version, provider/model metadata, deterministic seed and final transparent overlay hash.
