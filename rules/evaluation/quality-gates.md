# Quality gates

## Student prose gate
A student-facing artifact passes only if:
- `academic_fidelity` >= 4/5;
- clarity >= 4/5;
- progression >= 4/5;
- explanation >= 4/5;
- signal_to_noise >= 4/5;
- naturalness >= 4/5;
- coverage >= 4/5;
- visual_support >= 4/5;
- every required fidelity check is `pass` or genuinely `not_applicable`;
- every recorded high-risk claim check is `supported`;
- `academic_issues`, `pedagogy_issues` and `visual_issues` are empty;
- the final Markdown figure ids/assets agree with every selected treatment in `02-plan.json`; in particular, `reinterpret` never resolves to a source asset.

`visual_support` evaluates visual selection/pedagogy. It is not permission to claim that a generated V2 scene looks good.

A score cannot override a concrete issue. If the reviewer finds a taxonomy mismatch, unsupported claim, certainty drift or internal contradiction, the review fails even when the prose is otherwise excellent.

If `05-review.json` fails, produce targeted feedback, write exactly one repair pass to `06-repair.md`, then review that repair into `07-review.json`. If it passes, copy the accepted repair to `08-final.md`. Maximum two academic/prose review cycles total; do not loop indefinitely.

## Visual System V2 execution gate
Every planned schema-2 derived scene must pass a separate pre-draft visual lifecycle before drafting begins:

`scene -> deterministic preflight -> wide/narrow PNG preview -> independent vision review -> repair if needed -> finalize/register`.

The vision review follows `rules/evaluation/visual-rubric.md`. It must be bound to exact wide/narrow screenshot SHA-256 values and declare `vision_verified: true`, `capability: vision` and `independent: true`. The designer cannot approve its own scene. Maximum three reviewed visual attempts per scene.

Mechanical preflight success is not visual success. A model without image input must leave visual execution unverified and cannot finalize/register the scene.

Failed attempts remain run-local and never mutate canonical figure state. `02-visual-build.json` version 2 may be produced only by finalization after the current preview and independent review bindings pass. Drafting must not reference an unfinalized V2 scene.

The final candidate must then pass `artifact_integrity_v2.py` plus `visual_audit_v2.py`; the latter captures every published scene at desktop and mobile sizes in addition to the normal document screenshots. A missing crop, broken narrow asset or stale scene/review hash is a publication failure.

## Reviewer independence
When the execution environment supports isolated agents/contexts, prefer an independent reviewer that receives only the candidate/evidence needed for its role and the relevant evaluation rules. Otherwise simulate independence through the portable handoff boundary and do not inherit the creator's self-justifications.

Academic review must compare claims to canonical state before candidate consistency. V2 visual review must inspect the rendered preview images, not the source JSON alone.

## Cost rule
Do not add a pipeline stage unless it prevents a distinct failure mode. The V2 geometry preflight, vision review and final per-scene browser evidence each prevent a different failure mode and are therefore not interchangeable.
