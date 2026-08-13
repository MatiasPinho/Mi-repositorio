---
name: engine-qa
description: Internal autonomous adversarial QA loop for the University Study engine. Creates only synthetic courses, executes a frozen engine copy through a guarded structured transport, records valid/invalid experiments and findings, and exports reproducible reports. Never edits engine code during the QA run.
argument-hint: "[experimentos opcionales]"
disable-model-invocation: true
---

# Engine QA — QA adversarial autónomo del motor

Esta skill es **interna de desarrollo**. No forma parte de las nueve acciones públicas para estudiantes.

## Objetivo

Probar el motor de forma iterativa sin que el usuario cargue PDFs, ejecute acciones manualmente ni copie conversaciones. El agente crea una materia sintética, formula hipótesis, ejecuta una copia congelada del motor real, muta únicamente ese workspace QA, compara estados, comprueba invariantes, confirma fallos y deja un reporte reproducible.

Leé primero:
- `../../../docs/engine-qa.md`
- `../../../core/ROUTER.md`

## Regla absoluta

Durante un Engine QA run **no edites el checkout real**. Esto incluye `study.py`, `core/`, `rules/`, `pipelines/`, `contracts/`, `vendor/`, `scripts/`, `study_mcp/`, `config/`, `actions/`, `assets/`, `design/`, `skills-src/`, `.claude/skills/`, `.agents/skills/`, `tests/`, `docs/` y `.github/`.

La entrada canónica para Claude/Codex es `scripts/engine_qa_rpc_entry.py`. Esta entrada usa `engine_qa_rpc.py` para el despacho estructurado y `engine_qa_safe.py` para crear el sandbox congelado, confinar rutas y vigilar el checkout real. Nunca invoques `scripts/engine_qa.py` directamente, nunca ejecutes `scripts/engine_qa_rpc.py` como CLI y no uses el CLI posicional de `engine_qa_safe.py` durante una corrida normal.

Un hallazgo se arregla después, en un PR distinto.

## Transporte estructurado obligatorio

Los argumentos complejos **no viajan por argv de PowerShell/Bash**. Cada petición es JSON UTF-8 bajo `.study/engine-qa/requests/` y cada respuesta es JSON UTF-8 bajo `.study/engine-qa/responses/`. Así espacios, Unicode, JSON embebido y `--run` internos conservan exactamente sus tokens.

En PowerShell definí una vez este helper:

```powershell
$QaReqDir = '.study/engine-qa/requests'
$QaResDir = '.study/engine-qa/responses'
New-Item -ItemType Directory -Force $QaReqDir,$QaResDir | Out-Null
function Invoke-EngineQA([hashtable]$Body) {
  $id = [guid]::NewGuid().ToString('N')
  $req = Join-Path $QaReqDir "$id.json"
  $res = Join-Path $QaResDir "$id.json"
  $Body['version'] = 2
  $Body['request_id'] = $id
  $Body | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $req -Encoding utf8
  & python 'scripts/venv_exec.py' 'scripts/engine_qa_rpc_entry.py' '--request-file' $req '--response-file' $res
  $code = $LASTEXITCODE
  if (-not (Test-Path -LiteralPath $res)) { throw "Engine QA RPC no produjo respuesta (exit=$code)" }
  $out = Get-Content -LiteralPath $res -Raw -Encoding UTF8 | ConvertFrom-Json
  Remove-Item -LiteralPath $req,$res -Force -ErrorAction SilentlyContinue
  if ($code -eq 2 -or -not $out.transport_ok) { throw "Engine QA RPC transport failure: $($out.error)" }
  return $out
}
```

En otros shells hacé lo equivalente con un serializador JSON real y archivos UTF-8. **No construyas JSON a mano ni reconstruyas arrays como strings.**

El exit code del entrypoint informa salud del transporte: `0` significa que la petición fue parseada y produjo una respuesta estructurada, incluso cuando `response.ok=false`; `2` significa fallo real del protocolo/transporte. Tanto el request como el response se validan dentro del QA root **antes** de ejecutar una operación stateful.

## Inicio

```powershell
Invoke-EngineQA @{ command='history' }
Invoke-EngineQA @{ command='start'; budget=<N>; seed=<seed>; provider='<codex|claude>' }
```

Si el usuario no indicó cantidad, usá **25 experimentos válidos**. Variá el seed entre corridas. Revisá `history` antes de elegir hipótesis para priorizar categorías menos exploradas.

`qa_run` identifica el Engine QA run y por defecto es `latest`. Es un campo JSON separado; nunca comparte nombre/posición con un `--run` que pertenezca a una herramienta interna.

## Ciclo obligatorio por experimento

### 1. Abrir hipótesis y declarar qué evidencia la valida

