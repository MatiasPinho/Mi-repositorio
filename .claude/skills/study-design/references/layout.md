# Layout

The current canonical composition is a **gutter + reading measure** technical-manual layout.

- Prose lives in `--study-measure` (~42rem).
- A fixed `--study-gutter` (~8rem) carries real structure: unit labels, section numbers and semantic callout labels.
- Figures, tables and code may use `--study-wide` (~52rem), so technical material is not squeezed to prose width.
- Rows are wrapping flex layouts. On compact screens the gutter information moves above its associated content while the reading order stays linear.
- Long guides may add a quiet sticky TOC; summaries and rapid reviews remain document-first.

Spacing encodes relationships: smaller gaps inside one conceptual group, larger gaps between sections, and figures stay close to their interpretation. Avoid nested cards. Tables may scroll horizontally on very small screens; prose must not.
