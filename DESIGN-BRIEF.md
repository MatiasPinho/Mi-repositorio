# Design Brief — University Study System

## Goal
Redesign the student-facing study documents so they feel like a modern university textbook: calm, highly legible for 1–2 hour sessions, academically serious, and visually refined without looking like a dashboard or SaaS product.

## Preserve
- Warm paper-like reading surface, without fake paper textures.
- Strong readability, restrained color, clear hierarchy, accessible contrast.
- Figures/diagrams as first-class pedagogical elements.
- Semantic structure and existing renderer contracts.
- Responsive reading and print/PDF behavior.
- Portability across Claude Code and Codex.

## You may redesign
- Typography and font stack.
- Type scale, line-height, measure, spacing rhythm.
- Chapter/opening hierarchy.
- Figure/table/caption treatment.
- Callout treatment.
- Long-guide navigation.
- Code/pseudocode presentation.
- Print composition.

## Avoid
- Dashboard/card-heavy UI.
- SaaS aesthetics.
- Gradients, badges, chips, excessive rounded cards.
- Decorative color with no semantic role.
- Fake vintage/paper textures, grain, notebook lines, stickers.
- Huge decorative chapter numbers or ornamental textbook cosplay.
- Dark code blocks that dominate the page.
- Visual novelty that harms long-session reading.

## Priority order
1. Learning and comprehension.
2. Long-session readability.
3. Academic hierarchy and figure comprehension.
4. Accessibility and responsive behavior.
5. Consistency across subjects.
6. Aesthetic refinement.

## Stress cases
Review all three samples before deciding the redesign:
- theory.html: prose-heavy theory.
- architecture.html: technical diagram/figure-heavy content.
- operating-systems.html: prose + table + semantic callouts.

The redesign must work for all three, not just one page.

## Important implementation constraint
Do not rewrite academic pipelines or source-processing logic. Treat the design system and renderer as the main scope. Semantic markup may be extended only when needed for a real pedagogical/display purpose.

## Expected output
Produce a coherent redesign, not a list of tiny tweaks. Update the design system and representative samples, and explain the design rationale briefly. Preserve or improve mobile and print behavior.