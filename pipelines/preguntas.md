# Pipeline: preguntas

**Mode:** `RECALL`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/pedagogy/learning-principles.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve the requested scope to exactly one stable `unit_id`; this action does not accept a topic as a substitute for unit scope. Require canonical concepts for that unit. If the concept registry is empty, stop with **NEEDS_INGESTION**; `procesar` may be orchestrated only as a separate prerequisite action, after which `preguntas` restarts from resolution.

Select concepts only from the resolved unit. Cross-unit prerequisites may be read to grade or explain, but never silently quizzed as if they belonged to the target unit. Ask one question at a time unless a batch was explicitly requested. Do not reveal the answer before the attempt. Grade against canonical unit knowledge, explain the error, and record mastery only when evidence is meaningful.

Use observed topics as coverage blocks when selecting concepts, so a session or requested bank does not repeatedly sample one block while leaving another untested. Include explicitly unassigned concepts in the coverage audit rather than hiding them; topic count never dictates a fixed number of questions.

Persistent banks are generated only on explicit demand, stored under `unidades/<unit-id>/preguntas/` and artifact-tracked.
