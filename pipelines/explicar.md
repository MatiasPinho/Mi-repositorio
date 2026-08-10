# Pipeline: explicar

**Mode:** `EXPLAIN`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/examples.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/writing/explain.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve one concept and its prerequisites. Explain it from the course's canonical knowledge, using a minimal example, contrasts and a relevant figure/diagram when that representation genuinely improves comprehension. If outside knowledge would materially improve comprehension, label it as external. Apply Humanizer to substantial prose and then verify fidelity.
