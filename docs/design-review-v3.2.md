# V3.2 visual review

Design direction: **technical editorial notebook**.

Reviewed stress tests:
- `docs/design-samples/theory.html`
- `docs/design-samples/architecture.html`
- `docs/design-samples/operating-systems.html`

Screenshots were captured at desktop, tablet, mobile and print using `scripts/visual_audit.py`.

## Reviewer result

**PASS**

| Dimension | Score / 5 | Notes |
|---|---:|---|
| Hierarchy | 5 | H1/H2/prose/supporting blocks remain distinct without dashboard chrome. |
| Readability | 5 | 19px desktop, 18px mobile, narrow reading measure and generous leading. |
| Density | 5 | Continuous prose dominates; semantic blocks do not become card soup. |
| Signaling | 4 | Rails work well; continue policing overuse in generated content. |
| Figures | 5 | Diagram remains large, adjacent to interpretation and captioned with what to notice. |
| Responsive | 5 | No horizontal document overflow; TOC disappears cleanly on narrow screens. |
| Print | 4 | A4 output is readable and keeps semantic washes; long real guides still need regression samples. |
| Accessibility | 5 | Mechanical light-theme contrast checks exceed 4.5:1 for body, muted, links and semantic labels; roles have text labels. |

First thing to keep watching: **semantic callout frequency**. The renderer is restrained, but a writer could still over-signal by turning too many paragraphs into special blocks. The content reviewer must reject that.
