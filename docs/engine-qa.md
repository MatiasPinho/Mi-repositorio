# Engine QA Lab

Engine QA Lab es el entorno interno para someter el motor del University Study System a pruebas adversariales iterativas dirigidas por Claude o Codex sin usar materias reales.

## Objetivo

Separar cinco responsabilidades:

```text
Claude / Codex
    ↓
explora, formula hipótesis, decide secuencias
    ↓
scripts/engine_qa_rpc_entry.py
    ↓
valida rutas de protocolo + distingue transporte de workflow
    ↓
scripts/engine_qa_rpc_policy.py
    ↓
exige evidencia mecánica compatible con cada VALID
    ↓
scripts/engine_qa_rpc.py
    ↓
transporta/dispacha requests JSON sin quoting de shell
    ↓
scripts/engine_qa_safe.py
    ↓
crea sandbox congelado + confina rutas + vigila checkout
    ↓
scripts/engine_qa.py dentro del sandbox
    ↓
motor V4 congelado para ese run
```

El agente sirve para descubrir espacios de fallo todavía desconocidos. El harness hace que la evidencia no dependa de la memoria o narrativa del modelo. Engine QA no reemplaza la release suite: un bug descubierto una vez debe terminar convertido en un test determinístico permanente.

## Entrada canónica

La única entrada normal para Claude/Codex es:

```text
python scripts/venv_exec.py scripts/engine_qa_rpc_entry.py \
  --request-file .study/engine-qa/requests/<id>.json \
  --response-file .study/engine-qa/responses/<id>.json
```

`engine_qa_rpc_entry.py` es el entrypoint de proceso y reserva los exit codes para la salud del protocolo. `engine_qa_rpc_policy.py` aplica la política de evidencia. `engine_qa_rpc.py` implementa el dispatcher estructurado; se conserva como implementación/compatibilidad y **no debe ejecutarse como CLI normal**. `engine_qa_safe.py` conserva la seguridad de sandbox/rutas. `engine_qa.py` es el harness interno y no debe invocarse directamente durante una corrida normal.

El entrypoint sólo usa argv para dos rutas simples (`--request-file`/`--response-file`). Todo contenido complejo —espacios, Unicode, JSON, aliases y flags de herramientas internas— viaja dentro del JSON request.

## Por qué existe el RPC

Las primeras campañas adversariales demostraron que PowerShell podía alterar o perder tokens cuando el agente reconstruía arrays dinámicos:
- nombres como `Parcial 1` podían separarse;
- JSON embebido podía perder comillas;
- Unicode fuera de CP1252 podía contaminar salida;
- un `--run` de una herramienta interna podía competir conceptualmente con el `--run` del Engine QA.

El protocolo elimina esa superficie. La selección del QA run vive en `qa_run`; los argumentos del motor viven en `args: [string, ...]`. Un `--run` dentro de `args` pertenece siempre a la herramienta objetivo.

Las respuestas se escriben en UTF-8 y el agente las lee explícitamente como UTF-8. La consola del sistema no participa en el contrato machine-readable.

## Esquema de request V2

Inicio:

```json
{
  "version": 2,
  "command": "start",
  "budget": 100,
  "seed": 260813100,
  "provider": "codex"
}
```

Hipótesis normal:

```json
{
  "version": 2,
  "command": "hypothesis",
  "qa_run": "latest",
  "invariant": "assessment-scope",
  "category": "assessment",
  "text": "Parcial 1 debe resolverse como un único token",
  "evidence_mode": "engine"
}
```

Ejecución con espacios, Unicode y un `--run` interno:

```json
{
  "version": 2,
  "command": "exec",
  "qa_run": "latest",
  "script": "pipeline_run.py",
  "args": ["status", "--run", "run interno con espacio 漢"],
  "expect_code": 1
}
```

Argumento que por sí mismo contiene JSON:

```json
{
  "version": 2,
  "command": "exec",
  "qa_run": "latest",
  "script": "academic_context.py",
  "args": ["show", "--course", "@course", "--probe", "{\"name\":\"Parcial 1\",\"unicode\":\"漢\"}"],
  "expect_code": 2
}
```

Aunque la herramienta rechace deliberadamente un flag desconocido, el journal puede demostrar que recibió exactamente un token JSON intacto.

## Semántica del exit code

