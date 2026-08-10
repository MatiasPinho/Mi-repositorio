# Material processing

`procesar` is an ingestion pipeline, not a note-generation pipeline.

For new or changed materials:
1. deterministic scan/hash first;
2. classify source type;
3. for changed PDFs, build/update the deterministic visual-page catalog when the optional PDF visual capability is available;
3. read semantically only what changed plus enough existing context to integrate it;
4. update academic state, concepts, relations and evidence;
5. detect contradictions and unresolved questions;
6. sync tracker;
7. audit canonical state;
8. commit material hashes only after successful processing;
9. report derived artifacts that became STALE.

Do not generate summaries, guides, reviews, question banks or mock exams during ingestion.
