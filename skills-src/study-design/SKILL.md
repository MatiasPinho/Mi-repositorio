---
name: study-design
description: Design and evolve the University Study visual system for long-form academic reading. Use when changing typography, spacing, color semantics, components, figures, responsive layout, print styling, or the overall look of study HTML. Do not use during ordinary summary/guide/review generation; those runs must consume the frozen design system instead of redesigning it.
---
# Study Design

You are designing a **learning document**, not a dashboard, landing page or generic web app.

## Responsibility
Create or modify the shared visual system under `design/`. Do not style individual study artifacts ad hoc.

1. Read `DESIGN-BRIEF.md` and `design/README.md`.
2. Read only the references relevant to the requested change.
3. If making a substantial aesthetic change, also read `vendor/frontend-design/SKILL.md` when available for design-process guidance. Its aesthetic advice is subordinate to this skill's learning/readability constraints.
4. Make changes only in the canonical design sources and renderer-facing files.
5. Review all three stress-test documents under `docs/design-samples/`.
6. Inspect desktop, tablet, mobile and print behavior.
7. Use the `study-design-reviewer` rubric against the rendered result. Repair issues before considering the system stable.

## Priority order
1. comprehension and academic hierarchy;
2. sustained readability;
3. accessibility;
4. consistency across subjects and devices;
5. visual character.

## Fixed product thesis
The visual direction is **modern academic book**. The default should resemble a calm contemporary university textbook/course reader: warm paper, dark ink, chapter-style front matter, restrained hierarchy, one dominant reading column and almost no interface chrome. Semantic rails are quiet marginal notes, not colored components. Figures may become visually dominant when they are instructionally necessary. Do not introduce decoration whose meaning cannot be explained.

## Hard constraints
- No per-artifact redesign.
- No arbitrary per-course palette.
- No color-only meaning.
- No full justification.
- No decorative gradients, glassmorphism, dashboard card grids or animation during normal study reading.
- Figures are instructional objects and must remain visually close to the explanation they support. Prose measure stays narrower than figure/table/code width, as in technical books.
- Book identity comes from hierarchy, front matter, measure and rhythm; never from fake paper textures or ornamental flourishes.
- Course name + artifact type + scope should read like textbook front matter when those metadata are available.
- Persistent navigation is artifact-specific: summaries and rapid reviews should not carry sidebar chrome; long guides may use a quiet editorial index.
- The warm paper/light theme is the default. Dark mode may exist only as an explicit opt-in and must preserve hierarchy and meaning.
- Do not simulate paper with textures, grain, notebook lines, stickers or vintage effects.
- Use offline/system font stacks; never require bundled font files.