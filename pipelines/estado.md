# Pipeline: estado

**Mode:** `STATUS`

## READ
Load only these shared rules before semantic work:
- `rules/academic/assessments.md`
- `rules/academic/uncertainty.md`


## RUN
If Study MCP is connected, prefer `study_get_course_context`,
`study_list_units`, unit-scoped `study_get_progress`/`study_get_unit_context`
and `study_list_artifacts`; otherwise
use deterministic CLI first: status, due, assessments and artifacts. Report
mastery, untested concepts, weaknesses, due reviews and CURRENT/STALE artifacts
grouped by stable unit. Upcoming assessments remain course-wide. Do not invent
a probability of passing.

For each unit, derive observed-topic coverage from the progress of its
`concept_ids` (tested/total and mastery tracking coverage). Report aggregate
topic mastery only when every assigned concept has a progress record; otherwise
label the known-concept average as partial and show its denominator. Report
explicitly unassigned concepts as their own gap. Never write those derived
mastery values back into `topics.json`.
