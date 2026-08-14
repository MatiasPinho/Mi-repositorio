# QA-001 — unchanged_figure_scan_rewrites_registry

- Severidad: **low**
- Invariante: `figure-scan-idempotent`
- Run: `20260813T042126Z-s260813205`
- Seed: `260813205`

## Esperado
Repeating figure_assets scan --write for unchanged PDF sources should preserve the figure-pages registry bytes and avoid reporting a workspace change.

## Actual
Two consecutive reduced scans both rewrote unidades/unidad-1/.study/figure-pages.json; only the generated_at value changed while the source PDF and scan results were unchanged.

## Evidencia reciente
- paso 413: `experiment-result`
- paso 414: `hypothesis`
- paso 415: `exec` quiz_run.py
- paso 416: `rpc-exec` quiz_run.py
- paso 417: `experiment-result`
- paso 418: `check`
- paso 419: `exec` topic_catalog.py
- paso 420: `rpc-exec` topic_catalog.py
- paso 421: `check`
- paso 422: `checkpoint` restored-final-state
- paso 423: `exec` figure_assets.py
- paso 424: `rpc-exec` figure_assets.py
- paso 425: `exec` figure_assets.py
- paso 426: `rpc-exec` figure_assets.py

## Notas
Confirmed after the 100 valid experiments with two consecutive unit-scoped scans. Both reached the frozen engine, returned code 0, and changed the same registry file.
