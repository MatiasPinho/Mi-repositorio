# Pipeline: simulacro

**Mode:** `EXAM`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/academic/assessments.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve exactly one registered assessment record and exactly one target stable `unit_id` before authoring. Both are required inputs. Use only the intersection of confirmed/likely assessment scope and that unit; unknown scope is never silently included.

Require canonical concepts for the target unit. If they are empty, stop with **NEEDS_INGESTION**; any `procesar` execution must be a separate prerequisite action and the simulacro must restart from scope resolution afterwards.

Match documented format and difficulty where evidence exists. Hide solutions until submission, grade with a rubric, and update mastery only for actually tested concepts. Persisted mock exams live under `unidades/<unit-id>/simulacros/` and must be artifact-tracked.

Within the resolved assessment/unit intersection, use observed topics as a coverage audit so complete concept blocks are not silently omitted. Keep unassigned concepts visible and do not infer exam weights or a fixed question count from the number of topics.
