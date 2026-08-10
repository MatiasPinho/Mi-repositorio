# Documentation Index

Este directorio contiene la documentación técnica del University Study System. El `README.md` de la raíz explica el producto y el flujo normal de uso; este índice apunta a los contratos y protocolos que mantienen el sistema verificable.

## Arquitectura y operación

- [`../README.md`](../README.md): visión general, inicio rápido, arquitectura vigente, acciones y flujo de estudio.
- [`mcp.md`](mcp.md): adapter MCP local por stdio, herramientas expuestas y límites de seguridad.

## Ingesta y calidad de fuentes

- [`stressed-materials.md`](stressed-materials.md): benchmark adversarial de archivos, hashes, Unicode, renombres, duplicados y transcripciones problemáticas.
- [`pdf-stress.md`](pdf-stress.md): diagnóstico determinista de PDFs normales, escaneados, rotados, vacíos, cifrados o corruptos.
- [`claim-extraction.md`](claim-extraction.md): extracción automática de candidatos de alto valor con página/timestamp y la frontera entre evidencia candidata y claim canónico.
- [`semantic-contradictions.md`](semantic-contradictions.md): resolución de contradicciones con dos vistas separadas, `academic_truth` y `assessment_expectation`.

## Evaluación y publicación de artefactos

- [`academic-eval.md`](academic-eval.md): policy versionada del quality gate académico, benchmark congelado y reglas para evolucionar el contrato.

## Flujo canónico de evidencia

```text
fuentes
  ↓
scan + hashes + PDF health
  ↓
claim_candidates
  ↓
revisión semántica
  ↓
claims canónicos + evidence_ref
  ↓
semantic resolver
  ├─ academic_truth
  └─ assessment_expectation
  ↓
conocimiento canónico
  ↓
artefactos de estudio
  ↓
academic evaluation gate + integrity gate
```

`claim_candidates` nunca son verdad por sí mismos. Sólo una revisión semántica puede aceptarlos y convertirlos en `claims`. Una transcripción cruda conserva valor como evidencia, pero no adquiere automáticamente autoridad de `teacher_explicit` ni puede declarar `supersedes`.

## Benchmarks de CI

GitHub Actions ejecuta en Windows y Ubuntu, antes de la release suite:

```bash
python scripts/stressed_materials.py benchmark
python scripts/pdf_stress.py benchmark
python scripts/semantic_claims.py benchmark
python scripts/claim_candidates.py benchmark
```

El Academic Evaluation Protocol también forma parte de la release suite mediante `tests/test_academic_eval.py` y puede ejecutarse directamente:

```bash
python scripts/academic_eval.py benchmark
```

La suite completa se ejecuta con:

```bash
python tests/run_release_tests.py
```

## Regla para nuevas regresiones

Cuando una materia real descubre un fallo:

1. reducir el problema al fixture sintético más pequeño posible;
2. no copiar material privado al repositorio;
3. agregar el caso al benchmark correspondiente;
4. comprobar que el caso reproduce el fallo;
5. corregir el motor o documentar explícitamente la limitación;
6. exigir CI verde en Windows y Ubuntu.

## Qué documento modificar

| Cambio | Documento principal |
|---|---|
| Política del reviewer / quality gate | `academic-eval.md` |
| Fallo de archivo/transcripción | `stressed-materials.md` |
| Fallo estructural de PDF | `pdf-stress.md` |
| Nueva regla de extracción de claims | `claim-extraction.md` |
| Autoridad, conflictos o supersession | `semantic-contradictions.md` |
| MCP / herramientas disponibles | `mcp.md` |
| Flujo global o experiencia de uso | `../README.md` |

Una modificación de comportamiento no se considera completamente cerrada si cambia un contrato descrito aquí y la documentación correspondiente no se actualiza.