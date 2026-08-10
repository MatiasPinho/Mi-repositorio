# Design research behind V3.3

This is a design-time note, not prompt context for ordinary study generation.

## Practical references
- Anthropic `frontend-design`: https://github.com/anthropics/skills/tree/main/skills/frontend-design
- GOV.UK current type scale: https://design-system.service.gov.uk/styles/type-scale/
- Carbon typography/tokens: https://carbondesignsystem.com/elements/typography/overview/
- Carbon themes/tokens: https://carbondesignsystem.com/elements/themes/overview/
- WCAG 2.2 visual presentation/text spacing/contrast: https://www.w3.org/TR/WCAG22/

## Conclusions applied
1. Typography and spacing are a system, not local decoration.
2. Standard prose stays large and narrow enough for sustained reading.
3. Color signals stable semantic roles and is never the sole meaning channel.
4. Whitespace and hierarchy do more work than borders/cards.
5. Relevant diagrams belong beside the explanation they support.
6. The design system is frozen during content generation; visual design is a separate maintenance workflow.
7. Values such as 19px body copy are evidence-informed defaults to test, not universal cognitive laws.

## V3.3 refinement: academic paper reader
1. Warm paper is an aesthetic/default-comfort choice, not a claim that cream backgrounds improve memory.
2. Positive polarity and strong luminance contrast remain the accessibility/readability baseline.
3. Reduce interface chrome, saturated color, shadows and callout surfaces so semantic figures and prose dominate.
4. Dark mode is opt-in rather than automatically following the operating-system theme.
5. A design regression is a failure if the page feels more like a product UI than a university handout.
