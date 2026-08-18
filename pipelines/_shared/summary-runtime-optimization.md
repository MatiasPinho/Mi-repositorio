# Summary runtime optimization contract

This contract is loaded only by `pipelines/resumen.md`. Its purpose is to reduce avoidable model work without weakening academic fidelity or pedagogical visual selection.

## Published artifact truth
A finished historical run is not proof that a summary is currently published. Before stopping because a summary supposedly already exists, run:

```bash
python scripts/venv_exec.py scripts/summary_presence.py \
  --course <course> --scope "<scope>"
```

Only `published: true` means the current Markdown+HTML pair exists under the resolved unit's `resumenes/` directory. Historical runs, registered figures and old publication reports are cache/evidence only.

## Deterministic before model work
- Use code for hashes, asset identity, collisions, registration, image cleanup and other objective checks.
- Never ask a model to compare hashes or re-approve byte-identical evidence.
- `02-visual-build.json` must come from `scripts/visual_plan_hybrid.py`; do not hand-write it.
- Never patch engine code during an active study run.
- Exact registered diagram or illustration reuse is mechanical and must not spend a model/provider call.

## Visual selection is pedagogical, not a runtime shortcut
Runtime optimization begins **after** the planner decides whether a visual materially improves learning.

- `visual_not_needed` is a pedagogical judgment. Never choose it merely to save tokens, time, provider work or implementation effort.
- If a concept is spatial, structural, causal, temporal, relational or physically recognizable and a figure would materially improve understanding, keep `visual_required` / `visual_helpful` exactly as the visual rules require.
- A selected optional illustration may be omitted only after the bounded provider/fallback path fails.
- A post-failure omission is a runtime fallback for that run, not evidence that the concept was pedagogically better without a visual and not a precedent for future PLAN decisions.

## Active hybrid visual budget
The summary model does semantic planning, not graphic production.

### Deterministic diagrams
Use `visual_medium: diagram` whenever exact structure, order, topology, direction, chronology, label or quantity matters. The model writes only the compact schema-1 semantic sketch spec. `scripts/visual_plan.py` remains the deterministic diagram backend and `scripts/visual_plan_hybrid.py` dispatches to it.

Do not author raw SVG, explicit coordinate-heavy scenes, separate wide/narrow geometry or visual-review repair loops.

### Generated illustrations
Use `visual_medium: illustration` only for optional physical/recognition support and only with `visual_helpful`.

The planner writes a compact semantic illustration object. Carpeta constructs the provider prompt, applies the fixed pencil style, performs one bounded provider request, crops/keys the white background to transparency and registers the resulting notebook overlay.

Runtime rules:
1. one provider request per new illustration spec;
2. zero provider calls for exact registered reuse;
3. no independent per-illustration vision-review/regeneration loop;
4. if the provider is unavailable, make at most one run-local fallback decision: switch to a deterministic diagram only when the same supported meaning is naturally diagrammable, otherwise omit that optional illustration for the run;
5. a generated-image failure never blocks or weakens the textual academic summary.

Browser audit is final integration QA, not an illustration-refinement session.

## Why this boundary exists
The retired free-composition V2 experiment remains available in the repository for compatibility/testing, but it is not in the normal summary critical path. New summaries must not spend model time authoring large scene-graph geometry, responsive wide/narrow variants or per-scene independent visual-review loops before prose drafting.

Legacy V2 regression coverage remains valid for the dormant engine, including the deterministic `arrow-shaft-too-short` preflight guard. Keeping that regression does not place the V2 engine back on the active summary path.

## Fidelity risk ledger before prose
Before drafting, run:

```bash
python scripts/venv_exec.py scripts/fidelity_constraints.py \
  --course <course> --scope "<scope>" \
  --write <run-dir>/02-fidelity-constraints.json
```

This is deterministic. It surfaces already-structured risky canonical claims before prose is written.

Rules:
- `unresolved` → attribute competing evidence; never choose a winner by source count.
- `split-view` → keep `academic_truth` and `assessment_expectation` separate.
- resolved contradictory evidence → use the canonical resolved view.
- keep non-claim `likely`, `unknown` or `excluded` constraints the summary may mention in the plan.

The writer checks the ledger before HUMANIZE. The academic reviewer must receive enough canonical evidence to verify every high-risk claim in the candidate; runtime optimization must not reduce semantic coverage.

### Deterministic unresolved-conflict guard
After HUMANIZE and before independent academic review, run:

```bash
python scripts/venv_exec.py scripts/fidelity_guard.py \
  --markdown <run-dir>/04-humanized.md \
  --constraints <run-dir>/02-fidelity-constraints.json \
  --write <run-dir>/04-fidelity-guard.json
```

`ok: false` is a hard pre-review failure. Repair only the cited wording before spending an academic-review call. If the first academic review requires `06-repair.md`, run the same guard on the repair before the second/final review.

## Surgical retries
- Visual: no open-ended retries. Deterministic diagrams are idempotent; a new illustration gets one provider call and at most one fallback decision.
- Academic: edit only cited sentences/sections. The second review gets the repaired candidate, first-review findings, fidelity constraints and complete canonical support for the failed/high-risk claims. Do not regenerate unchanged visuals or re-humanize unchanged prose.
- Browser audit is deterministic integration QA, not another generation/review pass.

## Publication handoff
Use the exact report path required by finish:

```bash
python scripts/venv_exec.py scripts/publish_artifact.py \
  --markdown <accepted-md> --html <run-dir>/09-rendered.html \
  --dest-markdown <published-md> --dest-html <published-html> \
  --report <run-dir>/11-publication.json
```

## Deterministic runtime report
After successful publication and before `pipeline_run.py finish`:

```bash
python scripts/venv_exec.py scripts/run_timing.py \
  --run <run-dir> --write <run-dir>/12-runtime.json
```

Use the report for stage timings; do not estimate them from memory.

## Runtime target
A standard summary on a capable hosted model targets roughly 10–20 minutes. Thirty minutes is a performance warning; sixty minutes or more is a product/runtime failure. These targets never justify weakening academic fidelity or omitting a pedagogically useful visual during PLAN.
