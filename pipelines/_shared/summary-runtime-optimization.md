# Summary runtime optimization contract

This contract is loaded only by `pipelines/resumen.md`. It reduces avoidable model work without weakening academic or visual gates.

## Published artifact truth
A finished historical run is **not** proof that a summary is currently published. Before deciding that a summary-generation request can stop because an artifact already exists, run:

```bash
python scripts/venv_exec.py scripts/summary_presence.py \
  --course <course> --scope "<scope>"
```

Only `published: true` means a current Markdown+HTML pair exists under the resolved unit's `resumenes/` directory. `.study/runs/`, old publication reports, figure registrations and artifact history are cache/evidence only. If the user deleted the published summary pair, summary generation must start a new run even when old finished runs still exist.

## Deterministic before perceptual
- Geometry that code can prove must fail before vision review. In particular, an arrow/connector path whose final-display length is too short for its marker footprint is a deterministic preflight failure (`arrow-shaft-too-short`) and consumes no reviewed attempt.
- Hash equality, asset identity, responsive variant identity, bounds, collisions, empty semantic shapes and own-label crossings remain deterministic facts. Never ask a model to re-prove them.
- `02-visual-build.json` is deterministic finalizer output, not model-authored evidence. Integrity reconstructs the expected build from plan + preview + policy-bound review + deterministic rerender + canonical registry/assets and requires exact equivalence.
- Never patch engine code during a running study pipeline to make the candidate pass. `scripts/venv_exec.py` guards the active run before target commands execute; observed engine drift writes a sticky run-local violation marker, so reverting the edit does not make that run valid again.

## Registered visual reuse vs cross-run scene PASS reuse
There are two different reuse paths and they must not be confused.

### A. Already-registered immutable derived figures
A mixed summary run may reuse an already-registered **legacy V1 deterministic sketch** without creating a new `scene_spec`. `visual_plan_v2.py` validates its stable unit, treatment, provenance, source companion when applicable, registered asset hash and legacy spec hash, then reports it under `reused_registered`.

Rules:
- a registered legacy row is **not** a current V2 scene and must not be sent through preview or vision review again;
- its absence of `scene_spec` is not a reason to fall back to previewing every visual in the plan;
- in a mixed run, `02-visual-preview.json -> entries` contains only current V2 scenes that actually need preview/review; `reused_registered` contains immutable legacy reuse;
- finalization carries both sets into one `02-visual-build.json`;
- integrity validates reused legacy asset/spec hashes deterministically.

Therefore, if four registered legacy figures are reused and one new V2 scene is added, the expected visual work is **one previewed/reviewed scene, not five**.

A previously registered **V2** scene is different: registry metadata alone is never a new visual PASS. Before any V2 cross-run reuse or preview, run the policy-composition guard:

```bash
python scripts/venv_exec.py scripts/visual_scene_policy_guard.py \
  --course <course> --unit "<scope>" \
  --plan <run-dir>/02-plan.json \
  --write <run-dir>/02-visual-policy-guard.json
```

`ok: false` is a hard **pre-preview** design failure. If a byte-identical registered V2 composition has no independent PASS under the current visual policy, the old scene is only historical reference. Reconsider the concept from canonical knowledge under the current `figures.md` + `visual-rubric.md`, create a **new scene id + `derived_figure_id`**, update the plan and rerun the guard. Do not send the stale composition to vision merely to ask whether the new policy still likes it.

This is deliberately stronger than invalidating only the old PASS: a policy change means the old composition itself is no longer the default candidate. It prevents a stale generic-box scene from being mechanically re-presented to a new reviewer. Registered V2 ids remain immutable append-only history; changed geometry/semantics always use a new revision id.

Only when `02-visual-policy-guard.json -> ok: true` may an exact registered V2 scene be materialized into the current run for cross-run PASS reuse.

### B. Cross-run V2 visual PASS reuse
A rerun may reuse a previous V2 visual PASS only when the current scene spec and registered wide/narrow SVG assets are byte-identical to evidence from a previous independent PASS **and the visual pedagogy/review policy is unchanged**.

