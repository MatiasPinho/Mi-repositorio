# Pipeline: preguntas

**Mode:** `RECALL`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/pedagogy/learning-principles.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve the requested scope to one stable `unit_id`, then select concepts only
from that unit (cross-unit prerequisites may be read, not silently quizzed).
Ask one question at a time unless a batch was explicitly requested. Do not
reveal the answer before the attempt. Grade against canonical unit knowledge,
explain the error, and record mastery only when evidence is meaningful.
Persistent banks are generated only on explicit demand, stored under
`unidades/<unit-id>/preguntas/` and artifact-tracked.
