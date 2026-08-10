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
6. Run `python scripts/visual_audit.py ...` and inspect desktop, tablet, mobile and print screenshots.
7. Invoke/use the `study-design-reviewer` rubric against the screenshots. Repair issues before considering the system stable.
8. Run release tests.

## Priority order
1. comprehension and academic hierarchy;
2. sustained readability;
3. accessibility;
4. consistency across subjects and devices;
5. visual character.

## Fixed product thesis
The visual direction is **contemporary technical manual / university textbook**. The default is warm paper, dark ink, a narrow prose measure and a stable left gutter that carries section numbers and semantic labels without interrupting the reading line. Figures, tables and code may break wider than prose. The page should feel edited, not app-like. Do not introduce decoration whose meaning cannot be explained.

## Hard constraints
- No per-artifact redesign.
- No arbitrary per-course palette.
- No color-only meaning.
- No full justification.
- No decorative gradients, glassmorphism, dashboard card grids or animation during normal study reading.
- Figures are instructional objects and must remain visually close to the explanation they support. Prose measure stays narrower than figure/table/code width, as in technical books.
- Book identity comes from hierarchy, front matter, measure and rhythm; never from fake paper textures or ornamental flourishes.
- Course name + artifact type + scope should read like textbook front matter when those metadata are available.
- Preserve the reference grammar: role labels live in the gutter; concept names live in the body; the first lede belongs under the H1 in the chapter opening; `Unidad N` may be presented editorially as `Capítulo N` while the running line keeps the academic scope intact.
- Persistent navigation is artifact-specific: summaries and rapid reviews should not carry sidebar chrome; long guides may use a quiet editorial index.
- The warm paper/light theme is the default. Dark mode may exist only as an explicit opt-in and must preserve hierarchy and meaning.
- Do not simulate paper with textures, grain, notebook lines, stickers or vintage effects.
- Webfonts may be used as progressive enhancement when they materially improve long-form reading, but every role must have complete system fallbacks so artifacts remain readable offline. Never bundle font binaries in the project.
