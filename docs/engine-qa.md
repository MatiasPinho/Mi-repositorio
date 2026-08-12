# Engine QA Lab

Engine QA Lab es el entorno interno para someter el motor del University Study System a pruebas adversariales iterativas dirigidas por Claude o Codex sin usar materias reales.

## Objetivo

Separar dos responsabilidades:

```text
Claude / Codex
    ↓
explora, formula hipótesis, decide secuencias
    ↓
scripts/engine_qa.py
    ↓
confina cambios + registra + compara + valida invariantes
    ↓
motor V4 real
```

El agente sirve para descubrir espacios de fallo que todavía no conocemos. El harness sirve para que la evidencia no dependa de la memoria o narrativa del modelo.

Engine QA no reemplaza la release suite. Un bug descubierto una vez debe terminar convertido en un test determinístico permanente.

## Seguridad

Cada run crea una materia `materias/qa-engine-<run-id>` y estado efímero bajo `.study/engine-qa/`.

El harness captura al comienzo un fingerprint SHA-256 de:
- `study.py`;
- `core/`;
- `rules/`;
- `pipelines/`;
- `contracts/`;
- `vendor/`;
- `scripts/`;
- `study_mcp/`;
- `config/`;
- `actions/`;
- `assets/`;
- `design/`.

Antes y después de cada ejecución/mutación comprueba que esas rutas no hayan cambiado. Cualquier drift bloquea el run como `engine-mutated-during-qa`.

Las mutaciones del harness resuelven las rutas contra la materia sintética y rechazan path traversal. `exec` sólo admite scripts explícitamente allowlisted y comprueba que `--course` apunte al curso QA del run.

## Materia sintética

`start` genera automáticamente:
- `academic.json` con tres unidades y una evaluación;
- layout V4 completo mediante `course_layout.sync_units`;
- fuentes TXT unit-scoped;
- una transcripción SRT con timestamps y señal docente;
- una fuente course-wide con Unicode variable según seed;
- un PDF sintético de dos páginas cuando PyMuPDF está disponible.

No hace falta cargar material manualmente.

## Presupuesto e historial

Cada run tiene un número finito de experimentos (`1..200`). Un experimento empieza con `hypothesis`, que registra:
- invariante atacado;
- categoría;
- hipótesis textual;
- número de experimento.

`finish` agrega una entrada a `.study/engine-qa/history.json`. `history` resume las categorías exploradas y los invariantes donde ya aparecieron findings. El agente debe usar esa información para evitar repetir siempre la misma estrategia.

## Journal y snapshots

Todas las operaciones relevantes se guardan en `journal.jsonl` con número de paso y timestamp.

`exec` registra:
- script y argumentos lógicos/expandidos;
- código de salida esperado/real;
- stdout/stderr acotados;
- fingerprint del workspace antes/después;
- archivos agregados, eliminados y modificados;
- confirmación de que el engine quedó inmutable.

`mutate` registra el mismo diff para cambios adversariales sobre inputs.

`checkpoint` captura un snapshot del curso para cambios semánticos que el propio agente haya realizado siguiendo un pipeline IA.

## Invariantes V1

`check` comprueba mecánicamente, entre otros:
- engine inmutable;
- `academic.json` válido;
- layout físico igual al set de unidades declarado;
- todo JSON del curso parseable;
- registries obligatorios presentes por unidad;
- conceptos unit-local cuando declaran `unit_id`;
- `topics.json.unit_id` correcto;
- todo `concept_id` usado por topics existe;
- un concepto no aparece en más de un topic primario;
- `assigned` y `unassigned` no se superponen;
- todo unassigned existe;
- todo concepto está asignado o explícitamente unassigned;
- progress no referencia conceptos inexistentes;
- figuras no declaran otra unidad.

Estos checks no pretenden cubrir toda la semántica. El agente puede formular invariantes adicionales y documentarlos en un finding; si resultan válidos, deben promoverse después al checker o a la release suite.

## Familias de experimentos recomendadas

- idempotencia: repetir una operación sin cambios de input;
- metamorphic: renombrar, reordenar, cambiar line endings o aliases sin cambiar semántica;
- stale/fingerprints: contrastar cambios semánticos vs no semánticos;
- unit isolation: operaciones sobre U2 no deben mutar U1/U3;
- fault injection: borrar/corromper registries, assets o inputs sintéticos;
- topics: reassignments, IDs, aliases, unassigned;
- claims/assessment: incertidumbre, contradicciones, scope y aliases;
- tracker: progress huérfano, intentos, mastery, due reviews;
- publication/run safety: cambios entre start/finish, rollback, hashes;
- source stress: Unicode, duplicados, renombres, PDFs y transcripciones;
- sequence testing: combinaciones largas de sync/procesar/status/reset/reprocesar;
- provider differential: mismo escenario semántico en Claude y Codex.

## Findings

Una anomalía no es un finding hasta ser confirmada. El agente debe intentar reproducirla y reducirla.

`finding --confirmed` crea:

```text
.study/engine-qa/runs/<run>/findings/QA-001/
├── finding.json
└── reproduction.md
```

Incluye expected, actual, severidad, invariante, seed y los pasos recientes relevantes.

## Reporte y handoff

`finish --export` crea un paquete compacto:

```text
qa/reports/<run-id>/
├── report.md
├── report.json
├── replay.json
└── findings/
```

No copia el workspace sintético completo. `replay.json` conserva contexto operativo suficiente para orientar la reproducción; antes de corregir, cada bug debe reducirse a pasos determinísticos y convertirse en regresión.

Cuando existan findings, la skill `engine-qa` intenta publicar sólo este directorio en un draft PR `Engine QA findings <run-id>`. De este modo otra sesión de ChatGPT puede localizar el último reporte directamente en GitHub sin que el usuario copie logs o conversaciones.

## Flujo de reparación

```text
Engine QA run (engine read-only)
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