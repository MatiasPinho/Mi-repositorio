# Pipeline: simulacro

**Mode:** `EXAM`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/academic/assessments.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve the exact assessment record and one target `unit_id` before authoring.
Use only the intersection of the assessment scope and that unit; unknown scope
is never silently included. Match documented format/difficulty where evidence
exists. Hide solutions until submission, grade with a rubric, and update
mastery only for actually tested concepts. Persisted mock exams live under
`unidades/<unit-id>/simulacros/` and must be artifact-tracked.
