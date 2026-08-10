---
name: procesar
description: Ingiere material nuevo o modificado sin generar apuntes pedagógicos.
---
# Acción portable: procesar

**Modo fijo:** `INGEST`

Este archivo es un adaptador fino. No contiene metodología propia.

1. Leé `../../../core/ROUTER.md`.
2. Leé `../../../actions/ARGUMENTS.md`.
3. Ejecutá exactamente `../../../pipelines/procesar.md`.
4. Usá `rules/`, `contracts/` y `vendor/` sólo cuando el pipeline los indique.
5. No reemplaces el pipeline con comportamiento específico del proveedor. Las optimizaciones de `providers/` son opcionales y deben conservar los mismos handoffs.
