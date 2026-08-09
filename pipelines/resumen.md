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
1. Resolve course + scope. Run `python study.py figures migrate <course>` once; it only normalizes legacy derived-figure metadata and does not reread/reprocess sources. Then check `artifact_state.py status` for an existing artifact.
2. Start a run: `python scripts/pipeline_run.py start --course <course-folder> --pipeline resumen --scope "<scope>"`. Any temporary helper code belongs only inside `<run-dir>/scratch/`; never create persistent repair scripts in the course tree.
3. **PLAN** → write `02-plan.json`. Use canonical knowledge, not raw transcript prose, to decide central idea, ordering, required examples, traps and omissions. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; select only figures that add instructional value. Do not write polished prose here.
4. **DRAFT** → write `03-draft.md` from the plan and canonical knowledge. The draft must stand alone for a student who has not read the sources. Use semantic callouts and local figure assets according to the visual rules; place a figure beside the explanation it supports.
5. **HUMANIZE** → read `vendor/humanizer/SKILL.md` and edit only the student-facing prose into `04-humanized.md`. Never alter academic meaning or certainty, and preserve semantic callout/image markup.
6. **REVIEW** → evaluate `04-humanized.md` against canonical state, figure registry/assets and all rubrics, including visual support. Write `05-review.json` using `contracts/handoffs.md`. Act as an independent critic; do not justify the writer.
7. If `05-review.json` passes, copy `04-humanized.md` to `06-final.md`. If it fails, write one targeted repair to `06-repair.md`, review it independently into `07-review.json`, and only if that passes copy it to `08-final.md`. Do not run a third review cycle.
8. Register every newly created pedagogical diagram through the deterministic command `python study.py figures register-derived <course> --id <id> --unit "<scope>" --asset <asset> --description "..." --based-on <canonical-source-or-concept> ...`. Do not edit a source figure record into a derived one and never overwrite an existing id/asset.
9. **RENDER CANDIDATE** → `python scripts/render_study.py <accepted-md> <run-dir>/09-rendered.html --kind summary --course "<course-display-name>" --scope "<scope>" --check`. Caption metadata may have blank lines after tables/code; orphan captions are a hard render check failure.
10. **INTEGRITY GATE** → `python scripts/artifact_integrity.py --course <course> --markdown <accepted-md> --html <run-dir>/09-rendered.html --scope "<scope>" --type summary --write <run-dir>/10-integrity.json`. Do not publish unless this returns `ok: true`. This gate verifies image paths/alt text, caption association, figure registry uniqueness/provenance, stable unit scope and registered figures used by the artifact.
11. Only after the integrity gate passes, copy the accepted Markdown to `resumenes/_source/<scope>-resumen.md`, publish `09-rendered.html` to `resumenes/<scope>-resumen.html`, and mark the HTML with `artifact_state.py mark --type summary --scope "<scope>"`.
12. `python scripts/pipeline_run.py finish --run <run-dir>`.

## Context discipline
The writer should not reread full transcripts merely to imitate the teacher. Pull raw evidence only to resolve a missing/ambiguous canonical point. Quotes/timestamps stay internal unless exact wording matters.