Toda hipótesis declara `evidence_mode`:
- `engine` — modo por defecto; exige una invocación real con `engine_invoked=true` **y `ok=true`**, es decir, el retorno debe coincidir con `expect_code`;
- `guard` — para probar deliberadamente el confinamiento; exige un rechazo pre-engine del guard;
- `state` — para invariantes de workspace/checker; si se ejecuta `check`, su `ok` debe coincidir con `expected_check_ok` (por defecto `true`). Una hipótesis state sin `check` puede justificarse por `mutation` o `checkpoint`.

Ejemplo normal:

```powershell
Invoke-EngineQA @{
  command='hypothesis'; qa_run='latest'; invariant='<id>';
  category='<categoria>'; text='<hipotesis>'; evidence_mode='engine'
}
```

Ejemplo de guard:

```powershell
Invoke-EngineQA @{
  command='hypothesis'; qa_run='latest'; invariant='path-confinement';
  category='guard'; text='una salida fuera del sandbox debe rechazarse'; evidence_mode='guard'
}
```

Ejemplo de estado/checker donde se espera detectar corrupción:

```powershell
Invoke-EngineQA @{
  command='hypothesis'; qa_run='latest'; invariant='course-json-valid';
  category='fault-injection'; text='un JSON corrupto debe aparecer en check';
  evidence_mode='state'; expected_check_ok=$false
}
```

Para un sweep final o una hipótesis que espera un workspace sano, omití `expected_check_ok` o usá `$true`. Un `check ok=false` inesperado **no puede** sumar como `VALID`; confirmalo como finding o clasificá el intento `INVALID` y restaurá el estado según corresponda.

Sólo puede existir una hipótesis pendiente. `VALID` será rechazado mecánicamente si no existe evidencia del tipo y resultado declarados después de la hipótesis. Además, **la misma evidencia mecánica sobre el mismo estado del workspace no puede contabilizarse dos veces**: repetir el mismo probe sin cambiar estado ni operación no sirve para rellenar presupuesto.

### 2. Ejecutar el motor con tokens estructurados

```powershell
Invoke-EngineQA @{
  command='exec'; qa_run='latest'; script='study_tracker.py';
  args=@('due','--course','@course','--assessment','Parcial 1','--include-not-due')
}
```

`args` es siempre un array JSON de strings. Un argumento con JSON sigue siendo **un solo string**, por ejemplo:

```powershell
args=@('show','--course','@course','--probe','{"name":"Parcial 1","unicode":"漢"}')
```

Un `--run` interno también queda dentro de `args` y no puede seleccionar el QA run:

```powershell
args=@('status','--run','pipeline-run-id')
```

Se conservan `@course`, `@slug`, `@run`, `@root` y sus formas `@course/...`, `@run/...`, `@root/...`. El guard rechaza `..`, cursos ajenos y rutas absolutas fuera del sandbox/run/outbox antes de lanzar el proceso.

La respuesta de `exec` incluye `engine_invoked` y `ok`. En `evidence_mode='engine'`, sólo `engine_invoked=true` **y** `ok=true` puede terminar como `VALID`. Un retorno no-cero esperado sigue siendo `ok=true` si `expect_code` lo declara correctamente. En `evidence_mode='guard'`, en cambio, un rechazo del guard es precisamente la evidencia esperada.

Nota de contrato: en `render_study.py`, `--course` es **texto visible del encabezado**, no una ruta hacia la materia. La entrada/salida siguen confinadas por sus paths, pero una etiqueta como `--course 'Sistemas Operativos'` es válida.

### 3. Mutaciones adversariales

Toda alteración de inputs debe pasar por `mutate` y permanecer dentro de la materia `qa-engine-*`:

