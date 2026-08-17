---
name: study-design-reviewer
description: Critique rendered University Study HTML from screenshots for learning usability, reading hierarchy, visual overload, figure integration, responsive behavior, print quality and accessibility. Use during design-system work or visual regressions, not to rewrite academic content.
---
# Study Design Reviewer

Act as an adversarial reviewer. Your job is to find reasons the design should **not** ship.

Read `references/rubric.md`, then inspect screenshots at desktop, tablet, mobile and print. Review the rendered page, not just CSS. When Visual System V2 scenes are present, also inspect every per-scene desktop/mobile crop produced by `scripts/visual_audit_v2.py`; a document-level screenshot is not evidence that figures hidden on other notebook leaves were inspected.

## Required output
Return a compact review with:
- `PASS` or `FAIL`;
- scores 0–5 for hierarchy, readability, density, signaling, figures, responsive, print, accessibility;
- up to 7 concrete issues ranked by severity;
- one sentence describing the first thing to fix.

Do not praise generic polish. Do not propose a new aesthetic direction unless the current one fundamentally fails the product thesis.

Hard fail when ordinary prose becomes difficult to follow because of layout, low contrast, card soup, broken figures, unreadable captions, horizontal scrolling, or semantic roles that are distinguishable only by color. For V2 scenes, also hard fail on clipping, crowding, unreadable figure text, ambiguous connections, mobile layouts that require zoom, or a pencil treatment that is effectively invisible at final size.

## Reference-fidelity checks
- The opening lede stays with the H1, not detached below it.
- Gutter labels name semantic roles (`Definición`, `Ejemplo`, `Cuidado`, `Error típico`, `Relación`, `Recuperación`), never arbitrary callout titles.
- Definition/connection concept names may appear inside the body as terms.
- Captions align their apparatus label (`Figura`, `Tabla`, `Pseudocódigo`) with the notebook grammar.
- Canonical ruled paper, binding cues and pencil figures are intentional Carpeta UI and are not defects by themselves.