El entrypoint usa el exit code sólo para el transporte:
- `0`: request parseado y respuesta estructurada persistida; `response.ok` puede ser `true` o `false`;
- `2`: request JSON/archivo/protocolo o persistencia de respuesta fallaron.

Intentar `finish` con 87/100 experimentos válidos devuelve exit `0`, `transport_ok=true`, `ok=false` y un error de campaña incompleta. No se confunde con un transporte roto.

El path de `response-file` se valida **antes de leer/ejecutar el comando stateful**. Si intenta salir de `.study/engine-qa/responses/`, el proceso termina con exit `2` sin crear un run, mutar el sandbox ni ejecutar el motor.

`exec` agrega:
- `transport_ok`;
- `engine_invoked`;
- `request_args` exactamente como llegaron en JSON;
- `expanded_args` después de aliases/guard;
- código de salida y stdout/stderr del motor.

## Evidencia mecánica de un experimento válido

V2.1 evita que el contador dependa sólo de una decisión narrativa del modelo. Cada `hypothesis` declara `evidence_mode`:

- `engine` — modo por defecto. Para cerrar `VALID` debe existir después de la hipótesis un `rpc-exec` o `rpc-exec-timeout` con `engine_invoked=true`.
- `guard` — para probar deliberadamente confinamiento/validación previa. Debe existir un `rpc-exec-rejected` con `engine_invoked=false`.
- `state` — para fault injection, checker y transformaciones de workspace. Debe existir una `mutation`, `check` o `checkpoint`.

Si la evidencia no coincide con el modo, `experiment-result status=valid` devuelve una respuesta normal de workflow (`transport_ok=true`, `ok=false`) y **no incrementa** `valid_experiments`. La hipótesis sigue pendiente hasta ser cerrada correctamente como `VALID` o `INVALID`.

Ejemplos:

```json
{"command":"hypothesis","qa_run":"latest","invariant":"path-confinement","category":"guard","text":"...","evidence_mode":"guard"}
```

```json
{"command":"hypothesis","qa_run":"latest","invariant":"course-json-valid","category":"fault-injection","text":"...","evidence_mode":"state"}
```

Esto hace que `100/100` tenga una definición verificable: cien hipótesis cerradas con evidencia compatible con el tipo de prueba declarado.

## Seguridad en dos capas

### 1. Sandbox congelado del motor

Cada `start` crea una copia privada bajo:

```text
.study/engine-qa/sandboxes/engine-<id>/
```

La materia `qa-engine-*` vive dentro de `sandbox/materias/`, nunca en el árbol real de materias del usuario. Los scripts allowlisted se ejecutan desde esa copia y su `ROOT` apunta al sandbox.

El sandbox contiene la misma versión de `study.py`, `core/`, `rules/`, `pipelines/`, `contracts/`, `vendor/`, `scripts/`, `study_mcp/`, `config/`, `actions/`, `assets/` y `design/` que existía al comenzar el run. Esa copia conserva su propio fingerprint SHA-256 y el harness bloquea drift interno.

### 2. Guard del checkout real

`engine_qa_safe.py` registra un fingerprint independiente del checkout real incluyendo motor, skills, tests, docs y CI. Antes de continuar un run verifica que el checkout no haya cambiado desde `start`.

Si cambió, el run queda bloqueado como `live-checkout-mutated-during-qa` en vez de mezclar versiones.

### Rutas de `exec`

Antes de lanzar un proceso, la capa segura:
- sólo admite scripts allowlisted;
- expande `@course`, `@run`, `@root`, `@slug`;
- admite `@course/...`, `@run/...`, `@root/...`;
- rechaza cualquier segmento `..`;
- rechaza `--course`/`--course=` que no apunte exactamente a la materia QA;
- rechaza rutas absolutas fuera del sandbox, directorio de run u outbox de reportes;
- valida también opciones `--out=<ruta>`.

## Materia sintética

`start` genera automáticamente:
- `academic.json` con tres unidades y evaluación;
- layout V4 completo mediante `course_layout.sync_units`;
- fuentes TXT unit-scoped;
- transcripción SRT con timestamps/señal docente;
- fuente course-wide con Unicode variable según seed;
- PDF sintético de dos páginas cuando PyMuPDF está disponible.

No hace falta cargar material manualmente.

## Presupuesto: sólo cuentan experimentos válidos

