# Study document visual system

Student-facing documents are **learning documents**, not raw Markdown dumps or miniature web apps.
Markdown remains the portable semantic source; the primary reading artifact is rendered HTML.

## Evidence-informed defaults
- Use a comfortable single reading column; target roughly 60–75 characters per line and never design for >80.
- Body text should be large enough for sustained on-screen reading (about 19px desktop in the shipped theme).
- Use left alignment, never full justification.
- Use generous but not extreme line spacing (about 1.72 in the shipped screen theme) and clear paragraph separation.
- Headings must form a real hierarchy and describe what the section teaches.
- Maintain high luminance contrast. Color is a cue, not the only carrier of meaning.
- Prefer whitespace and grouping over borders everywhere.

## Book structure
The rendered artifact follows a contemporary technical-manual/textbook grammar:
1. course/subject name and artifact type in a quiet running line;
2. artifact type + academic scope remain in the running line (for example `Resumen · Unidad 1`);
3. when the scope is `Unidad N`, the opening gutter presents it editorially as `Capítulo N`, beside one restrained H1;
4. the first orienting paragraph, when present, stays inside the chapter opening under the H1 rather than becoming a detached prose row;
5. numbered major sections with numbers in the gutter;
6. semantic callout labels in the gutter so prose stays uninterrupted;
7. figures/tables/code allowed to use more width than prose;
8. compact visible retrieval material near the end of coherent concept groups.

Do not repeat the unit label inside the title when the renderer already receives `--scope`.
Do not fake book aesthetics with paper textures, ornamental flourishes or decorative chapter numbers.

## Emphasis
- **Bold** is the default emphasis for a term or decisive phrase.
- Do not underline normal emphasis. Underlining is reserved for links.
- Do not highlight whole paragraphs.
- Do not use ALL CAPS as emphasis.
- Keep each paragraph focused on one idea.

## Semantic callouts
Use the supported Markdown callout syntax only when it earns visual weight:

```markdown
> [!DEFINITION] Optional title
> Precise but understandable definition.

> [!EXAMPLE] Example
> A small example that removes ambiguity.

> [!WARNING] Common mistake
> A trap, contradiction or exception.

> [!EXAM] Exam relevance
> Only if the assessment relevance is actually supported.

> [!CONNECTION] Connection
> A useful relationship to another concept.

> [!RECALL] Check yourself
> A retrieval question, preferably answerable without rereading.
```

The renderer owns the gutter label and keeps it stable by semantic role (`Definición`, `Ejemplo`, `Cuidado`, `Error típico`, `Relación`, `Recuperación`). An optional specific title must never replace or disappear behind that role label. When present, it appears as a term inside the reading column for every callout type (for example `Cuidado` in the gutter + **Precondición no es lo mismo que validación** in the body).

Callouts must always include a textual role label, so meaning never depends on color alone.

## Color semantics
The renderer owns exact colors. Writers only choose semantic roles.
- Definition/concept → blue family.
- Example/application → green family.
- Warning/error/uncertainty → amber/red family depending on severity.
- Exam relevance → amber family.
- Connection/relationship → violet family.
- Recall/self-test → neutral/blue-gray family.

Never invent a new color meaning inside an artifact.

## Frozen design system
The writer chooses **semantic roles only**. It must never choose hex colors, fonts, margins, border radii, component shapes or per-course styling.

The canonical visual implementation lives in `design/` and is compiled to `assets/study-theme.css`. Ordinary summary, guide and rapid-review runs must **not** load `frontend-design`, `study-design` or `study-design-reviewer`; those are design-time maintenance skills. This prevents style drift and avoids spending design tokens on every artifact.
