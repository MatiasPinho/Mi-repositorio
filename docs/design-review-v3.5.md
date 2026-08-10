# Design review — V3.5

Direction: **modern academic book**.

V3.5 keeps the warm-paper minimalism of V3.4 but replaces the remaining document/web cues with textbook grammar.

## Changes accepted
- Course name + artifact type form a restrained running line.
- Scope/unit is presented as the chapter label.
- H1 is a chapter title rather than a hero.
- H2 no longer uses a top border; sections are separated mainly by whitespace and typography.
- H3 joins the serif hierarchy; sans-serif is reserved mostly for utility labels.
- Tables use serif body cells with compact sans-serif headers and horizontal rules.
- Code blocks use a light paper-muted treatment instead of a dark editor-like slab.
- Figures lose unnecessary borders; captions use `Figura N.` book-style numbering.
- Print CSS requests bottom-center page folios through paged-media margin boxes where supported.

## Rejected directions
- fake book textures or binding effects;
- drop caps and ornamental chapter flourishes;
- decorative section numbering;
- justified prose;
- per-course visual identities;
- dark code panels that dominate a page.

## Stress-test result
Theory, architecture and operating-systems samples pass mechanical desktop/tablet/mobile/print audits with no overflow, no card-like UI and high contrast. The architecture figure benefits from the wider technical measure while ordinary prose remains narrow.
