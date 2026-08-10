# Pipeline: auditar

**Mode:** `AUDIT`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Compare canonical state or a derived artifact with original evidence as needed. Search specifically for omissions, unsupported claims, lost conditions/exceptions, source conflicts, incorrect evidence references and certainty drift. Report unresolved uncertainty instead of forcing a resolution.
