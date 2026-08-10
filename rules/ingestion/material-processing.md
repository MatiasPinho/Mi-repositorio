# Material processing

`procesar` is an ingestion pipeline, not a note-generation pipeline.

For new or changed materials:
1. deterministic scan/hash first;
2. classify source type;
3. for changed PDFs, build/update the deterministic visual-page catalog when the optional PDF visual capability is available;
4. run the deterministic claim-candidate extractor so high-signal assessment rules, definitions and explicit change cues are registered with exact evidence locators;
5. read semantically only what changed plus enough existing context to integrate it;
6. review pending `claim_candidates`: candidate extraction may suggest structure, but only semantic review may accept/reject a candidate and promote it into canonical `claims`;
7. update academic state, concepts, relations and evidence;
8. resolve structured claims and preserve unresolved/split-view contradictions;
9. sync tracker;
10. audit canonical state;
11. commit material hashes only after successful processing;
12. report derived artifacts that became STALE.

A `semantic_ready` claim candidate means only that the extractor found enough text to propose a structured key/value. It is not evidence that the proposition is true.

Do not generate summaries, guides, reviews, question banks or mock exams during ingestion.
