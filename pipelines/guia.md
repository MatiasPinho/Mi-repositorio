# Pipeline: guia

**Mode:** `GUIDE`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/concept-ordering.md`
- `rules/pedagogy/examples.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/visual/active-reading.md`
- `rules/writing/guide.md`
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/pedagogy-rubric.md`
- `rules/evaluation/visual-rubric.md`
- `rules/evaluation/quality-gates.md`
- `contracts/handoffs.md`


## Portable staged RUN
1. Resolve course + scope to exactly one stable `unit_id`; guide scope is unit-only. If Study MCP is connected, call `study_get_unit_context(course, scope)` once and `study_list_artifacts(course)`; otherwise read only `unidades/<unit-id>/` plus explicit cross-unit prerequisites and use `artifact_state.py status`. Refuse an unresolved/global pedagogical scope. If the resolved unit has no canonical concepts, stop with **NEEDS_INGESTION** before starting a guide run. `procesar` may be orchestrated only as a separate prerequisite action, after which `guia` restarts from step 1; never ingest/edit canonical knowledge inside an active guide run. Run `python scripts/venv_exec.py study.py figures migrate <course>` once to normalize legacy figure metadata.
2. Start a run: `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline guia --scope "<scope>"`. The run records deterministic fingerprints of the study engine and canonical academic/concept/topic/figure inputs. Do not modify engine files while the run is active; temporary helpers belong only under `<run-dir>/scratch/`.
3. **PLAN** → write `02-plan.json`. Use canonical knowledge, not raw transcript prose, to decide central idea, ordering, required examples, traps and omissions. Use observed topics as a flexible coverage map so complete concept blocks are not overlooked; declared syllabus topics remain a separate academic reference. Topic boundaries may guide or combine sections but never impose a fixed count/order/length. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; select only figures that add instructional value. Do not write polished prose here.
4. **DRAFT** → write `03-draft.md` from the plan and canonical knowledge. The guide must stand alone for a student who has not read the sources and may develop concepts more fully than a summary. Use semantic callouts and local figure assets according to the visual rules; place a figure beside the explanation it supports.
5. **HUMANIZE** → read `vendor/humanizer/SKILL.md` and edit only the student-facing prose into `04-humanized.md`. Never alter academic meaning or certainty, and preserve semantic callout/image markup.
6. **REVIEW** → evaluate `04-humanized.md` against canonical state, observed-topic coverage, figure registry/assets and all rubrics, including visual support. First audit high-risk claims against canonical knowledge; then run a separate candidate-vs-candidate consistency pass for repeated definitions, taxonomies/counts, conditions and certainty. Write `05-review.json` using the full fidelity-check contract in `contracts/handoffs.md`. Act as an independent critic; do not justify the writer or inherit its plan assumptions.
7. If `05-review.json` passes, copy `04-humanized.md` to `06-final.md`. If it fails, write one targeted repair to `06-repair.md`, review it independently into `07-review.json`, and only if that passes copy it to `08-final.md`. Do not run a third academic review cycle.
8. Register newly derived figures through `study_register_derived_figure` when MCP is connected or `python scripts/venv_exec.py study.py figures register-derived` otherwise. Never edit `figures.json` directly.
9. **RENDER CANDIDATE** → `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered.html --kind guide --course "<course-display-name>" --scope "<scope>" --check`.
10. **INTEGRITY GATE** → run `study_validate_artifact` when Study MCP is connected or `python scripts/venv_exec.py scripts/artifact_integrity.py --type guide` otherwise; persist `<run-dir>/10-integrity.json`. Do not publish unless `ok: true`.
11. **BROWSER VISUAL GATE** → run `python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`. Require exit code 0 and `visual-audit/audit.json -> ok: true`; all lazy images must be force-loaded and verified. Inspect at least `desktop.png` and `mobile.png` against `rules/evaluation/visual-rubric.md`. Missing `.venv`, Playwright/Chromium or inability to inspect screenshots means visual review is incomplete; do not claim PASS and do not publish.
12. **ATOMIC PUBLISH** → resolve `<publish-dir>` as `unidades/<unit-id>/resumenes`, then run `python scripts/venv_exec.py scripts/publish_artifact.py --markdown <accepted-md> --html <run-dir>/09-rendered.html --dest-markdown <publish-dir>/_source/<scope>-guia.md --dest-html <publish-dir>/<scope>-guia.html --report <run-dir>/11-publication.json`. The publisher must leave the validated run sources immutable. It may deterministically rebase local image references only in the published destinations and must record immutable `source_sha256` plus transformed `published_sha256`/`destination_sha256`. Do not require source/destination equality when relocation changes URLs.
13. Mark the published artifact with MCP or `python scripts/venv_exec.py scripts/artifact_state.py`.
14. `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. Finish rejects missing/corrupt publication evidence, engine mutations and changes to the canonical academic/concept/topic/figure fingerprints captured at step 2.

## Engine failure contract
If a required engine capability fails, stop and report **ENGINE FAILURE**. Do not repair `scripts/`, `pipelines/`, `rules/`, `config/`, `contracts/`, `core/`, `design/`, `study_mcp/`, `tests/` or protected setup files during the study run; fix the engine separately and rerun the action.

## Environment contract
A normal staged guide run requires the repository-local `.venv` installed by `INSTALAR-STUDY.bat` (or the equivalent steps in `docs/setup.md`). Check readiness with `python scripts/venv_exec.py scripts/setup_env.py check`.

## Context discipline
The writer should not reread full transcripts merely to imitate the teacher. Pull raw evidence only to resolve a missing/ambiguous canonical point. Quotes/timestamps stay internal unless exact wording matters.
