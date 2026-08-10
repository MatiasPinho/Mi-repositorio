# Documentation Index

Este directorio contiene la documentación técnica del University Study System. El `README.md` de la raíz explica el producto y el flujo normal de uso; este índice apunta a los contratos y protocolos que mantienen el sistema verificable.

## Arquitectura y operación

- [`../README.md`](../README.md): visión general, inicio rápido, arquitectura vigente, acciones y flujo de estudio.
- [`setup.md`](setup.md): instalación completa, `INSTALAR-STUDY.bat`, `.venv`, preflight de Chromium y paridad con CI.
- [`runtime-safety.md`](runtime-safety.md): inmutabilidad del motor durante una corrida, carga verificada de lazy images y publicación atómica con SHA-256.
- [`mcp.md`](mcp.md): adapter MCP local por stdio, herramientas expuestas y límites de seguridad.

## Ingesta y calidad de fuentes

- [`stressed-materials.md`](stressed-materials.md): benchmark adversarial de archivos, hashes, Unicode, renombres, duplicados y transcripciones problemáticas.
- [`pdf-stress.md`](pdf-stress.md): diagnóstico determinista de PDFs normales, escaneados, rotados, vacíos, cifrados o corruptos.
- [`claim-extraction.md`](claim-extraction.md): extracción automática de candidatos de alto valor con página/timestamp y la frontera entre evidencia candidata y claim canónico.
- [`semantic-contradictions.md`](semantic-contradictions.md): resolución de contradicciones con dos vistas separadas, `academic_truth` y `assessment_expectation`.

## Evaluación y publicación de artefactos

- [`academic-eval.md`](academic-eval.md): policy versionada del quality gate académico, benchmark congelado y reglas para evolucionar el contrato.
- [`runtime-safety.md`](runtime-safety.md): contrato de browser audit real, `11-publication.json` y bloqueo de modificaciones del motor.
- `rules/evaluation/visual-rubric.md`: contrato de soporte visual y evidencia renderizada obligatoria para resumen/guía/repaso.

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
academic evaluation gate
  ↓
render + integrity gate
  ↓
Chromium visual audit
  ├─ lazy images realmente decodificadas
  └─ screenshot inspection
  ↓
publicación atómica + SHA-256
  ↓
11-publication.json
  ↓
finish: publicación íntegra + motor sin cambios
```

`claim_candidates` nunca son verdad por sí mismos. Sólo una revisión semántica puede aceptarlos y convertirlos en `claims`. Una transcripción cruda conserva valor como evidencia, pero no adquiere automáticamente autoridad de `teacher_explicit` ni puede declarar `supersedes`.

Los artefactos HTML de resumen, guía y repaso tampoco pueden finalizar sólo porque sus rutas sean válidas: `pipeline_run.py` exige auditoría visual real, evidencia de publicación byte-for-byte y que el fingerprint del motor permanezca idéntico desde el comienzo de la corrida.

## Benchmarks de CI

GitHub Actions crea primero la `.venv` aislada, instala el entorno completo y verifica que Chromium pueda arrancar. Después ejecuta en Windows y Ubuntu:

```bash
python scripts/venv_exec.py scripts/stressed_materials.py benchmark
python scripts/venv_exec.py scripts/pdf_stress.py benchmark
python scripts/venv_exec.py scripts/semantic_claims.py benchmark
python scripts/venv_exec.py scripts/claim_candidates.py benchmark
```

El Academic Evaluation Protocol también forma parte de la release suite mediante `tests/test_academic_eval.py` y puede ejecutarse directamente:

```bash
python scripts/venv_exec.py scripts/academic_eval.py benchmark
```

La suite completa se ejecuta con:

```bash
python scripts/venv_exec.py tests/run_release_tests.py
```

Incluye smoke/regression tests que renderizan documentos sintéticos, ejecutan Chromium real, fuerzan imágenes diferidas fuera del viewport, prueban publicación sin truncamiento y verifican el bloqueo de mutaciones del motor.

## Regla para nuevas regresiones

Cuando una materia real descubre un fallo:

1. reducir el problema al fixture sintético más pequeño posible;
2. no copiar material privado al repositorio;
3. agregar el caso al benchmark/test correspondiente;
4. comprobar que el caso reproduce el fallo;
5. corregir el motor o documentar explícitamente la limitación;
6. no corregir el motor dentro de la propia corrida de estudio;
7. exigir CI verde en Windows y Ubuntu.

## Qué documento modificar

| Cambio | Documento principal |
|---|---|
| Instalación / dependencias / Chromium | `setup.md` |
| Motor durante una corrida / publicación / lazy images | `runtime-safety.md` |
| Política del reviewer / quality gate | `academic-eval.md` |
| Fallo de archivo/transcripción | `stressed-materials.md` |
| Fallo estructural de PDF | `pdf-stress.md` |
| Nueva regla de extracción de claims | `claim-extraction.md` |
| Autoridad, conflictos o supersession | `semantic-contradictions.md` |
| MCP / herramientas disponibles | `mcp.md` |
| Flujo global o experiencia de uso | `../README.md` |

Una modificación de comportamiento no se considera completamente cerrada si cambia un contrato descrito aquí y la documentación correspondiente no se actualiza.
