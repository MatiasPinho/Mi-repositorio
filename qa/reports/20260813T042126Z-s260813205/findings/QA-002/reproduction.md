# QA-002 — excluded_assessment_concept_leaks_into_due_results

- Severidad: **high**
- Invariante: `assessment-unit-scope`
- Run: `20260813T042126Z-s260813205`
- Seed: `260813205`

## Esperado
With an assessment filter, due results must stay within confirmed or likely assessment scope; a concept explicitly excluded from that assessment must remain omitted even when generally due.

## Actual
For both parcial-1 and the display name Parcial 1 at 2030-01-01, study_tracker due returned Funcion from unidad-3 with assessment_relevance=excluded, while academic_context scope omitted unidad-3.

## Evidencia reciente
- paso 420: `rpc-exec` topic_catalog.py
- paso 421: `check`
- paso 422: `checkpoint` restored-final-state
- paso 423: `exec` figure_assets.py
- paso 424: `rpc-exec` figure_assets.py
- paso 425: `exec` figure_assets.py
- paso 426: `rpc-exec` figure_assets.py
- paso 427: `finding`
- paso 428: `exec` academic_context.py
- paso 429: `rpc-exec` academic_context.py
- paso 430: `exec` study_tracker.py
- paso 431: `rpc-exec` study_tracker.py
- paso 432: `exec` study_tracker.py
- paso 433: `rpc-exec` study_tracker.py

## Notas
Confirmed after the 100 valid experiments with reduced id and spaced-name alias invocations. This independently reproduces the assessment-scope leak seen in prior campaigns.
