# Study Design System

Canonical source for the student-facing visual system. Ordinary `/resumen`, `/guia` and `/repaso` runs consume this frozen system instead of restyling each artifact.

Direction: **university study notebook**. The reading surface should feel like a carefully made set of class notes rather than a dashboard or a faux textbook: ruled paper, a restrained binding margin, compact `§` section markers, practical sans-serif typography, selective marker emphasis, and handwritten accents only where a student would naturally annotate something.

The notebook cues are structural CSS, not content. Markdown remains semantic and the same renderer must work for every subject.

The previous **contemporary technical manual** direction remains preserved in repository history; this redesign deliberately replaces its page grammar with the notebook system while keeping the same semantic Markdown and renderer contract.

## Files

- `tokens.css` — notebook surfaces, ink, semantic hues, type roles, line rhythm, measure and spacing.
- `typography.css` — sustained-reading type, marker emphasis, code and baseline rhythm.
- `layout.css` — notebook sheet, CSS-only binding/margin, running line, section marks, progress and long-guide index.
- `components.css` — semantic notes, exam annotations, retrieval worksheet, tables and apparatus captions.
- `figures.css` — instructional figures and handwritten-style captions without filtering the source image. Semantic `reinterpret` / `preserve` decisions belong to `rules/visual/figures.md`, not to CSS.
- `print.css` — A4/paged-media behaviour that keeps the notebook identity without printing binding holes.
- `assets/notebook-reader.css` / `assets/notebook-reader.js` — physical leaf pagination, front/back flipping and stacked-sheet navigation layered on top of the canonical notebook theme. They do not redefine typography, content components or academic semantics.

Deterministic derived diagrams are rendered by `scripts/sketch_figure.py`. Its
SVG canvas is always transparent: the notebook paper and rules remain owned by
CSS and show through the drawing. The generator uses a restrained
graphite/ink subset of the notebook palette, while the planner remains limited
to semantic tones and structure. The renderer removes the normal image plate
only for SVGs carrying the deterministic sketch marker. Source images are never
filtered or converted by that generator.

## Composition rules

1. Ordinary prose is capped at a comfortable reading measure. Do not widen it just because the sheet has space.
2. The right rail stays intentionally empty for future drawings and notes; summaries do not place a persistent guide, progress widget or topic tabs there.
3. Binding holes, ruled lines and the red margin are chrome owned by CSS. Never write them into artifact HTML or Markdown.
4. Major sections use compact `§N` markers because the number represents real document order.
5. Figures, tables and code may use more width than prose but stay visually attached to the explanation they support.
6. Semantic meaning is always written in words. Colour, marker strokes and handwriting can reinforce a role but never define it alone.
7. Handwriting is an accent for annotations, exam relevance and captions. Body explanations remain in the practical reading face.
8. Retrieval prompts remain visible and include answer space; they are study material, not collapsible UI.

## Physical leaf reader

On desktop-sized summary surfaces, the continuous semantic article may be deterministically paginated into physical leaves without changing its content. Each leaf has a front and a back. The current leaf stays centered while its immediate neighbours remain partially visible behind it, like a stack of paper.

Navigation follows the paper metaphor:

- clicking a visible neighbouring sheet brings that physical leaf to the front;
- only the bottom corner of the active sheet controls front/back flipping, leaving the page body free for text selection and future highlighting or handwriting;
- left/right keyboard arrows provide an accessible secondary way to move between physical leaves;
- each top-level topic heading is its own full-title index tab at the exact point where that topic starts; its title keeps the original left alignment while a translucent warm-pencil tab protrudes into the left margin and lets the ruled paper and margin line remain visible through its shading; every tab permanently repeats the menu index's blue double contour and inset blue rail, while the current topic uses denser pencil shading; tab spacing stays on whole notebook-line increments so later prose never drifts off the ruled rhythm, and `T` opens that full keyboard-accessible index in both physical and continuous views without a permanently visible shortcut label;
- `V` opens a ruled-paper reading-view selector instead of changing modes immediately; its `Hojas` and `Continua` choices pair plain-language explanations with small CSS pencil sketches, expose radio semantics and full keyboard navigation, and keep `Hojas` visible but unavailable where the physical reader cannot run;
- pagination never introduces inner scrolling or clips an oversized semantic block. If a safe page split cannot be produced, the reader falls back to the proven continuous document;
- print stays continuous and paged-media driven rather than printing the interactive 3D stack;
- mobile keeps the continuous reading surface rather than shrinking a desktop-sized physical sheet.

The reader is presentation state only. It must never change Markdown, academic wording, figure provenance or canonical knowledge. Its CSS/JS participate in the visual artifact fingerprint so changes correctly stale previously rendered visual artifacts.

## Type

IBM Plex Sans is the body/display face and IBM Plex Mono handles utility text and code. Handwritten accents use system handwriting fallbacks so the artifact works offline without bundling fonts.

## Responsive behaviour

Desktop preserves the binding margin and uses three restrained punched-hole cues per physical sheet. Tablet can use the physical reader while enough width remains; mobile progressively removes decorative binding chrome and keeps the continuous article so the reading measure never becomes artificially small. Long-guide navigation remains a normal continuous surface rather than being forced into the leaf reader.

## Dark mode

Dark mode is explicit opt-in. It keeps the same hierarchy and notebook grammar, with subdued rules and warm annotation ink; it must never invert source figures or alter their academic meaning.

## Rule

Change the canonical notebook theme in `design/`, then rebuild `assets/study-theme.css`. The physical reader is a separate presentation layer in `assets/notebook-reader.css` and `assets/notebook-reader.js`; changes to it must preserve the same semantic renderer contract and visual-audit gates.