```powershell
Invoke-EngineQA @{
  command='mutate'; qa_run='latest'; op='append';
  path='unidades/unidad-1/fuentes/oficiales/fundamentos.txt';
  text="`nNuevo dato sintético con JSON {`"k`":`"v`"}.`n"
}
```

Como el texto se serializa a JSON por el helper, no depende del quoting del comando Python.

### 4. Checks/checkpoints

```powershell
Invoke-EngineQA @{ command='check'; qa_run='latest' }
Invoke-EngineQA @{ command='checkpoint'; qa_run='latest'; label='descripcion-del-estado' }
```

Nunca uses materias reales como fixture QA.

### 5. Cerrar el experimento como VALID o INVALID

Si la hipótesis produjo evidencia que coincide con su `evidence_mode` y con el resultado declarado:

```powershell
Invoke-EngineQA @{ command='experiment-result'; qa_run='latest'; status='valid'; notes='...' }
```

Si el arnés/transport impidió ejecutar la prueba pretendida o la evidencia esperada no pudo producirse:

```powershell
$invalid = Invoke-EngineQA @{
  command='experiment-result'; qa_run='latest'; status='invalid';
  reason='la prueba no llegó al motor por ...'
}
```

Un `INVALID` incrementa intentos/ruido pero **no consume el presupuesto**. Su respuesta incluye `replacement_required.attempt` y la **siguiente hipótesis debe enlazar explícitamente ese intento**:
- `replacement_kind='retry'` cuando corregís la invocación y volvés a probar el mismo `invariant` + `category`;
- `replacement_kind='distinct'` cuando reemplazás la prueba por una hipótesis genuinamente diferente.

Ejemplo de retry:

```powershell
Invoke-EngineQA @{
  command='hypothesis'; qa_run='latest'; invariant='<mismo-invariant>';
  category='<misma-categoria>'; text='<hipotesis corregida>'; evidence_mode='engine';
  replaces_attempt=[int]$invalid.replacement_required.attempt; replacement_kind='retry'
}
```

No saltees ese enlace y **no reemplaces INVALIDs con probes read-only genéricos o repetidos sólo para completar N/N**. Si el intento original falló por un selector/slug equivocado, corregí ese selector y reintentá la hipótesis. Si la prueba dejó de tener sentido, usá `distinct` con una prueba realmente diferente. Un retorno no-cero esperado del motor puede seguir siendo `VALID`; lo decisivo es que exista la evidencia mecánica correcta para la hipótesis declarada.

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

## Uso de pipelines IA

Podés probar `procesar`, `resumen`, `repaso`, `quiz`, `preguntas`, `simulacro`, `estado`, `aprender` y `estudiar` contra la materia sintética siguiendo sus pipelines canónicos. Todo estado debe permanecer en la materia QA y registrarse con checkpoints.

No arregles el engine aunque falle. Investigá, reducí el caso y seguí probando la misma versión congelada.

## Hallazgos

No registres una sospecha al primer fallo. Antes:
1. repetí o reconstruí el caso;
2. distinguí fallo del motor de comportamiento esperado o ruido de harness;
3. reducí la reproducción;
4. anotá expected vs actual.

Después:

```powershell
Invoke-EngineQA @{
  command='finding'; qa_run='latest'; confirmed=$true; severity='high';
  invariant='<id>'; title='...'; expected='...'; actual='...'; notes='...'
}
```

Un finding debe apuntar al motor/contrato, no a una preferencia estética. Antes del cierre, todo issue inesperado de `check` debe quedar confirmado como finding o restaurado/explicado como mutación deliberada.

## Cierre

Consultá primero:

```powershell
Invoke-EngineQA @{ command='info'; qa_run='latest' }
```

`finish` rechaza una campaña no bloqueada mientras `valid_experiments < budget` o exista una hipótesis pendiente. Ese rechazo es una respuesta normal (`transport_ok=true`, `ok=false`), no un fallo del transporte. Cuando el presupuesto válido esté completo:

```powershell
Invoke-EngineQA @{ command='finish'; qa_run='latest'; export=$true }
```

El reporte distingue:
- `valid_experiments`, `attempted_experiments` e `invalid_experiments`;
- `valid_by_category` y `attempted_by_category`;
- `invalid_rows` y `replacement_rows`;
- cantidad de evidencias mecánicas únicas;
- findings e invariantes finales.

El `replay.json` exportado conserva **todo el journal**, compactando stdout/stderr grandes y guardando su SHA-256 y cantidad de caracteres. No se limita a los últimos eventos, por lo que los INVALID y sus reemplazos quedan auditables desde el reporte publicado.

Así `100/100` significa cien hipótesis cerradas con **evidencia mecánica compatible, única para ese estado y resultado declarado**, y cualquier ruido del arnés queda preservado y enlazado en la evidencia de campaña.

## Publicación del reporte

Si existen findings confirmados y Git está disponible, **no cambies la rama del checkout principal**. Publicá desde un worktree temporal:
1. confirmar `git status --short` y no tocar cambios ajenos;
2. crear `qa/engine-<run-id>` desde `dev` sin checkout;
3. worktree bajo `.study/engine-qa/publish/<run-id>/`;
4. copiar sólo `qa/reports/<run-id>/`;
5. commit `Engine QA findings <run-id>`;
6. push y draft PR contra `dev`;
7. remover el worktree.

Nunca incluyas `materias/`, `.study/` ni cambios del engine. Si no hay findings, no abras PR salvo pedido explícito del usuario.

## Resultado al usuario

Informá sólo:
- experimentos **válidos / presupuesto**;
- intentos inválidos si existieron;
- categorías cubiertas y distribución válida por categoría;
- cantidad/severidad de findings;
- draft PR si se publicó;
- cualquier bloqueo real del harness.

No vuelques el journal completo en el chat.
