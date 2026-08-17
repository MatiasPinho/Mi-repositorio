# Shared contract: semantic study-document lifecycle

This contract applies only when an owning pipeline explicitly loads it. It currently defines the common staged lifecycle for `resumen` and `repaso`.

The owning pipeline remains responsible for academic purpose, scope, artifact kind, visual policy, commands and destination paths. Pipeline-specific instructions may add stricter gates or intermediate stages, but must not skip, weaken or contradict this contract.

## Scope and ingestion boundary
1. Resolve the request to exactly one stable `unit_id` before semantic artifact work.
2. Require canonical concepts for the resolved unit. If empty, stop with **NEEDS_INGESTION** before starting the run.
3. `procesar` may run only as a separate prerequisite action. Never ingest or edit canonical academic/concept/topic knowledge inside an active semantic artifact run.
4. Prefer the owning pipeline's coarse-grained Study MCP context operations when connected; otherwise use deterministic unit-scoped files plus explicit prerequisites.

## Run boundary
1. Start a portable run with `scripts/pipeline_run.py start`.
2. Treat the run snapshot as an isolation boundary. Do not modify engine/rules/contracts/design/tests while the study run is active.
3. Do not mutate canonical academic, concept or topic state. Figure mutations are allowed only when the owning pipeline explicitly authorizes reviewed deterministic finalization.
4. Temporary helper code belongs only under the run's `scratch/` directory.
5. If an engine capability is broken, stop with **ENGINE FAILURE**; never patch the engine inside the active run and continue publishing.

## Common staged lifecycle
The canonical filenames below are shared by semantic document pipelines. Owning pipelines may add stricter evidence files/stages.

1. **PLAN** → write `02-plan.json` from canonical knowledge. No polished prose.
2. **OPTIONAL PRE-DRAFT BUILD / REVIEW STAGES** → run deterministic builds and any owning-pipeline review that must complete before drafting. A V2 visual preview plus independent rendered-image review belongs here: perceptual review is not called deterministic merely because its screenshot/hash binding is deterministic.
3. **DRAFT** → write `03-draft.md` only after mandatory pre-draft stages pass.
4. **HUMANIZE** → read `vendor/humanizer/SKILL.md` and edit only student-facing prose into `04-humanized.md`; preserve academic meaning, certainty, semantic callouts and image markup.
5. **INDEPENDENT REVIEW** → evaluate `04-humanized.md` against canonical state and every rubric required by the owning pipeline. Act as an **independent critic**: audit high-risk claims first, then candidate internal consistency, and write `05-review.json` without inheriting writer justifications.
6. **ACCEPT OR REPAIR ONCE**:
   - if `05-review.json` passes, copy `04-humanized.md` to `06-final.md`;
   - if it fails, preserve evidence, write one targeted `06-repair.md`, review into `07-review.json`, and only on PASS copy to `08-final.md`;
   - do not run a third academic review/repair cycle.
7. **RENDER CANDIDATE** → produce the exact final `09-rendered.html` required by the owning pipeline. A pipeline may first create `09-rendered-base.html` and apply a deterministic responsive transform, but only `09-rendered.html` is the candidate that proceeds to integrity/publication.
8. **INTEGRITY GATE** → validate accepted Markdown plus final HTML with the owning pipeline's deterministic integrity command and persist `10-integrity.json`. Do not publish unless `ok: true`.
9. **BROWSER VISUAL GATE** → run the browser auditor specified by the owning pipeline against final `09-rendered.html`, require `visual-audit/audit.json -> ok: true`, and inspect required screenshot evidence against `rules/evaluation/visual-rubric.md`. For V2 this includes per-scene desktop/mobile crops in addition to document screenshots. Missing Playwright/Chromium or unavailable required screenshots is incomplete visual review, not permission to downgrade the gate.
10. **ATOMIC PUBLISH** → publish only after all required gates pass. Leave accepted run Markdown and `09-rendered.html` byte-for-byte unchanged. Deterministic rebasing of local image/srcset references is allowed only in published destinations and every rewritten reference must resolve to the same physical asset. The publication report keeps immutable `source_sha256` plus transformed `published_sha256` / destination hashes.
11. **MARK + FINISH** → mark the published artifact, then finish with `scripts/pipeline_run.py finish`. Owning-pipeline fingerprint/figure/publication checks remain mandatory.

## Review-bound visual distinction
Academic/pedagogical review can judge whether a visual was a good teaching choice from plan/content context. It cannot certify rendered execution without images. When an owning pipeline requires a pre-draft vision review, the visual creator and visual reviewer must be independent executions/contexts and the reviewer must actually receive the rendered previews.

## Environment contract
A complete semantic document run requires the repository-local `.venv` installed by the project setup flow. Check readiness with `python scripts/venv_exec.py scripts/setup_env.py check`. Missing `.venv`, Playwright or Chromium is an environment failure.

## Context discipline
Do not reread full raw transcripts merely to imitate teacher wording or add volume. Pull raw evidence only when needed to resolve a missing or ambiguous canonical point. Quotes and timestamps remain internal unless exact wording materially matters.
