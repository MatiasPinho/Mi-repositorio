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
- `figures.css` — instructional figures and handwritten-style captions without filtering the source image.
- `print.css` — A4/paged-media behaviour that keeps the notebook identity without printing binding holes.

## Composition rules

1. Ordinary prose is capped at a comfortable reading measure. Do not widen it just because the sheet has space.
2. Binding holes, ruled lines and the red margin are chrome owned by CSS. Never write them into artifact HTML or Markdown.
3. Major sections use compact `§N` markers because the number represents real document order.
4. Figures, tables and code may use more width than prose but stay visually attached to the explanation they support.
5. Semantic meaning is always written in words. Colour, marker strokes and handwriting can reinforce a role but never define it alone.
6. Handwriting is an accent for annotations, exam relevance and captions. Body explanations remain in the practical reading face.
7. Retrieval prompts remain visible and include answer space; they are study material, not collapsible UI.

## Type

IBM Plex Sans is the body/display face and IBM Plex Mono handles utility text and code. Handwritten accents use system handwriting fallbacks so the artifact works offline without bundling fonts.

## Responsive behaviour

Desktop preserves the binding margin and punched-hole cue. Tablet/mobile progressively remove decorative binding chrome before it can steal reading width; the ruled sheet and semantic hierarchy remain. Long-guide navigation becomes a normal block above the document rather than squeezing the page.

## Dark mode

Dark mode is explicit opt-in. It keeps the same hierarchy and notebook grammar, with subdued rules and warm annotation ink; it must never invert source figures or alter their academic meaning.

## Rule

Change the design here, then rebuild `assets/study-theme.css`. Do not hand-edit generated theme output as the source of truth.
