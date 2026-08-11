# Pipeline: resumen

**Mode:** `SUMMARY`

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
- `rules/writing/summary.md`
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/pedagogy-rubric.md`
- `rules/evaluation/visual-rubric.md`
- `rules/evaluation/quality-gates.md`
- `contracts/handoffs.md`


## Portable staged RUN
1. Resolve course + scope to a stable `unit_id`. If Study MCP is connected, call `study_get_unit_context(course, scope)` once and `study_list_artifacts(course)` instead of manually reopening/filtering canonical JSON. Otherwise use only the files below `unidades/<unit-id>/` plus explicit cross-unit prerequisites. Refuse an unresolved/global pedagogical scope. Run `python scripts/venv_exec.py study.py figures migrate <course>` once; it only normalizes legacy derived-figure metadata and does not reread/reprocess sources.
2. Start a run: `python scripts/venv_exec.py scripts/pipeline_run.py start --course <course-folder> --pipeline resumen --scope "<scope>"`. Any temporary helper code belongs only inside `<run-dir>/scratch/`; never create persistent repair scripts in the course tree. The run records a deterministic fingerprint of the study engine. Do not modify `scripts/`, `pipelines/`, `rules/`, `config/`, `contracts/`, `core/`, `design/`, `study_mcp/`, `tests/` or protected root setup files while the run is active.
3. **PLAN** → write `02-plan.json`. Use canonical knowledge, not raw transcript prose, to decide central idea, ordering, required examples, traps and omissions. Use observed topics as a flexible coverage map so concept blocks are not overlooked, while preserving declared syllabus topics as a separate academic reference. Topic boundaries may guide or combine sections; they never impose a fixed section count, order or length. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; select only figures that add instructional value. Do not write polished prose here.
4. **DRAFT** → write `03-draft.md` from the plan and canonical knowledge. The draft must stand alone for a student who has not read the sources. Use semantic callouts and local figure assets according to the visual rules; place a figure beside the explanation it supports.
5. **HUMANIZE** → read `vendor/humanizer/SKILL.md` and edit only the student-facing prose into `04-humanized.md`. Never alter academic meaning or certainty, and preserve semantic callout/image markup.
6. **REVIEW** → evaluate `04-humanized.md` against canonical state, figure registry/assets and all rubrics, including visual support. First audit high-risk claims against canonical knowledge; then run a separate candidate-vs-candidate consistency pass for repeated definitions, taxonomies/counts, conditions and certainty. Write `05-review.json` using the full fidelity-check contract in `contracts/handoffs.md`. Act as an independent critic; do not justify the writer or inherit its plan assumptions.
7. If `05-review.json` passes, copy `04-humanized.md` to `06-final.md`. If it fails, write one targeted repair to `06-repair.md`, review it independently into `07-review.json`, and only if that passes copy it to `08-final.md`. Do not run a third academic review cycle.
8. Register every newly created pedagogical diagram through `study_register_derived_figure` when Study MCP is connected; otherwise use `python scripts/venv_exec.py study.py figures register-derived <course> --id <id> --unit "<scope>" --asset <asset> --description "..." --based-on <canonical-source-or-concept> ...`. Do not edit `figures.json` directly, do not edit a source figure record into a derived one, and never overwrite an existing id/asset.
9. **RENDER CANDIDATE** → `python scripts/venv_exec.py scripts/render_study.py <accepted-md> <run-dir>/09-rendered.html --kind summary --course "<course-display-name>" --scope "<scope>" --check`. Caption metadata may have blank lines after tables/code; orphan captions are a hard render check failure.
10. **INTEGRITY GATE** → use `study_validate_artifact` when Study MCP is connected, otherwise `python scripts/venv_exec.py scripts/artifact_integrity.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --write <run-dir>/10-integrity.json`. In either path, persist the result as `<run-dir>/10-integrity.json`. Do not publish unless it returns `ok: true`. This gate verifies image paths/alt text, caption association, figure registry uniqueness/provenance, stable unit scope and registered figures used by the artifact.
11. **BROWSER VISUAL GATE** → run `python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`. This is mandatory in the complete study environment. Do not replace it with checking HTML strings or image paths. The auditor must force and verify all lazy images before the full-page capture. Require exit code 0 and `visual-audit/audit.json -> ok: true`; otherwise do not publish. Inspect at least `visual-audit/desktop.png` and `visual-audit/mobile.png` against `rules/evaluation/visual-rubric.md` to catch obvious hierarchy, clipping, figure-legibility or spacing defects that mechanical metrics cannot express. If screenshots cannot be inspected, report visual review as incomplete and do not claim it passed.
12. **ATOMIC PUBLISH** → resolve `<publish-dir>` as `unidades/<unit-id>/resumenes`. Only after both gates pass, run `python scripts/venv_exec.py scripts/publish_artifact.py --markdown <accepted-md> --html <run-dir>/09-rendered.html --dest-markdown <publish-dir>/_source/<scope>-resumen.md --dest-html <publish-dir>/<scope>-resumen.html --report <run-dir>/11-publication.json`. The publisher deterministically rebases local image references for the Markdown and HTML destination directories, verifies that every rewritten reference resolves to the same physical asset that was validated before publication, and commits source/destination bytes transactionally so the existing SHA-256 equality contract remains true. Require `ok: true` and matching source/destination SHA-256 values. Do not publish with generic copy/edit operations.
13. Mark the published HTML with `study_mark_artifact` when MCP is connected or `python scripts/venv_exec.py scripts/artifact_state.py mark --type summary --scope "<scope>"` otherwise.
14. `python scripts/venv_exec.py scripts/pipeline_run.py finish --run <run-dir>`. Finish mechanically rejects missing/corrupt publication evidence or any engine mutation detected since step 2.

## Engine failure contract
If a required engine capability is broken during the run, stop and report an **ENGINE FAILURE** with the diagnostic. Do not patch the engine inside a study run and then continue publishing. Engine fixes belong in a separate development branch/PR and the study action is rerun afterwards.

## Environment contract
A normal staged summary run requires the repository-local `.venv` installed by `INSTALAR-STUDY.bat` (or the equivalent steps in `docs/setup.md`). Missing `.venv`, Playwright or Chromium is an environment failure, not permission to silently skip the visual gate. Check readiness with `python scripts/venv_exec.py scripts/setup_env.py check`.

## Context discipline
The writer should not reread full transcripts merely to imitate the teacher. Pull raw evidence only to resolve a missing/ambiguous canonical point. Quotes/timestamps stay internal unless exact wording matters.
