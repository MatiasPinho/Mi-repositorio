# Summary runtime optimization contract

This contract is loaded only by `pipelines/resumen.md`. Its purpose is to reduce avoidable model work without weakening academic fidelity.

## Published artifact truth
A finished historical run is not proof that a summary is currently published. Before stopping because a summary supposedly already exists, run:

```bash
python scripts/venv_exec.py scripts/summary_presence.py \
  --course <course> --scope "<scope>"
```

Only `published: true` means the current Markdown+HTML pair exists under the resolved unit's `resumenes/` directory. Historical runs, registered figures and old publication reports are cache/evidence only.

## Deterministic before model work
- Use code for hashes, asset identity, bounds, collisions, responsive identity and other objective checks.
- A deterministic preflight failure consumes no vision-review attempt. This includes the established `arrow-shaft-too-short` guard for arrow/connector paths whose marker would consume the readable shaft at final display size.
- Never ask a model to compare hashes or re-approve byte-identical evidence.
- `02-visual-build.json` must come from the deterministic finalizer; integrity reconstructs it independently.
- Never patch engine code during an active study run.

## Visual work budget
The AI remains free to choose the semantic composition and drawing of a schema-2 scene. Runtime is controlled by limiting review loops, not by restricting that creative freedom.

For each current V2 scene:
1. Render the initial preview after deterministic preflight.
2. Run one independent vision-review batch for all new/changed scenes.
3. If a scene fails, allow exactly one model-authored repair of that failed scene and one final vision review of the changed evidence.
4. There is no third visual review. New runs may create at most two reviewable/rendered attempts per scene.
5. If a scene still fails after the final review, omit that scene from the current summary plan and continue with the remaining visuals. A failed optional illustration must not prevent production of the textual summary.

Unchanged PASS scenes are carried forward mechanically. Do not re-render or re-review them.

A deterministic preflight failure may be repaired, but do not enter an open-ended geometry loop. If a scene cannot be made mechanically renderable with a targeted repair, omit it from the current summary instead of repeatedly redesigning it.

## V2 reuse
A prior V2 PASS may be reused only when the current scene bytes, permanent wide/narrow SVG hashes and active visual-policy fingerprint are identical to the prior independently reviewed evidence. In that exact case use `scripts/visual_reuse_v2.py` and do not call a vision model.

A visual-policy change invalidates the old PASS for reuse, but it does not by itself force the old composition to be redesigned before anyone sees it. The exact scene may be previewed under the current policy and judged in the normal single review batch. If it fails and must change, use a new append-only scene id for the repaired geometry; never overwrite an already registered V2 revision.

Legacy V1 registered deterministic sketches remain immutable reusable assets and stay outside V2 vision review.

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
- Visual: at most one repair round; only failed/changed scenes are touched. After the second reviewed attempt, omit remaining failed scenes and continue. No third review.
- Academic: edit only cited sentences/sections. The second review gets the repaired candidate, first-review findings, fidelity constraints and complete canonical support for the failed/high-risk claims. Do not repeat visual review or humanization of unchanged prose.
- Browser audit is deterministic integration QA, not another open-ended vision pass.

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
A standard summary on a capable hosted model targets roughly 10–20 minutes. Thirty minutes is a performance warning; sixty minutes or more is a product/runtime failure. These targets never justify weakening academic fidelity.