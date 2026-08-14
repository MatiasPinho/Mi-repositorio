# QA-003 — equivalent_unit_aliases_rewrite_concept_registry

- Severidad: **low**
- Invariante: `concept-unit-alias-idempotence`
- Run: `20260813T052216Z-s260813407`
- Seed: `260813407`

## Esperado
Stable unit id and display-name aliases resolve to one canonical stored representation, so alternating equivalent aliases does not rewrite concept state.

## Actual
concept_graph.py stores the raw --unit token in concept.unit while separately resolving unit_id; alternating Algoritmos y datos and unidad-1 rewrites concepts.json in both directions with the same unit_id.

## Evidencia reciente
- paso 414: `experiment-result`
- paso 415: `exec` concept_graph.py
- paso 416: `rpc-exec` concept_graph.py
- paso 417: `exec` topic_catalog.py
- paso 418: `rpc-exec` topic_catalog.py
- paso 419: `exec` study_tracker.py
- paso 420: `rpc-exec` study_tracker.py
- paso 421: `check`
- paso 422: `finding`
- paso 423: `finding`
- paso 424: `exec` concept_graph.py
- paso 425: `rpc-exec` concept_graph.py
- paso 426: `exec` concept_graph.py
- paso 427: `rpc-exec` concept_graph.py

## Notas
Confirmed with two consecutive upserts in the frozen run; each changed the workspace digest while unit_id remained unidad-1. This can create unnecessary state churn and downstream stale fingerprints.
