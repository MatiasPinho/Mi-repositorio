# Design review — V3.6

Direction: **contemporary technical manual / university textbook**.

This release integrates the external Claude Design proposal into the real deterministic renderer rather than shipping the exported preview HTML.

## What changed

- 8rem left gutter carries section numbers, scope labels and semantic roles.
- Prose remains on a 42rem reading measure; figures, tables and code may use 52rem.
- Source Serif 4 is the preferred long-form face, with IBM Plex Sans/Mono for utility/code and complete system fallbacks.
- Major sections are numbered automatically by the renderer.
- Semantic callouts keep their label outside the prose line and use a thin role-colored rail.
- Recall prompts are visible rather than collapsed.
- Figures use a technical plate and split `Figura N` + explanatory caption.
- Long guides may add a quiet TOC and 2px reading-progress indicator.
- Mobile collapses gutter metadata above the associated content; no prose overflow.

## Stress-test result

| Dimension | Result |
| --- | --- |
| Theory / long prose | PASS |
| Architecture / technical figure | PASS |
| Operating systems / table + callouts | PASS |
| Desktop overflow | PASS |
| Tablet overflow | PASS |
| Mobile overflow | PASS |
| A4 print | PASS |
| Card soup | 0 detected |
| Body contrast | 11.59:1 |
| Lowest audited semantic contrast | 7.20:1 |

The visual audit uses browser screenshots plus mechanical checks; final aesthetic judgment is still screenshot-based rather than inferred from CSS alone.
