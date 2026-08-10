# V3.3 visual review

Design direction: **academic paper reader**.

Reviewed stress tests:
- `docs/design-samples/theory.html`
- `docs/design-samples/architecture.html`
- `docs/design-samples/operating-systems.html`

Screenshots were captured at desktop, tablet, mobile and print using `scripts/visual_audit.py`.

## Reviewer result

**PASS**

| Dimension | Score / 5 | Notes |
|---|---:|---|
| Hierarchy | 5 | Restrained editorial headings remain immediately distinguishable without hero/UI styling. |
| Readability | 5 | Warm paper, dark ink, 18px desktop body, 17px mobile, 67ch measure and generous leading. |
| Density | 5 | Prose dominates. No cards, shadows, gradients or decorative surfaces compete with reading. |
| Signaling | 5 | Thin transparent marginal rails preserve semantic roles while remaining visually quiet. |
| Figures | 5 | Technical figure becomes a natural focal point because surrounding chrome has been removed. |
| Responsive | 5 | Mobile becomes a clean edge-to-edge paper page with no horizontal prose scrolling. |
| Print | 5 | A4 remains white, calm and readable; navigation disappears and semantic structure survives. |
| Accessibility | 5 | Mechanical light-theme contrast checks exceed 7:1 for muted/semantic text and 11:1 for body text; labels carry meaning beyond color. |

## Things intentionally rejected
- fake paper texture/grain;
- notebook lines, stickers or vintage effects;
- automatic dark mode;
- strong shadows/floating cards;
- saturated semantic panels;
- oversized hero headings.

Primary regression risk: generated content can still overuse semantic callouts. The content reviewer must keep ordinary prose as the dominant surface.
