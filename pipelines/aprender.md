# Pipeline: aprender

**Mode:** `LEARN`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/concept-ordering.md`
- `rules/pedagogy/examples.md`
- `rules/writing/student-prose.md`
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/evaluation/academic-fidelity.md`


## RUN
Resolve the topic to its owning stable `unit_id`, then load that unit plus only
explicit prerequisite records from earlier units. Teach progressively: mental
model → simple explanation → relevant diagram/figure when it materially helps
→ example → precise course formulation → active recall/application. Record
progress in the owning unit. Use Humanizer for substantial explanatory prose,
then perform a fidelity check. Do not pre-generate a large static guide unless
requested.
