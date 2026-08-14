# QA-002 — fixture_scope_type_ignored_by_tracker

- Severidad: **high**
- Invariante: `assessment-unit-scope`
- Run: `20260812T173616Z-s26081250`
- Seed: `26081250`

## Esperado
parcial1_scope_marks_unit1_confirmed_unit2_likely_and_excludes_unit3

## Actual
scope_rows_have_type_but_tracker_requires_kind_so_all_relevance_unknown

## Evidencia reciente
- paso 157: `mutation` write
- paso 158: `exec` semantic_claims.py
- paso 159: `exec` semantic_claims.py
- paso 160: `check`
- paso 161: `hypothesis`
- paso 162: `exec` study_tracker.py
- paso 163: `exec` study_tracker.py
- paso 164: `check`
- paso 165: `exec` study_tracker.py
- paso 166: `exec` study_tracker.py
- paso 167: `exec` study_tracker.py
- paso 168: `exec` study_tracker.py
- paso 169: `exec` academic_context.py
- paso 170: `check`

## Notas
reproduced_after_future_dating_one_concept_per_unit_and_academic_scope_output_shows_null_kind
