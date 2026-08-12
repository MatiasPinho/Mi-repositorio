---
name: engine-qa
description: Internal autonomous adversarial QA loop for the University Study engine. Creates only synthetic courses, executes a frozen engine copy through a guarded harness, records experiments/findings, and exports reproducible reports. Never edits engine code during the QA run.
argument-hint: "[experimentos opcionales]"
disable-model-invocation: true
---

# Engine QA — QA adversarial autónomo del motor

Esta skill es **interna de desarrollo**. No forma parte de las nueve acciones públicas para estudiantes.

## Objetivo

Probar el motor de forma iterativa sin que el usuario tenga que cargar PDFs, ejecutar acciones manualmente ni copiar conversaciones. El agente crea una materia sintética, formula hipótesis, ejecuta una copia congelada del motor real, muta únicamente ese workspace QA, compara estados, comprueba invariantes, confirma fallos y deja un reporte reproducible.

Leé primero:
- `../../../docs/engine-qa.md`
- `../../../core/ROUTER.md`

## Regla absoluta

Durante un Engine QA run **no edites el checkout real**. Esto incluye `study.py`, `core/`, `rules/`, `pipelines/`, `contracts/`, `vendor/`, `scripts/`, `study_mcp/`, `config/`, `actions/`, `assets/`, `design/`, `skills-src/`, `.claude/skills/`, `.agents/skills/`, `tests/`, `docs/` y `.github/`.

La entrada canónica es siempre `scripts/engine_qa_safe.py`. El wrapper crea una copia congelada del motor bajo `.study/engine-qa/sandboxes/`, hace que la materia sintética viva dentro de ese sandbox y mantiene un fingerprint independiente del checkout real. Nunca invoques `scripts/engine_qa.py` directamente durante una corrida normal de QA.

Un hallazgo se arregla después, en un PR distinto.

## Inicio

Usá siempre el Python del proyecto:

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py history
python scripts/venv_exec.py scripts/engine_qa_safe.py start --budget <N> --seed <seed> --provider <codex|claude>
```

Si el usuario no indicó cantidad, usá **25 experimentos**. Variá el seed entre corridas. Revisá `history` antes de elegir hipótesis para priorizar categorías menos exploradas y evitar repetir mecánicamente el último run.

## Ciclo obligatorio por experimento

1. Declarar una hipótesis antes de tocar estado:

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py hypothesis --invariant <id> --category <categoria> --text "<hipotesis>"
```

2. Ejecutar herramientas determinísticas del motor únicamente mediante `engine_qa_safe.py exec`. Usá `@course`, `@slug`, `@run`, `@root` y sus formas `@course/...`, `@run/...`, `@root/...` para que el wrapper resuelva rutas dentro del sandbox.

Ejemplo:

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py exec --script topic_catalog.py -- reconcile --course @course --unit unidad-1 --write
```

El wrapper rechaza `..`, cursos ajenos y rutas absolutas fuera del sandbox/run/outbox antes de lanzar el proceso.

3. Toda alteración adversarial de inputs debe pasar por `mutate` y permanecer dentro de la materia `qa-engine-*` del sandbox.

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py mutate --op append --path unidades/unidad-1/fuentes/oficiales/fundamentos.txt --text "\nNuevo dato sintético.\n"
```

4. Después de una secuencia relevante, ejecutar:

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py check
```

5. Si el propio trabajo semántico del agente creó o modificó archivos dentro de la materia QA siguiendo `procesar`, `resumen`, `quiz`, etc., registrar inmediatamente el cambio con:

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py checkpoint --label "descripcion-del-estado"
```

Nunca uses materias reales como fixture QA.

## Qué atacar

Rotá entre estas familias, priorizando huecos vistos en `history`:
- unit isolation y resolución de scopes;
- idempotencia de ingesta/reconciliación;
- stale/fingerprints después de cambios semánticos y no semánticos;
- topics y concept assignments;
- claims, uncertainty y contradicciones;
- assessment scope/aliases;
- tracker y mastery;
- publicación atómica, rollback y hashes;
- runs interrumpidos o canonical state cambiado;
- Unicode, renombres, duplicados y cambios de orden;
- PDFs/transcripciones sintéticas;
- secuencias largas de operaciones;
- diferencias entre CLI/MCP/pipelines cuando sea posible.

No gastes el presupuesto principalmente en visuales. Los gates visuales existentes son secundarios dentro de Engine QA.

## Uso de los pipelines IA

El agente puede probar comportamiento de `procesar`, `resumen`, `repaso`, `quiz`, `preguntas`, `simulacro`, `estado`, `aprender` y `estudiar` contra la materia sintética. Para hacerlo, seguí sus pipelines canónicos exactamente igual que en uso normal, pero manteniendo todo el estado dentro de la materia QA y registrando checkpoints.

No arregles el engine aunque un pipeline falle. Investigá el fallo, reducí el caso y seguí probando.

## Hallazgos

No registres una sospecha al primer fallo. Antes:
1. repetí o reconstruí el caso;
2. distinguí fallo del motor de comportamiento esperado;
3. reducí la reproducción a la menor secuencia determinista posible;
4. anotá expected vs actual.

Después:

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py finding --confirmed --severity high --invariant <id> --title "..." --expected "..." --actual "..." --notes "..."
```

Un finding debe apuntar al motor/contrato, no a una preferencia estética.

Antes del cierre, cualquier issue inesperado que siga apareciendo en `check` debe quedar confirmado como finding o explicado/restaurado como una mutación adversarial deliberada. No cierres dejando un FAIL inexplicado que después no llegue al reporte de GitHub.

## Cierre

Siempre terminá con:

```text
python scripts/venv_exec.py scripts/engine_qa_safe.py finish --export
```

Esto actualiza el historial local y crea un paquete compacto en `qa/reports/<run-id>/` con `report.md`, `report.json`, findings y contexto de replay. No exporta la materia sintética completa ni material privado.

### Publicación del reporte

Si existen findings confirmados y Git está disponible, **no cambies la rama del checkout principal**. Publicá desde un worktree temporal:

1. confirmar `git status --short` y no tocar cambios ajenos;
2. crear la rama `qa/engine-<run-id>` desde `dev` sin checkout;
3. crear un worktree bajo `.study/engine-qa/publish/<run-id>/` para esa rama;
4. copiar allí **solamente** `qa/reports/<run-id>/`;
5. commit `Engine QA findings <run-id>`;
6. push y abrir un **draft PR** contra `dev` titulado `Engine QA findings <run-id>`;
7. remover el worktree temporal.

Nunca incluyas `materias/`, `.study/` ni cambios del engine. Si no hay findings, no abras un PR de reporte. El usuario no debe tener que copiar la conversación: un futuro agente puede localizar el último PR `Engine QA findings ...` y leer el paquete directamente.

## Resultado al usuario

Informá sólo:
- experimentos ejecutados;
- categorías cubiertas;
- cantidad/severidad de findings;
- si se publicó un draft PR de reporte;
- cualquier bloqueo del harness.

No vuelques el journal completo en el chat.
