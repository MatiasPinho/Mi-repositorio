# Visual System V2

Visual System V2 changes the responsibility boundary for pedagogical derived figures.

> **The model designs the illustration; Carpeta owns visual style, fidelity, safety, responsiveness and approval.**

## Why V2 exists

Schema 1 remains the frozen legacy graph renderer for `flow`, `tree`, `concept-map`, `relations` and `technical-schematic`. It is intentionally retained for backward compatibility.

Schema 2 is not a larger list of diagram templates. It is a constrained scene graph. The model may compose shapes, text, paths, connectors, regions, groups, braces, axes, dividers and annotations with explicit geometry. It may use those primitives to create a timeline, Venn-like composition, layers, cycle, spatial explanation or a representation the engine never named in advance.

The model never emits SVG, HTML, CSS, fonts, hex colors, filters or scripts. Exact visual output comes only from deterministic code.

## Truth and provenance

Every semantic element carries non-empty `based_on` references included in the scene-level provenance. Text-bearing objects cannot opt out by declaring themselves decorative. `representation_role` distinguishes `literal`, `structural` and `pedagogical_analogy` content; analogy is an explanatory construction and must never be represented as canonical source material.

The existing treatment policy remains unchanged:

- `reinterpret` for reconstructible pedagogical figures;
- `preserve` when pixels, notation, scale or precise geometry are evidence;
- `preserve+derived_sketch` when an exact source plus a separate simplified scene teaches better than either alone.

Source assets are never restyled or overwritten.

## Wide and narrow

Academic semantics live once in `elements`. `layouts.wide` and `layouts.narrow` contain geometry only and must place the same element set. This allows a five-step process to be horizontal on wide screens and vertical on mobile without creating two contradictory academic scenes.

## Pipeline

New V2 derived figures follow this lifecycle:

1. PLAN writes `02-scenes/<id>.json`.
2. `visual_plan_v2.py preview` validates the scene, runs deterministic geometry preflight and creates run-local wide/narrow SVG + PNG attempts.
3. A separate vision-capable reviewer inspects both PNGs using `rules/evaluation/visual-rubric.md` and writes `02-visual-review.json` bound to exact PNG hashes.
4. Failed attempts are repaired and previewed again. At most three reviewed attempts are allowed per scene.
5. `visual_plan_v2.py finalize` mechanically verifies review bindings, re-renders the SVGs, requires identical hashes to the reviewed attempt and only then registers immutable wide/narrow assets.
6. Drafting begins only after all planned derived scenes are finalized.
7. `scene_responsive.py` upgrades final V2 image markup to `<picture>` so the browser uses the independently designed narrow asset on mobile.
8. `artifact_integrity_v2.py` binds plan, preview, vision review, registered scene/variant hashes and final responsive HTML.
9. `visual_audit_v2.py` reuses the normal browser audit and additionally captures every published V2 scene at desktop and mobile sizes.

## Deterministic versus perceptual guarantees

The engine can prove geometry, hashes, provenance, asset identity and whether an external review claims vision capability. It cannot prove from Python alone that a model genuinely perceived an image. Therefore `vision_verified: true`, `capability: vision` and `independent: true` are explicit executor assertions, while the exact screenshots inspected are mechanically bound by SHA-256.

A model without image input must never produce a visual PASS. Its state is incomplete until a vision-capable reviewer inspects the PNGs.

## Pencil renderer

V2 uses a dedicated deterministic scene renderer whose style values are centralized in `scene_pencil.py`. Pencil widths, ghost traces, jitter and typography are expressed relative to expected final display width so their perceptual strength does not disappear when a large logical canvas is embedded into the notebook.

The model chooses semantic tones only. It cannot choose exact colors, stroke widths or fonts.

## Compatibility

Schema 1 files and `scripts/sketch_figure.py` remain untouched. Existing registered figures retain their generator identity and hashes. V2 scenes use separate generator identity/metadata and may coexist in the same figure registry.
