---
name: study-design
description: Design and evolve the University Study visual system for long-form academic reading. Use when changing typography, spacing, color semantics, components, figures, responsive layout, print styling, or the overall look of study HTML. Do not use during ordinary summary/guide/review generation; those runs must consume the frozen design system instead of redesigning it.
---
# Study Design

You are designing a **learning document**, not a dashboard, landing page or generic web app.

## Responsibility
Create or modify the shared visual system under `design/`. Do not style individual study artifacts ad hoc.

1. Read `design/README.md`.
2. Read only the references relevant to the requested change.
3. If making a substantial aesthetic change, also read `vendor/frontend-design/SKILL.md` for design-process guidance. Its aesthetic advice is subordinate to this skill's learning/readability constraints.
4. Make changes only in `design/*.css`; run `python scripts/build_design.py` to regenerate `assets/study-theme.css`.
5. Render all three stress-test documents under `docs/design-samples/`.
6. Run `python scripts/visual_audit.py ...` for legacy/non-scene documents or `python scripts/visual_audit_v2.py ...` when responsive V2 scenes are present; inspect desktop, tablet, mobile, print and per-scene evidence.
7. Invoke/use the `study-design-reviewer` rubric against the screenshots. Repair issues before considering the system stable.
8. Run release tests.

## Priority order
1. comprehension and academic hierarchy;
2. sustained readability;
3. accessibility;
4. consistency across subjects and devices;
5. visual character.

## Fixed product thesis
The visual direction is the **Carpeta university study notebook**. The default is warm ruled paper, dark ink, a restrained binding/margin cue, practical reading typography, selective marker emphasis and handwritten/pencil accents only where a student would naturally annotate or sketch. The page should feel like carefully edited university notes rather than a dashboard or faux vintage object. Figures, tables and code may break wider than ordinary prose when that improves learning.

The notebook identity is intentional product UI, not decoration to be removed by a reviewer. The historical contemporary-technical-manual direction is repository history, not the active visual target.

## Hard constraints
- No per-artifact redesign.
- No arbitrary per-course palette.
- No color-only meaning.
- No full justification.
- No decorative gradients, glassmorphism, dashboard card grids or animation during normal study reading.
- Figures are instructional objects and must remain visually close to the explanation they support. Prose measure stays narrower than figure/table/code width.
- Notebook cues must be systematic and restrained: ruled lines, binding margin/holes and handwriting accents are allowed because they are part of the canonical product grammar; do not add unrelated stickers, scrapbook ornament, fake wear, heavy grain or vintage cosplay.
- Course name + artifact type + scope should read like coherent notebook/chapter metadata when those values are available.
- Preserve the reference grammar: stable semantic role labels remain distinct from concept names; the first lede stays with the chapter opening; `Unidad N` may be presented editorially as `Capítulo N` while the running line keeps the academic scope intact.
- Persistent navigation is artifact-specific: summaries and rapid reviews should not carry sidebar chrome; long guides may use a quiet editorial index.
- The warm paper/light theme is the default. Dark mode may exist only as an explicit opt-in and must preserve hierarchy and meaning.
- Derived pedagogical V2 figures use the shared deterministic pencil renderer. The model may design composition, but not fonts, hex colors, CSS, filters or per-figure visual styling.
- Webfonts may be used as progressive enhancement when they materially improve long-form reading, but every role must have complete system fallbacks so artifacts remain readable offline. Never bundle font binaries in the project.
