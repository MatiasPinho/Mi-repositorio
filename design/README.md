# Study Design System

Canonical source for the student-facing visual system. Ordinary `/resumen`, `/guia` and `/repaso` runs consume this frozen system instead of restyling each artifact.

Direction: **contemporary technical manual**. Warm paper, dark ink, one uninterrupted prose column, and a fixed left gutter that carries section numbers and semantic labels so nothing breaks the reading line. Figures, tables and code break past the prose measure.

## Files

- `tokens.css` — surfaces, ink, semantic hues, type roles, measure/gutter system, spacing.
- `typography.css` — long-form reading typography and hierarchy.
- `layout.css` — shell, paper, row primitive, front matter, section heads, progress, index.
- `components.css` — semantic rails, retrieval blocks, tables.
- `figures.css` — plates and captions.
- `print.css` — A4/paged-media behaviour.

## Composition rules

1. Prose is capped at `--study-measure` (42rem ≈ 68 characters). Never widen it.
2. Anything that labels or numbers the prose lives in `--study-gutter` (8rem), not inside the column.
3. Figures/tables/code use `--study-wide` (52rem).
4. Rows are wrapping flexboxes: the layout collapses by available width, not by viewport breakpoints, so it survives being embedded at any size.
5. Colour only ever encodes an academic role, and the role is always also written in words.

## Type

Source Serif 4 (body, 19px/1.72), IBM Plex Sans (labels, index, captions), IBM Plex Mono (code). Google Fonts with full system fallbacks; the page remains legible offline.

## Rule

Change the design here, then rebuild `assets/study-theme.css`. Do not hand-edit generated theme output as the source of truth.
