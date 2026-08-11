---
name: auditar
description: Audita conocimiento o artefactos de una unidad contra las fuentes.
argument-hint: "[materia] [unidad]"
disable-model-invocation: true
---
# Acción portable: auditar

**Modo fijo:** `AUDIT`

Este archivo es un adaptador fino. No contiene metodología propia.

1. Leé `../../../core/ROUTER.md`.
2. Leé `../../../actions/ARGUMENTS.md`.
3. Ejecutá exactamente `../../../pipelines/auditar.md`.
4. Usá `rules/`, `contracts/` y `vendor/` sólo cuando el pipeline los indique.
5. No reemplaces el pipeline con comportamiento específico del proveedor. Las optimizaciones de `providers/` son opcionales y deben conservar los mismos handoffs.
