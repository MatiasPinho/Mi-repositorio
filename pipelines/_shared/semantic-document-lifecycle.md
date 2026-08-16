# Shared contract: semantic study-document lifecycle

This contract applies only when an owning pipeline explicitly loads it. It currently defines the common staged lifecycle for `resumen` and `repaso`.

The owning pipeline remains responsible for its academic purpose, scope details, artifact kind, visual policy, commands and destination paths. Pipeline-specific instructions may add stricter gates or intermediate stages, but they must not skip, weaken or contradict this contract.

## Scope and ingestion boundary

1. Resolve the request to exactly one stable `unit_id` before starting semantic artifact work, following `actions/ARGUMENTS.md` and the owning pipeline's stricter scope rules.
2. Require canonical concepts for the resolved unit. If canonical concepts are empty, stop with **NEEDS_INGESTION** before starting the run.
3. `procesar` may run only as a separate prerequisite action when orchestration is available. After successful ingestion, restart the owning pipeline from scope resolution. Never ingest or edit canonical academic/concept/topic knowledge inside an active semantic artifact run.
4. When Study MCP is connected, prefer the coarse-grained context/artifact operations named by the owning pipeline. Otherwise use the deterministic CLI and only the unit-scoped canonical files plus explicit cross-unit prerequisites.

## Run boundary

1. Start a portable run with `scripts/pipeline_run.py start`; the owning pipeline supplies the exact course, pipeline and scope arguments.
2. Treat the run snapshot as an isolation boundary. Do not modify `scripts/`, `pipelines/`, `rules/`, `config/`, `contracts/`, `core/`, `design/`, `study_mcp/`, `tests/` or protected root setup files while the run is active.
3. Do not mutate canonical academic, concept or topic state during the run. Figure mutations are allowed only when the owning pipeline explicitly authorizes them through the deterministic figure tooling and its finish contract.
4. Temporary helper code belongs only under the run's `scratch/` directory.
5. If a required engine capability is broken, stop and report **ENGINE FAILURE** with the diagnostic. Do not patch the engine inside the active study run and then continue publishing.

## Common staged lifecycle

The canonical file names below are shared by the semantic document pipelines. An owning pipeline may add intermediate evidence files, but must preserve this review/publication chain.

1. **PLAN** → write `02-plan.json` from canonical knowledge and the owning pipeline's pedagogical/visual rules. Do not write polished prose during planning.
2. **OPTIONAL BUILD STAGES** → run any deterministic pre-draft build required by the owning pipeline. Such stages must complete successfully before drafting.
3. **DRAFT** → write `03-draft.md` from the accepted plan and canonical knowledge. The artifact must satisfy the owning pipeline's audience and scope contract.
4. **HUMANIZE** → read `vendor/humanizer/SKILL.md` and edit only student-facing prose into `04-humanized.md`. Preserve academic meaning, certainty, semantic callouts and image markup.
5. **INDEPENDENT REVIEW** → evaluate `04-humanized.md` against canonical state and every rubric/contract required by the owning pipeline. Audit high-risk claims first, then run a separate candidate-vs-candidate consistency pass for repeated definitions, taxonomies/counts, conditions and certainty. Write `05-review.json`. Act as an independent critic: do not justify the writer or inherit its assumptions merely because they appeared in the plan.
6. **ACCEPT OR REPAIR ONCE**:
   - if `05-review.json` passes, copy `04-humanized.md` to `06-final.md` and use it as the accepted Markdown;
   - if it fails, preserve the failed candidate/review, write one targeted `06-repair.md`, review that repair independently into `07-review.json`, and only if it passes copy it to `08-final.md` and use that as the accepted Markdown;
   - do not run a third academic review/repair cycle.
7. **RENDER CANDIDATE** → render the exact accepted Markdown to `09-rendered.html` with the owning pipeline's renderer arguments and require its structural check to pass.
8. **INTEGRITY GATE** → validate the accepted Markdown and rendered HTML with the owning pipeline's deterministic integrity command/tool and persist `10-integrity.json`. Do not publish unless it reports `ok: true`.
9. **BROWSER VISUAL GATE** → run `scripts/visual_audit.py` against `09-rendered.html`, require exit code 0 and `visual-audit/audit.json -> ok: true`, and inspect at least `visual-audit/desktop.png` and `visual-audit/mobile.png` against `rules/evaluation/visual-rubric.md`. Required lazy images must be force-loaded and verified by the auditor. If browser dependencies are missing or screenshots cannot be inspected, visual review is incomplete: do not claim PASS and do not publish.
10. **ATOMIC PUBLISH** → publish only after all required gates pass. The publisher must leave the accepted run Markdown and `09-rendered.html` byte-for-byte unchanged. Deterministic rebasing of local image references is allowed only in published destinations and must preserve asset identity. When relocation changes URLs, source and destination hashes need not be equal; require the recorded deterministic transform and destination hash to match instead.
11. **MARK + FINISH** → mark the published artifact through MCP or the deterministic artifact-state CLI, then finish the run with `scripts/pipeline_run.py finish`. The owning pipeline's finish contract may impose additional fingerprint/figure/publication checks and remains mandatory.

## Environment contract

A complete semantic document run requires the repository-local `.venv` installed by `INSTALAR-STUDY.bat` or the equivalent setup flow. Check readiness with `python scripts/venv_exec.py scripts/setup_env.py check`. Missing `.venv`, Playwright or Chromium is an environment failure, not permission to skip a required gate.

## Context discipline

Do not reread full raw transcripts merely to imitate teacher wording or add volume. Pull raw evidence only when needed to resolve a missing or ambiguous canonical point. Quotes and timestamps remain internal unless exact wording materially matters.
