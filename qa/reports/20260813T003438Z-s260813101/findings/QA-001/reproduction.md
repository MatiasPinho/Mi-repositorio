# QA-001 — excluded_assessment_concept_leaks_into_due_results

- Severidad: **high**
- Invariante: `assessment-unit-scope`
- Run: `20260813T003438Z-s260813101`
- Seed: `260813101`

## Esperado
With an assessment filter, due results must be limited to confirmed or likely assessment scope; concepts explicitly excluded from that assessment must remain omitted regardless of review date.

## Actual
For both assessment id parcial-1 and name Parcial 1 at 2030-01-01, study_tracker due returns Funcion from unidad-3 with assessment_relevance=excluded, although academic_context scope contains only unidad-1 and unidad-2.

## Evidencia reciente
- paso 434: `exec` semantic_claims.py
- paso 435: `rpc-exec` semantic_claims.py
- paso 436: `exec` artifact_state.py
- paso 437: `rpc-exec` artifact_state.py
- paso 438: `exec` figure_assets.py
- paso 439: `rpc-exec` figure_assets.py
- paso 440: `check`
- paso 441: `check`
- paso 442: `exec` academic_context.py
- paso 443: `rpc-exec` academic_context.py
- paso 444: `exec` study_tracker.py
- paso 445: `rpc-exec` study_tracker.py
- paso 446: `exec` study_tracker.py
- paso 447: `rpc-exec` study_tracker.py

## Notas
Confirmed after the 100 valid experiments with two reduced invocations using the stable id and spaced name alias. The leak appears when the excluded concept is generally due, indicating the assessment filter does not remove already-due out-of-scope rows.
