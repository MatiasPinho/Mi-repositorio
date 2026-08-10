# Pipeline: estado

**Mode:** `STATUS`

## READ
Load only these shared rules before semantic work:
- `rules/academic/assessments.md`
- `rules/academic/uncertainty.md`


## RUN
If Study MCP is connected, prefer `study_get_course_context`, `study_get_progress` and `study_list_artifacts`; otherwise use deterministic CLI first: status, due, assessments and artifacts. Summarize mastery, untested concepts, recurring weaknesses, due reviews, upcoming assessments and CURRENT/STALE artifacts. Do not invent a probability of passing.
