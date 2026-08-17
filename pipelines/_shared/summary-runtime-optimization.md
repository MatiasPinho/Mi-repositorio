# Summary runtime optimization contract

This contract is loaded only by `pipelines/resumen.md`. It reduces avoidable model work without weakening academic or visual gates.

## Deterministic before perceptual
- Geometry that code can prove must fail before vision review. In particular, an arrow/connector path whose final-display length is too short for its marker footprint is a deterministic preflight failure (`arrow-shaft-too-short`) and consumes no reviewed attempt.
- Hash equality, asset identity, responsive variant identity, bounds, collisions, empty semantic shapes and own-label crossings remain deterministic facts. Never ask a model to re-prove them.

## Fidelity risk ledger before prose
Before drafting, run:

```bash
python scripts/venv_exec.py scripts/fidelity_constraints.py \
  --course <course> --scope "<scope>" \
  --write <run-dir>/02-fidelity-constraints.json
```

This is not an AI stage. It filters already-structured canonical claims to risky groups.

Rules:
- `unresolved` → attribute the competing evidence; never pick a winner or use source-count majority as a substitute for canonical resolution.
- `split-view` → keep `academic_truth` and `assessment_expectation` separate.
- resolved contradictory evidence → use the canonical resolved view while keeping source disagreement explicit only when pedagogically relevant.
- Add any non-claim canonical `likely`, `unknown` or `excluded` item that the summary is likely to mention to `02-plan.json -> fidelity_constraints`.

The writer must check this ledger before HUMANIZE. The academic reviewer receives the ledger plus only the canonical rows needed to verify the candidate; it must not browse the repository to rediscover already-known contradictions.

## Surgical retries
- Visual repair: only failed/changed scenes are repaired and reviewed; byte-identical PASS rows are carried forward mechanically.
- Academic repair: edit only cited sentences/sections. The second review gets the repaired candidate, first-review findings, the fidelity ledger and canonical support for the failed claims. Do not repeat repository exploration, visual review or humanization of unchanged prose.
- Browser audit remains deterministic integration QA, not another open-ended vision pass.

## Publication handoff
Use the exact report path required by finish:

```bash
python scripts/venv_exec.py scripts/publish_artifact.py \
  --markdown <accepted-md> --html <run-dir>/09-rendered.html \
  --dest-markdown <published-md> --dest-html <published-html> \
  --report <run-dir>/11-publication.json
```

Do not create `11-publish.json` and rename it later.

## Runtime target
Standard summary: 10–20 minutes target. Thirty minutes is a performance warning. Sixty minutes or more is a product/runtime failure. These are engineering targets, not permission to skip required fidelity gates.
