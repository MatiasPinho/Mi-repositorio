# Pipeline: repaso

**Mode:** `REVIEW`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/pedagogy/learning-principles.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/visual/active-reading.md`
- `rules/writing/review.md`
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/quality-gates.md`
- `contracts/handoffs.md`


## Portable staged RUN
1. Resolve course + scope and check `artifact_state.py status` for an existing artifact.
2. Start a run: `python scripts/pipeline_run.py start --course <course-folder> --pipeline repaso --scope "<scope>"`.
3. **PLAN** → write `02-plan.json`. Use canonical knowledge, not raw transcript prose, to decide central idea, ordering, required examples, traps and omissions. For every major concept decide `visual_required`, `visual_helpful` or `visual_not_needed`; select only figures that add instructional value. Do not write polished prose here.
4. **DRAFT** → write `03-draft.md` from the plan and canonical knowledge. The draft must stand alone for a student who has not read the sources. Use semantic callouts and local figure assets according to the visual rules; place a figure beside the explanation it supports.
5. **HUMANIZE** → read `vendor/humanizer/SKILL.md` and edit only the student-facing prose into `04-humanized.md`. Never alter academic meaning or certainty, and preserve semantic callout/image markup.
6. **REVIEW** → evaluate `04-humanized.md` against canonical state, figure registry/assets and all rubrics, including visual support. Write `05-review.json` using `contracts/handoffs.md`. Act as an independent critic; do not justify the writer.
7. If `05-review.json` passes, copy `04-humanized.md` to `06-final.md`. If it fails, write one targeted repair to `06-repair.md`, review it independently into `07-review.json`, and only if that passes copy it to `08-final.md`. Do not run a third review cycle.
8. Copy the accepted Markdown (`06-final.md` or `08-final.md`) to `resumenes/_source/<scope>-repaso.md`.
9. **RENDER** → `python scripts/render_study.py <accepted-md> <run-dir>/09-rendered.html --kind rapid-review --course "<course-display-name>" --scope "<scope>" --check`. Rendering is deterministic: textbook front matter, typography, semantic rails, figure placement, TOC and visible recall blocks come from the shared theme. Fix broken local figure paths before publishing.
10. Publish `09-rendered.html` to `resumenes/<scope>-repaso.html` and mark the HTML with `artifact_state.py mark --type rapid-review --scope "<scope>"`. The HTML is the normal reading artifact; Markdown remains the portable source.
11. `python scripts/pipeline_run.py finish --run <run-dir>`.

## Context discipline
The writer should not reread full transcripts merely to imitate the teacher. Pull raw evidence only to resolve a missing/ambiguous canonical point. Quotes/timestamps stay internal unless exact wording matters.


## Publication integrity
Run `python study.py figures migrate <course>` before planning to normalize legacy derived figure metadata without reprocessing sources.

Before publishing any `rapid-review` artifact, register newly derived figures with `study.py figures register-derived`, render with `render_study.py --check`, then run `scripts/artifact_integrity.py --type rapid-review` and write `<run-dir>/10-integrity.json`. Publish only when it returns `ok: true`. Temporary helper scripts are allowed only under `<run-dir>/scratch/`, never in the course tree. Use stable `unit_id` from `01-input.json` for unit scope.
