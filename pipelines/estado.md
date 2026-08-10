# Pipeline: estado

**Mode:** `STATUS`

## READ
Load only these shared rules before semantic work:
- `rules/academic/assessments.md`
- `rules/academic/uncertainty.md`


## RUN
If Study MCP is connected, prefer `study_get_course_context`,
`study_list_units`, `study_get_progress` and `study_list_artifacts`; otherwise
use deterministic CLI first: status, due, assessments and artifacts. Report
mastery, untested concepts, weaknesses, due reviews and CURRENT/STALE artifacts
grouped by stable unit. Upcoming assessments remain course-wide. Do not invent
a probability of passing.
