# QA-002 — tracker_progress_name_keys_fail_stable_id_checker

- Severidad: **medium**
- Invariante: `progress-concept-stable-identity`
- Run: `20260813T052216Z-s260813407`
- Seed: `260813407`

## Esperado
Tracker progress produced from a canonical concept is resolvable by the final invariant checker, either through a persisted stable concept id or name-aware resolution.

## Actual
study_tracker sync/record stores entries under normalized concept names without id; engine check compares those keys only to concept ids and reports Bucle λ, Parámetro ñ, and Árbol β as unknown progress.

## Evidencia reciente
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
- paso 422: `finding`

## Notas
Reproduced after a successful tracker sync and check. This is independent of the Unicode duplicate: unit 2 and unit 3 each contain one unique concept but their valid name-keyed progress is still rejected.
