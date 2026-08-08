# Evidence notes (design-time only)

This file documents why the visual defaults exist. It is not loaded during ordinary study generation.

- WCAG 2.2 describes mechanisms for readable line length, non-justified text, text spacing and robust resizing. https://www.w3.org/TR/WCAG22/
- GOV.UK's type system uses a consistent vertical rhythm and readability/accessibility-oriented type scale. https://design-system.service.gov.uk/styles/type-scale/
- Carbon uses role-based type and theme tokens to create predictable hierarchy rather than local styling decisions. https://carbondesignsystem.com/elements/typography/overview/
- Signaling/cueing research supports visual cues when they direct attention to relevant material; this is why semantic color is sparse and stable rather than decorative.
- Multimedia learning principles support relevant words + graphics and spatial contiguity; this is why figures are attached to the explanation they serve.

Do not turn these observations into fake universal constants. The shipped values are defaults to test, not laws of cognition.