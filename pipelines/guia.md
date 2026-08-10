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
1. Resolve course + scope. If Study MCP is connected, call `study_get_unit_context(course, scope)` once and `study_list_artifacts(course)`; otherwise read canonical state and use `artifact_state.py status`. Run `python study.py figures migrate <course>` once to normalize legacy figure metadata.
2. Start a run: `python scripts/pipeline_run.py start --course <course-folder> --pipeline guia --scope "<scope>"`.
3. **PLAN** → write `02-plan.json`. Use canonical knowledge, not raw transcript prose, to decide central idea, ordering, required examples, traps and omissions. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; select only figures that add instructional value. Do not write polished prose here.
4. **DRAFT** → write `03-draft.md` from the plan and canonical knowledge. The draft must stand alone for a student who has not read the sources. Use semantic callouts and local figure assets according to the visual rules; place a figure beside the explanation it supports.
5. **HUMANIZE** → read `vendor/humanizer/SKILL.md` and edit only the student-facing prose into `04-humanized.md`. Never alter academic meaning or certainty, and preserve semantic callout/image markup.
6. **REVIEW** → evaluate `04-humanized.md` against canonical state, figure registry/assets and all rubrics, including visual support. First audit high-risk claims against canonical knowledge; then run a separate candidate-vs-candidate consistency pass for repeated definitions, taxonomies/counts, conditions and certainty. Write `05-review.json` using the full fidelity-check contract in `contracts/handoffs.md`. Act as an independent critic; do not justify the writer or inherit its plan assumptions.
7. If `05-review.json` passes, copy `04-humanized.md` to `06-final.md`. If it fails, write one targeted repair to `06-repair.md`, review it independently into `07-review.json`, and only if that passes copy it to `08-final.md`. Do not run a third academic review cycle.
8. Register newly derived figures through `study_register_derived_figure` when MCP is connected or `study.py figures register-derived` otherwise. Never edit `figures.json` directly.
9. **RENDER CANDIDATE** → `python scripts/render_study.py <accepted-md> <run-dir>/09-rendered.html --kind guide --course "<course-display-name>" --scope "<scope>" --check`.
10. **INTEGRITY GATE** → run `study_validate_artifact` when MCP is connected or `scripts/artifact_integrity.py --type guide` otherwise; persist `<run-dir>/10-integrity.json`. Do not publish unless `ok: true`.
11. **BROWSER VISUAL GATE** → run `python scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`. Require exit code 0 and `visual-audit/audit.json -> ok: true`. Inspect at least `desktop.png` and `mobile.png` against `rules/evaluation/visual-rubric.md`. Missing Playwright/Chromium or inability to inspect screenshots means visual review is incomplete; do not claim PASS and do not publish.
12. After both gates pass, copy accepted Markdown to `resumenes/_source/<scope>-guia.md`, publish `09-rendered.html` to `resumenes/<scope>-guia.html`, and mark the artifact with MCP or `artifact_state.py`.
13. `python scripts/pipeline_run.py finish --run <run-dir>`.

## Environment contract
A normal staged guide run assumes the complete environment installed by `INSTALAR-STUDY.bat` (or `python -m pip install -r requirements.txt` plus `python -m playwright install chromium`). Check readiness with `python scripts/setup_env.py check`.

## Context discipline
The writer should not reread full transcripts merely to imitate the teacher. Pull raw evidence only to resolve a missing/ambiguous canonical point. Quotes/timestamps stay internal unless exact wording matters.
