# QA-003 — derived_asset_hash_drift_passes_verify

- Severidad: **medium**
- Invariante: `figure-asset-hash-verify`
- Run: `20260812T173616Z-s26081250`
- Seed: `26081250`

## Esperado
figures_verify_rejects_asset_when_bytes_no_longer_match_registered_asset_sha256

## Actual
figures_verify_returns_ok_true_after_registered_derived_asset_bytes_are_modified

## Evidencia reciente
- paso 258: `check`
- paso 259: `mutation` delete
- paso 260: `mutation` move
- paso 261: `check`
- paso 262: `hypothesis`
- paso 263: `exec` study.py
- paso 264: `exec` topic_catalog.py
- paso 265: `exec` topic_catalog.py
- paso 266: `exec` topic_catalog.py
- paso 267: `exec` study_tracker.py
- paso 268: `exec` claim_candidates.py
- paso 269: `exec` semantic_claims.py
- paso 270: `exec` artifact_state.py
- paso 271: `check`

## Notas
reproduced_in_experiment_48_and_confirmed_by_registry_issues_omitting_asset_sha256_validation