El protocolo separa:
- `valid_experiments`: hipótesis cerradas con evidencia mecánica compatible;
- `attempted_experiments`: todos los intentos abiertos;
- `invalid_experiments`: intentos invalidados por ruido/transport/harness;
- `pending_experiment`: como máximo uno.

`hypothesis` no consume presupuesto. Después de ejecutar la secuencia, el agente debe cerrar explícitamente:

```json
{"command":"experiment-result","qa_run":"latest","status":"valid"}
```

o:

```json
{
  "command":"experiment-result",
  "qa_run":"latest",
  "status":"invalid",
  "reason":"la invocación no llegó al motor"
}
```

Un `INVALID` se registra, pero no consume presupuesto. Si el budget es 100, `finish` exige 100 experimentos válidos aunque hayan sido necesarios más intentos.

`finish` también rechaza una campaña con hipótesis pendiente. `allow_partial=true` existe sólo para cierres deliberadamente parciales/bloqueados; no debe usarse para presentar una campaña incompleta como completa.

## Journal y snapshots

Todas las operaciones relevantes se guardan en `journal.jsonl` con número de paso y timestamp.

`exec` registra script, argumentos, código esperado/real, stdout/stderr acotados, fingerprints before/after, diff del workspace y confirmación de inmutabilidad del engine.

El RPC agrega `rpc-exec`, `rpc-exec-rejected` y `rpc-exec-timeout`. La policy usa esos eventos —junto con `mutation`, `check` y `checkpoint`— como prueba mecánica antes de aceptar `VALID`.

`mutate` registra diff para cambios adversariales sobre inputs. `checkpoint` captura un snapshot del curso para cambios semánticos realizados siguiendo un pipeline IA.

## Invariantes V1

`check` comprueba mecánicamente, entre otros:
- engine congelado inmutable;
- `academic.json` parseable;
- layout físico igual al set de unidades declarado;
- todo JSON del curso parseable;
- registries obligatorios presentes por unidad;
- conceptos unit-local cuando declaran `unit_id`;
- `topics.json.unit_id` correcto;
- todo `concept_id` usado por topics existe;
- un concepto no aparece en más de un topic primario;
- assigned/unassigned no se superponen;
- todo unassigned existe;
- todo concepto está asignado o explícitamente unassigned;
- progress no referencia conceptos inexistentes;
- figuras no declaran otra unidad.

Estos checks no pretenden cubrir toda la semántica. El agente puede formular invariantes adicionales; si son válidos, deben promoverse después al checker o a la release suite.

## Familias de experimentos recomendadas

- idempotencia;
- metamorphic (rename/order/line endings/aliases);
- stale/fingerprints;
- unit isolation;
- fault injection;
- topics;
- claims/assessment;
- tracker;
- publication/run safety;
- Unicode/duplicados/PDF/transcripciones;
- secuencias largas;
- provider differential.

## Findings

Una anomalía no es finding hasta confirmarse y reducirse. `finding` crea:

```text
.study/engine-qa/runs/<run>/findings/QA-001/
├── finding.json
└── reproduction.md
```

Incluye expected, actual, severidad, invariante, seed y evidencia reciente.

Antes de cerrar, un `check` final no debe dejar issues inesperados sin clasificar: o se restauran porque eran mutaciones deliberadas, o se confirman como finding.

## Reporte y handoff

`finish` con `export=true` crea:

```text
qa/reports/<run-id>/
├── report.md
├── report.json
├── replay.json
└── findings/
```

El reporte incluye `valid_experiments`, `attempted_experiments`, `invalid_experiments`, protocolo de transporte, findings e invariantes finales. La materia sintética completa nunca se exporta.

Cuando existan findings, la skill publica sólo ese directorio en un draft PR `Engine QA findings <run-id>` usando un worktree temporal. Si no hay findings, no abre PR salvo pedido explícito del usuario.

## Flujo de reparación

```text
Engine QA run (motor congelado + transporte estructurado + evidence policy)
        ↓
N experimentos válidos con evidencia mecánica
        ↓
finding confirmado
        ↓
draft PR de reporte
        ↓
PR de fix separado
        ↓
regression test determinístico
        ↓
CI Windows + Ubuntu
        ↓
nuevo Engine QA run con otro seed/estrategia
```

Nunca se arregla el engine dentro del mismo QA run que lo está evaluando.
