# Study Design System

This directory is the canonical source for the student-facing visual system. Ordinary `/resumen`, `/guia`, and `/repaso` runs must consume this frozen system instead of redesigning each artifact.

The current direction is **modern academic book**: warm paper, dark ink, chapter-style hierarchy, restrained semantic accents, and figures/tables that may extend beyond the prose measure when needed.

## Files

- `tokens.css` — color, type, spacing, measure, radius, semantic design tokens.
- `typography.css` — long-form reading typography and hierarchy.
- `layout.css` — paper/canvas, reading measure, optional guide navigation, responsive structure.
- `components.css` — semantic rails, tables, code, recall blocks.
- `figures.css` — figures and captions.
- `print.css` — A4/paged-media behavior.

## Rule

Change the design here, then rebuild `assets/study-theme.css`. Do not hand-edit generated theme output as the source of truth.