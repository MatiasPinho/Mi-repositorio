# Pipeline: estudiar

**Mode:** `TODAY`

## READ
Load only these shared rules before semantic work:
- `rules/academic/assessments.md`
- `rules/academic/uncertainty.md`
- `rules/pedagogy/learning-principles.md`


## RUN
Default to 60 minutes if duration is omitted. Sync the per-unit trackers and load unit-scoped progress plus derived observed-topic coverage. Inspect due/weak concepts and assessment context, then allocate time by unit and begin active recall immediately.

Priority remains concept-level and evidence-based: confirmed/likely assessment scope, weak prerequisites, repeated errors and overdue reviews come first. Use observed topics only as a coverage guard so the session does not repeatedly sample one thematic block while another relevant block remains untested; do not create fixed topic quotas or infer assessment weights from topic count.

Never merge or move progress records between units. Record progress in each concept's owning unit after meaningful evidence. If a declared unit has sources but no canonical concepts/topics yet, report it as **NEEDS_INGESTION** and exclude it from adaptive questioning until `procesar` completes; do not ingest sources inside the study session.
