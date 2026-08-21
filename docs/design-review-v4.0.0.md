# Design review — V4.0.0 topic index

Verdict: **PASS**.

Every semantic top-level topic heading is now its own full-title index tab at
the exact point where the section starts. The title keeps its former left edge
while a warm, translucent pencil tab reaches into the left notebook margin and
keeps the underlying paper rules visible. Every tab permanently repeats the
blue double contour and inset rail of the topic index; denser pencil shading
marks the current topic without depending on scroll-derived borders. Tab
margins use whole ruled-line increments, and programmatic heading focus reuses
the tab treatment instead of drawing a second rectangle. There is no detached `T1–Tn` rail, visible legacy `Tema N` counter, or
permanent `Temas T` control in the reading surface. The `T` shortcut still opens
the ruled-paper index in physical, continuous and mobile reading without
changing the document content.

## Evidence reviewed

- `docs/design-samples/theory.html` — sustained prose and code;
- `docs/design-samples/architecture.html` — technical figure and captions;
- `docs/design-samples/operating-systems.html` — continuous guide, table,
  callouts and TOC;
- the published Arquitectura y Sistemas Operativos Unit 1 summary — six topics,
  twenty paginated sides and seven figures.

Each artifact passed the Chromium audit at desktop, tablet, mobile and print.
Interaction evidence covered the left-aligned pencil tabs, the open index,
keyboard traversal and topic selection, continuous mode, and the mobile panel.
The audit found every title alignment compensation within 1.5 px and found zero
persistent shortcut triggers at desktop, tablet and mobile. All screen tabs
kept both blue contours and the inset rail before scrolling; their 27 px top
and bottom margins matched the 27 px ruled-line pitch. Selecting a topic left
one active tab, one `aria-current` row and no visible heading focus outline.
Print hides all interactive navigation. The notebook-reader browser suite
passed all 16 tests, and the release suite passed all 317 tests.

## Reviewer rubric

| Dimension | Score (0–5) | Finding |
| --- | ---: | --- |
| Hierarchy | 5 | Topic titles remain at the original reading edge; only the contour moves into the margin. |
| Readability | 5 | Full titles stay in document flow and wrap cleanly at mobile width. |
| Density | 5 | Translucent pencil shading and removal of the permanent trigger avoid adding a control rail or floating card layer. |
| Signaling | 5 | Stable blue contours and rails connect every page tab to the index; denser shading plus `aria-current` identify the current topic without a duplicate focus box. |
| Figures | 5 | Tabs do not reduce figure width or separate figures from their explanations. |
| Responsive | 5 | The compensated left overhang scales from 2.15 rem to 1 rem and causes no horizontal overflow. |
| Print | 5 | Interactive chrome is absent and the continuous A4 layout is unchanged. |
| Accessibility | 4 | Named panel controls, visible focus, `T`, arrows, Home/End, Enter and Escape work; shortcut discoverability awaits the planned shared shortcuts icon. |

Concrete issues: the `T` shortcut is intentionally undiscoverable from the
reading surface until the shared shortcuts icon is introduced; this matches the
requested interim experience but should not become the final discoverability
model.

First fix: add the shared shortcuts icon and list `T · Índice de temas` there,
without restoring a permanent topic-specific label beside the paper.
