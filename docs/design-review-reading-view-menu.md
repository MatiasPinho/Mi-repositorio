# Design review — reading view menu

Verdict: **PASS**.

Pressing `V` opens a ruled-paper selector instead of changing presentation
immediately. `Hojas` and `Continua` each combine a plain-language explanation
with a distinct CSS pencil sketch: a layered page stack with a turn cue, and a
long ruled strip with a downward reading cue. The selected row uses the same
blue contour, inset rail and restrained marker wash as the topic index.

## Evidence reviewed

- the published Arquitectura y Sistemas Operativos Unit 1 summary with the
  selector open in paged and continuous modes at desktop width;
- the same selector at tablet and mobile widths;
- `docs/design-samples/theory.html`, `architecture.html` and
  `operating-systems.html` at desktop, tablet, mobile and print.

The audits found two named options, two pencil previews, one checked option and
visible keyboard focus in every eligible summary. Desktop and tablet changed
between modes without losing content. Mobile kept both explanations visible,
disabled only the unavailable physical-page choice and introduced no
horizontal overflow. Print omitted the selector. All four audited documents
reported zero issues. The notebook-reader suite passed all 16 tests and the
release suite passed all 317 tests.

## Reviewer rubric

| Dimension | Score (0–5) | Finding |
| --- | ---: | --- |
| Hierarchy | 5 | The title, two choices and short footer form one immediate decision. |
| Readability | 5 | Labels and explanations remain readable over the ruled surface at all widths. |
| Density | 5 | Two large rows explain the modes without adding persistent reading chrome. |
| Signaling | 5 | Text, radio state, focus, contour and sketches all reinforce the choice without color-only meaning. |
| Figures | 5 | The CSS sketches remain legible at their final size and never compete with document figures. |
| Responsive | 5 | The selector becomes a contained bottom sheet on mobile with no horizontal overflow. |
| Print | 5 | The selector is excluded from printed output. |
| Accessibility | 4 | Dialog naming, radio semantics, visible focus, arrows, Home/End, Enter, Escape and disabled-state explanation work; shortcut discoverability still awaits the planned shared shortcuts control. |

Concrete issue: `V` remains intentionally undiscoverable from the reading
surface until the shared shortcuts control exists.

First fix: add the future shared shortcuts control without restoring permanent
view-specific chrome beside the paper.
