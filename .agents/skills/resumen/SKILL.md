---
name: resumen
description: Genera o actualiza un resumen estudiable; puede pedirse en modo detallado.
---
# Acción portable: resumen

**Modo fijo:** `SUMMARY`

Este archivo es un adaptador fino. No contiene metodología propia.

1. Leé `../../../core/ROUTER.md`.
2. Leé `../../../actions/ARGUMENTS.md`.
3. Ejecutá exactamente `../../../pipelines/resumen.md`.
4. Usá `rules/`, `contracts/` y `vendor/` sólo cuando el pipeline los indique.
5. No reemplaces el pipeline con comportamiento específico del proveedor. Las optimizaciones de `providers/` son opcionales y deben conservar los mismos handoffs.
