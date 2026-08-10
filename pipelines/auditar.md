# Pipeline: auditar

**Mode:** `AUDIT`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve unit-scoped content to its stable `unit_id` and compare it with sources
from that unit plus explicit course-wide evidence. Search specifically for
omissions, unsupported claims, lost conditions/exceptions, source conflicts,
incorrect evidence references, records stored in the wrong unit and certainty
drift. Report unresolved uncertainty instead of forcing a resolution.
