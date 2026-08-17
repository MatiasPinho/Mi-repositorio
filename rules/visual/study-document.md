# Study document visual system

Student-facing documents are **learning documents**, not raw Markdown dumps or miniature web apps. Markdown remains the portable semantic source; rendered HTML is the primary reading artifact.

## Evidence-informed defaults
- Use a comfortable single reading column; target roughly 60–75 characters per line and never design ordinary prose for >80.
- Body text must support sustained on-screen reading.
- Use left alignment, never full justification.
- Use generous but not extreme leading and clear paragraph separation.
- Headings form a real hierarchy and describe what the section teaches.
- Maintain high luminance contrast. Color is a cue, never the only carrier of meaning.
- Prefer whitespace/grouping over generic card borders.

## Carpeta notebook structure
The active product direction is the **university study notebook** defined in `design/README.md`, not the historical technical-manual direction. The renderer owns this grammar:
1. course/subject + artifact type + scope in quiet running metadata;
2. a restrained chapter opening with H1 and orienting lede;
3. ruled warm paper and a stable binding/margin cue supplied by CSS;
4. compact section markers and semantic role labels;
5. practical reading typography for body explanations;
6. selective marker/handwriting accents where a student would naturally annotate;
7. figures/tables/code may use more width than prose;
8. retrieval material remains visible near coherent concept groups.

Ruled paper, binding holes/margin cues and deterministic pencil figures are intentional product grammar. Do not treat them as fake-paper defects. Also do not escalate the metaphor into scrapbook/vintage decoration, heavy grain, distressed edges, stickers or unrelated ornament.

Do not repeat the unit label inside the title when the renderer already receives `--scope`.

## Emphasis
- **Bold** is the default emphasis for a term or decisive phrase.
- Do not underline normal emphasis; underlining is for links.
- Do not highlight whole paragraphs.
- Do not use ALL CAPS as emphasis.
- Keep each paragraph focused on one idea.

## Semantic callouts
Use supported Markdown callouts only when they earn visual weight:

```markdown
> [!DEFINITION] Optional title
> Precise but understandable definition.

> [!EXAMPLE] Example
> A small example that removes ambiguity.

> [!WARNING] Common mistake
> A trap, contradiction or exception.

> [!EXAM] Exam relevance
> Only if assessment relevance is supported.

> [!CONNECTION] Connection
> A useful relationship to another concept.

> [!RECALL] Check yourself
> A retrieval question, preferably answerable without rereading.
```

The renderer owns the stable semantic role label (`Definición`, `Ejemplo`, `Cuidado`, `Error típico`, `Relación`, `Recuperación`). Optional specific titles appear as content terms and never replace the semantic role. Meaning never depends on color alone.

## Color semantics
The renderer owns exact colors. Writers choose semantic roles only:
- definition/concept → blue family;
- example/application → green family;
- warning/error/uncertainty → amber/red according to severity;
- exam relevance → amber;
- connection/relationship → violet;
- recall/self-test → neutral/blue-gray.

Never invent a new color meaning inside an artifact.

## Figures and free scene composition
Writers still cannot choose local CSS, fonts or exact visual styling. Visual System V2 is a deliberate exception only for **structured figure composition**: a planner may choose scene primitives and geometry through `contracts/scene-figure.schema.json`, while deterministic code owns all concrete style. See `rules/visual/figures.md` and `docs/visual-system-v2.md`.

## Frozen design system
Ordinary student artifacts consume the shared visual system; they do not redesign it per course. Canonical CSS lives in `design/` and compiles to `assets/study-theme.css`. Design-time skills remain maintenance tools rather than ordinary summary-writing instructions.
