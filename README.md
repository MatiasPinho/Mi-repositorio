# University Study System V3.5

Design-focused workspace for the University Study System. The full local package remains the source for academic pipelines; this repository is intentionally scoped to the student-facing renderer, design system, visual rules, samples, and design skills so a design agent can iterate without unrelated context.

## Design scope

The current direction is **modern academic book**: warm paper, dark ink, restrained color, strong long-form readability, instructional figures, and minimal interface chrome.

Start with `DESIGN-BRIEF.md`, then inspect all three samples under `docs/design-samples/` before proposing changes.

## Canonical visual files

```text
design/
├── tokens.css
├── typography.css
├── layout.css
├── components.css
├── figures.css
└── print.css
```

`assets/study-theme.css` is the built theme consumed by `scripts/render_study.py`.

## Stress tests

- `docs/design-samples/theory.html` — prose-heavy theory
- `docs/design-samples/architecture.html` — technical diagram/figure-heavy content
- `docs/design-samples/operating-systems.html` — prose + table + semantic callouts

## Constraints

Do not redesign academic pipelines or source-processing logic. Preserve semantic roles, responsive behavior, figures, print/PDF behavior, and portability across Claude Code and Codex.