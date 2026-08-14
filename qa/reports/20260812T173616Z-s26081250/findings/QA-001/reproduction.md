# QA-001 — non_cp1252_path_breaks_safe_wrapper_json

- Severidad: **medium**
- Invariante: `harness-unicode-output`
- Run: `20260812T173616Z-s26081250`
- Seed: `26081250`

## Esperado
wrapper_emits_valid_json_for_all_unicode_fixture_paths

## Actual
operations_complete_and_journal_but_cli_returns_UnicodeEncodeError

## Evidencia reciente
- paso 38: `mutation` move
- paso 39: `check`
- paso 40: `hypothesis`
- paso 41: `mutation` copy
- paso 42: `mutation` write
- paso 43: `exec` pdf_probe.py
- paso 44: `mutation` delete
- paso 45: `mutation` move
- paso 46: `check`
- paso 47: `hypothesis`
- paso 48: `mutation` move
- paso 49: `exec` sync_materials.py
- paso 50: `mutation` move
- paso 51: `check`

## Notas
reproduced_with_beta_and_han_character_on_mutate_exec_and_restore
