# Transcript processing

Transcripts are evidence, not prose templates.

Extract:
- what was taught;
- examples and clarifications;
- teacher emphasis;
- recurring confusion/questions;
- explicit scope/rule statements;
- timestamps and speaker when useful for audit.

Before semantic interpretation, `scripts/claim_candidates.py` may register deterministic candidates for explicit assessment scope, grading rules, definitions and change signals. Those candidates remain `pending` evidence until reviewed during `procesar`.

Do **not** build student notes by concatenating or lightly cleaning teacher quotations. Convert speech into structured meaning. Exact quotations are retained only as evidence when wording itself matters.

Ambiguous statements remain ambiguous. Candidate emphasis detected mechanically by scripts is not automatically an academic rule. A raw `teacher_transcript` candidate must never be upgraded to `teacher_explicit` merely because its wording sounds definitive, and an automatic change signal must never declare `supersedes` on its own.
