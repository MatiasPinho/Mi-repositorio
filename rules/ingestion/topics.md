# Observed topics

`academic.json -> units[].topics` is the declared/offical syllabus. It remains
course-wide academic evidence and is never rewritten from processed material.

The reconstructed semantic grouping lives separately at
`unidades/<unit-id>/conocimiento/topics.json`:

- a topic groups concepts that belong together for understanding, not merely
  text that shared a PDF heading;
- each topic has one stable `id`; reuse an existing id whenever the semantic
  group is the same, even if its preferred name evolves;
- `aliases` retain useful prior/alternate names;
- `concept_ids` reference real ids in that unit's `concepts.json` and express
  each concept's single primary topic;
- `unassigned_concept_ids` explicitly records concepts for which no defensible
  primary topic has been established yet;
- `declared_matches` links an observed topic to exact strings from the unit's
  declared syllabus without modifying that syllabus;
- `evidence` records why the observed grouping exists.

Run deterministic reconciliation after concept updates. Semantic review decides
the grouping; the reconciler preserves ids, validates references and makes
unassigned concepts visible. Do not infer a topic from layout alone, and do not
store mastery, difficulty, exam weight or topic-to-topic graphs in V1.