The policy has two bindings:
1. the prior run's engine-snapshot hashes for `rules/visual/figures.md` and `rules/evaluation/visual-rubric.md` must still match; and
2. the prior `02-visual-preview.json` and `02-visual-review.json` must carry the same explicit `visual_policy_sha256` fingerprint as the current policy.

Changing either rule invalidates the old perceptual PASS even if scene and PNG bytes stayed identical. Do not copy an old review and merely replace its policy hash; that is a new-policy review and requires current independent vision inspection.

When the policy-composition guard has passed and the plan intentionally reuses an already-reviewed V2 scene, materialize the exact registered scene JSON into the current run's `02-scenes/`. Then, before normal preview, run:

```bash
python scripts/venv_exec.py scripts/visual_reuse_v2.py \
  --course <course> --unit "<scope>" \
  --plan <run-dir>/02-plan.json \
  --review-write <run-dir>/02-visual-review.json \
  --write <run-dir>/02-visual-reuse.json
```

If `all_reused: true`:
- the utility has verified current visual-policy hashes + policy fingerprint + current scene SHA + permanent wide/narrow SVG hashes + prior preview PNG hashes + prior independent PASS;
- it copies the old reviewed evidence into the new run and mechanically rebinds paths/hashes;
- run the normal `visual_plan_v2.py preview` next. It must report the seeded scenes as reused without rendering/screenshotting them again;
- **do not call a vision model**. Use the mechanically carried `02-visual-review.json` and proceed to the normal `visual_plan_v2.py finalize` command;
- integrity/browser/publication/finish remain unchanged.

If `all_reused: false`, the utility must not claim a PASS. Continue through normal preview + independent vision review **only for the current V2 entries returned by preview**. Registered legacy reuse stays outside that review set. Partial/mismatched V2 PASS reuse remains conservative: fall back for those V2 scenes rather than fabricate or combine unverifiable review evidence.

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

### Deterministic unresolved-conflict guard
After HUMANIZE and before the independent academic reviewer, run:

```bash
python scripts/venv_exec.py scripts/fidelity_guard.py \
  --markdown <run-dir>/04-humanized.md \
  --constraints <run-dir>/02-fidelity-constraints.json \
  --write <run-dir>/04-fidelity-guard.json
```

`ok: false` is a hard pre-review failure: repair the cited wording before spending an academic-review call. The guard catches explicit winner language such as choosing the version with "more sources" or saying an unresolved version is "the one followed here". It is a narrow deterministic safety net, not a replacement for semantic academic review.

If the first academic review requires `06-repair.md`, run the same guard against the repaired Markdown before the second/final review. Never send a candidate with a known deterministic fidelity violation to another model.

## Surgical retries
- Visual repair: only failed/changed scenes are repaired and reviewed; byte-identical PASS rows are carried forward mechanically only while the visual policy is unchanged. A policy-stale registered V2 composition is redesigned under a new append-only id **before preview**; a changed already-registered V2 scene is never overwritten.
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

## Deterministic runtime report
After successful publication and before `pipeline_run.py finish`, emit real stage timings from the canonical handoff-file mtimes:

```bash
python scripts/venv_exec.py scripts/run_timing.py \
  --run <run-dir> --write <run-dir>/12-runtime.json
```

Report the resulting stage table to the user. Do not estimate "content took ~10 minutes" from memory. The report separates PLAN, VISUAL_BUILD, DRAFT, HUMANIZE, ACADEMIC_REVIEW, RENDER, INTEGRITY, BROWSER_AUDIT and PUBLISH.

## Runtime target
Standard summary on a capable hosted model: 10–20 minutes target. Thirty minutes is a performance warning. Sixty minutes or more is a product/runtime failure. These are engineering targets, not permission to skip required fidelity gates. Slower free/community models may reasonably exceed the hosted-model target; use `12-runtime.json` to distinguish model latency from avoidable engine work.
