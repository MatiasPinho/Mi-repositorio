# Concept graph

Keep semantic knowledge in
`unidades/<unit-id>/conocimiento/concepts.json` and dynamic mastery in
`unidades/<unit-id>/progreso/progress.json`. Never rebuild a course-wide mixed
registry in a V4 matter; merged reads are an in-memory query view only.

A concept may contain: name, unit, concise meaning, precise definition, prerequisites, relations, examples, traps, recurring errors, source references, assessment relevance by assessment, teaching signals and source fingerprints.

Prefer concepts that are useful for learning and assessment. Do not fragment every sentence into a concept.

After ingestion, sync graph concepts to the tracker. Relations/prerequisites must be evidence-backed or clearly marked as model organization rather than course fact.
