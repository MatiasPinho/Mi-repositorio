# Pipeline: auditar

**Mode:** `AUDIT`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve the request to exactly one stable `unit_id`. Compare that unit's canonical concepts, observed topics, figures and derived artifacts with sources from the same unit plus explicit course-wide evidence.

Search specifically for omissions, unsupported claims, lost conditions/exceptions, source conflicts, incorrect evidence references, records stored in the wrong unit and certainty drift. Audit `conocimiento/topics.json` as canonical structure too: topic ids must remain stable, `concept_ids` must exist and have one primary topic, `declared_matches` must refer only to that unit's official syllabus topics, explicitly unassigned concepts must remain visible, and observed topics must not silently overwrite the declared syllabus. Run the deterministic topic validator when available.

An empty or incomplete canonical registry is an audit finding, not permission to ingest sources during the audit. Report **NEEDS_INGESTION** where appropriate. Report unresolved uncertainty instead of forcing a resolution.
