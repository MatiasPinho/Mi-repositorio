# Student-facing prose

Write like excellent human study notes, not an audit report.

## Default behavior
- Paraphrase source speech into a better explanation.
- Do not expose timestamps, source sigla, hashes or constant citations in normal prose.
- Do not open with a source inventory.
- Prefer connected paragraphs with selective bullets/tables when they genuinely improve comprehension.
- Avoid a wall of definitions, warning icons, “very askable” labels, artificial symmetry and repetitive “teacher said” framing.
- Preserve necessary course terminology, but explain it in normal language.

## Quotes
Exact teacher wording is exceptional. Use it only if exact wording is likely to be assessed, resolves a genuine ambiguity, or the user explicitly asks what was said.

## Humanizer
After the pedagogical draft, apply `vendor/humanizer/SKILL.md` in embedded mode to the student-facing prose only. Humanizer is editorial; it may not change academic truth, certainty, formulas, code behavior, dates, scope, conditions or required terminology.

## Visual/semantic markup boundary
Humanizer may edit prose inside semantic blocks, but it must preserve heading hierarchy, Markdown image paths/alt text, callout markers (`[!DEFINITION]`, `[!EXAMPLE]`, etc.), code fences and table structure. Do not turn semantic markup into decorative prose.
