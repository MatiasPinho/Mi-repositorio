# QA-001 — unicode_equivalent_concept_names_create_duplicate_stable_id

- Severidad: **high**
- Invariante: `concept-unicode-canonical-identity`
- Run: `20260813T052216Z-s260813407`
- Seed: `260813407`

## Esperado
Canonically equivalent NFC and NFD concept names resolve to one unit-local concept record and topic validation remains operable.

## Actual
Upserting Árbol β and Árbol β creates two keys whose id is arbol; topic_catalog validate then returns Id de concepto duplicado en la unidad: arbol.

## Evidencia reciente
- paso 408: `exec` academic_context.py
- paso 409: `rpc-exec` academic_context.py
- paso 410: `experiment-result`
- paso 411: `hypothesis`
- paso 412: `exec` academic_context.py
- paso 413: `rpc-exec` academic_context.py
- paso 414: `experiment-result`
- paso 415: `exec` concept_graph.py
- paso 416: `rpc-exec` concept_graph.py
- paso 417: `exec` topic_catalog.py
- paso 418: `rpc-exec` topic_catalog.py
- paso 419: `exec` study_tracker.py
- paso 420: `rpc-exec` study_tracker.py
- paso 421: `check`

## Notas
Reproduced twice in frozen run using concept_graph.py upsert followed by topic_catalog.py validate. The duplicate blocks reconciliation and leaves explicit topic coverage unresolved.
