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
- the final Markdown figure ids/assets agree with every selected treatment in `02-plan.json`; in particular, `reinterpret` never silently resolves to a source asset.

`visual_support` evaluates visual selection, representational fit and truth preservation. A generated illustration is optional recognition support, not authoritative academic evidence.

A score cannot override a concrete issue. If the reviewer finds a taxonomy mismatch, unsupported claim, certainty drift or internal contradiction, the review fails even when the prose is otherwise excellent.

If `05-review.json` fails, produce targeted feedback, write exactly one repair pass to `06-repair.md`, then review that repair into `07-review.json`. If it passes, copy the accepted repair to `08-final.md`. Maximum two academic/prose review cycles total; do not loop indefinitely.

## Active hybrid visual execution gate
Every planned selected visual is materialized before DRAFT through `scripts/visual_plan_hybrid.py`.

The gate distinguishes three jobs:

- `diagram`: exact structure uses the compact deterministic schema-1 SVG generator;
- `illustration`: optional recognizable/physical support uses one bounded generated-image call and deterministic transparent-overlay cleanup;
- `source`: precision-sensitive source evidence remains unchanged.

A final `02-visual-build.json` with `ok: true` is required before drafting. The report must bind the current `02-plan.json` hash to the exact registered assets.

Generated illustration rules are strict:
- only `visual_helpful` may use `illustration`;
- no academic text, numbers, arrows, formulas, chronology or exact topology may depend on generated pixels;
- there is no independent per-illustration vision-review/regeneration loop;
- provider failure allows at most one run-local fallback decision and never weakens or blocks the textual summary.

The final candidate then uses `artifact_integrity.py` plus `visual_audit.py`. Browser audit validates the actual notebook integration on desktop/mobile and may reject broken, blank, misleading or opaque-card illustrations, but it must not become an open-ended generation loop.

## Legacy V2 compatibility
The schema-2 free-composition scene engine and its independent vision-review machinery remain available for historical runs, experiments and regression tests. They are not a required execution gate for the active summary hybrid path.

## Reviewer independence
When the execution environment supports isolated agents/contexts, prefer an independent academic reviewer that receives only the candidate/evidence needed for its role and the relevant evaluation rules. Otherwise simulate independence through the portable handoff boundary and do not inherit the creator's self-justifications.

Academic review must compare claims to canonical state before candidate consistency. Visual-support review checks semantic selection and truth; rendered-browser audit checks final integration.

## Cost rule
Do not add a pipeline stage unless it prevents a distinct failure mode. Exact diagram materialization, bounded generated illustration, academic review, deterministic integrity and final browser audit each protect a different boundary. Do not reintroduce a separate model-authored scene-design/review loop when the same teaching job is covered by the hybrid path.
