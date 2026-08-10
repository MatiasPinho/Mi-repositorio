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
- `academic_issues`, `pedagogy_issues` and `visual_issues` are empty.

A score cannot override a concrete issue. If the reviewer finds a taxonomy mismatch, unsupported claim, certainty drift or internal contradiction, the review fails even when the prose is otherwise excellent.

If `05-review.json` fails, produce targeted feedback, write exactly one repair pass to `06-repair.md`, then review that repair into `07-review.json`. If it passes, copy the accepted repair to `08-final.md`. Maximum two review cycles total; do not loop indefinitely.

## Reviewer independence
When the execution environment supports isolated agents/contexts, prefer an independent reviewer that receives only: candidate artifact, canonical state needed for scope, and evaluation rules. Otherwise simulate independence through the portable handoff boundary: re-read only those files and do not rely on the writer's self-justifications, plan rationale or previous score.

The reviewer must first compare claims to canonical state, then perform a separate candidate-vs-candidate consistency pass. Do not infer correctness from fluent prose or from the fact that the draft followed the plan.

## Cost rule
Do not add a pipeline stage unless it prevents a distinct failure mode. Short/simple outputs may use the pipeline's documented fast path.
