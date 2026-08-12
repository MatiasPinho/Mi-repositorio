# QA-001 — unchanged_material_commit_rewrites_index

- Severidad: **low**
- Invariante: `material-index-idempotent`
- Run: `20260812T161405Z-s26081225`
- Seed: `26081225`

## Esperado
unchanged_commit_preserves_index_bytes

## Actual
updated_at_changes_and_workspace_digest_drifts

## Evidencia reciente
- paso 5: `hypothesis`
- paso 6: `check`
- paso 7: `hypothesis`
- paso 8: `check`
- paso 9: `exec` study.py
- paso 10: `exec` study.py
- paso 11: `check`
- paso 12: `hypothesis`
- paso 13: `exec` sync_materials.py
- paso 14: `check`
- paso 15: `hypothesis`
- paso 16: `exec` sync_materials.py
- paso 17: `check`
- paso 18: `exec` sync_materials.py

## Notas
reproduced_twice_with_zero_added_changed_removed
