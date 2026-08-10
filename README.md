# University Study System V3.7.2

Sistema local para estudiar materias universitarias con **Claude Code o Codex** usando el mismo núcleo metodológico y una salida visual pensada para lectura real, no Markdown crudo.

V3.7.2 conserva la arquitectura portable de V3, mantiene el **MCP local por stdio** como interfaz segura y refuerza el reviewer académico adversarial. Usa como superficie visual un **manual universitario contemporáneo**: gutter semántico, prosa de lectura larga, aparato editorial para figuras/tablas/código y fidelidad estructural al rediseño de referencia de Claude. Claude y Codex siguen siendo **motores de ejecución** del mismo core portable.

## Principio central

```text
                         FUENTES
                            │
                            ▼
                    CONOCIMIENTO CANÓNICO
                  academic + concepts + evidence
                            │
                            ▼
                    PIPELINE COMPARTIDO
                            │
                 ┌──────────┴──────────┐
                 │                     │
            Claude Code              Codex
                 │                     │
                 └──────────┬──────────┘
                            │
                       mismo resultado
```

La infraestructura interna puede ser obsesivamente trazable. El material que lee el estudiante debe ser **normal, humano, claro y didáctico**.

## Inicio rápido

En Windows podés abrir `INICIAR-STUDY.bat`, o desde terminal:

```bash
python study.py
```

Activar el MCP local (opcional, recomendado para Claude Code/Codex):

```bash
python -m pip install -r requirements-mcp.txt
python study.py mcp preflight
```

La release incluye `.mcp.json` y `.codex/config.toml`. Ambos arrancan el mismo adapter con `python study.py mcp serve`; el core sigue funcionando por CLI si MCP no está disponible.

Crear una materia:

```bash
python study.py course add "Programación I"
```

Resetear una materia para reprocesarla desde cero, conservando los archivos originales de `fuentes/` y la identidad básica:

```bash
python study.py course reset programacion-i
```

El comando pide escribir exactamente el slug de la materia antes de borrar. También está disponible como **opción 13** del menú interactivo (`python study.py`). El reset elimina conocimiento procesado, contexto académico derivado, notas, progreso, resúmenes/guías/repasos, preguntas, simulacros, figuras generadas y `.study/`; después todos los materiales fuente vuelven a aparecer como nuevos para `/procesar`. Para automatización existe `--yes`.

Copiar fuentes a:

```text
materias/programacion-i/fuentes/
├── oficiales/
└── transcripciones/
```

Procesarlas:

```text
Claude: /procesar Programacion-I
Codex:  $procesar Programacion-I
```

Después generás sólo lo que necesitás:

```text
/resumen Programacion-I "Unidad 1"
/guia Programacion-I "Unidad 1"
/repaso Programacion-I "Unidad 1"
```

En Codex reemplazá `/` por `$`.

---

# Arquitectura V3

## 1. Una sola fuente de verdad

```text
core/                    router mínimo
rules/                   responsabilidades pequeñas y separadas
pipelines/               orden de ejecución
contracts/               contratos entre etapas
vendor/humanizer/        Humanizer canónico
config/actions.json      definición de acciones
```

`.claude/skills/` y `.agents/skills/` contienen **adaptadores finos generados**, no metodología duplicada.

Si cambiás una acción o Humanizer:

```bash
python scripts/sync_agent_assets.py generate
```

Verificar que Claude y Codex no divergieron:

```bash
python scripts/sync_agent_assets.py verify
```

## 2. Progressive disclosure

Una acción sólo carga las reglas que necesita.

Por ejemplo, `/resumen` carga pedagogía, escritura y evaluación. `/procesar` carga reglas de fuentes, ingestión y auditoría, pero **no Humanizer ni reglas de prosa**.

Esto reduce ruido de contexto y evita que reglas irrelevantes compitan entre sí.

## 3. MCP local como adapter seguro

```text
Claude Code / Codex
        │
        │ MCP stdio
        ▼
   study_mcp/
        │
        ▼
study.py + scripts/
        │
        ▼
estado canónico local
```

El MCP **no reemplaza** el core ni los pipelines. Expone lecturas agregadas como `study_get_unit_context` y escrituras acotadas como `study_register_derived_figure` para evitar que el agente tenga que reabrir, filtrar o editar registries delicados a mano. No hay tools V1 para borrar materias, resetear, escribir JSON arbitrario ni publicar archivos libres.

La interfaz es deliberadamente gruesa: una llamada debe traer un contexto coherente, no generar decenas de micro-llamadas. Si el MCP no está conectado, las mismas operaciones continúan por `study.py`/`scripts/`. Ver `docs/mcp.md`.

## 4. `/procesar` sigue siendo sólo ingesta

```text
fuentes nuevas/modificadas
        ↓
clasificación
        ↓
lectura semántica
        ↓
academic.json
concepts.json
contexto.md
        ↓
auditoría
        ↓
tracker + hashes
```

No genera resumen, guía, repaso, preguntas ni simulacro.

## 5. Pipeline de `/resumen`

```text
CONOCIMIENTO CANÓNICO + FIGURAS
        ↓
1. PLAN PEDAGÓGICO + DECISIÓN VISUAL
        ↓
2. BORRADOR SEMÁNTICO
        ↓
3. HUMANIZER (sólo prosa)
        ↓
4. REVIEW ACADÉMICO + PEDAGÓGICO + VISUAL
        ↓
     PASS ───────────────→ FINAL MD
        │
       FAIL
        ↓
5. UNA REPARACIÓN
        ↓
6. SEGUNDO REVIEW
        ↓
        FINAL MD
        ↓
7. RENDER DETERMINÍSTICO
        ↓
   HTML DE ESTUDIO
```

El Markdown es fuente portable para Claude/Codex y versionado. **El HTML es el artefacto normal de lectura.** Colores, tipografía, ancho de línea, callouts, índice y comportamiento de impresión los controla `scripts/render_study.py` + `assets/study-theme.css`, no la improvisación del modelo.

No hay loops infinitos: máximo dos reviews.

## 7. Design system congelado

La V3.6 separa explícitamente **design time** de **study time**. El theme aprobado es **contemporary technical manual**: papel cálido, tinta oscura, una columna de prosa estable y un gutter izquierdo que carga números de sección y etiquetas académicas sin cortar la lectura. Figuras, tablas y código pueden usar más ancho que la prosa.

```text
DESIGN TIME
frontend-design + study-design
        ↓
design/*.css
        ↓
visual_audit + study-design-reviewer
        ↓
assets/study-theme.css

STUDY TIME
/resumen /guia /repaso
        ↓
Markdown semántico
        ↓
renderer determinístico
        ↓
HTML
```

Las skills de diseño existen en ambos motores:

```text
Claude: /study-design
Codex:  $study-design

Claude: /study-design-reviewer
Codex:  $study-design-reviewer
```

No se cargan durante un resumen normal. El escritor sólo decide roles semánticos como `DEFINITION`, `EXAMPLE`, `WARNING`, `CONNECTION` o `RECALL`; nunca colores, fuentes o márgenes.

Fuente visual canónica:

```text
design/
├── tokens.css
├── typography.css
├── layout.css
├── components.css
├── figures.css
└── print.css
```

Regenerar el theme:

```bash
python scripts/build_design.py
```

La tipografía principal usa Source Serif 4 + IBM Plex mediante Google Fonts como mejora progresiva. Si no hay conexión, los fallbacks del sistema mantienen el documento plenamente legible; no se distribuyen binarios de fuentes dentro del proyecto.

Auditar una muestra visual (herramienta de mantenimiento, no necesaria para estudiar):

```bash
pip install -r requirements-design.txt
python -m playwright install chromium
python scripts/visual_audit.py docs/design-samples/architecture.html --out visual-tests/architecture
```

Los HTML de resumen/guía/repaso guardan también un fingerprint del design system. Si cambia el theme, pasan a `STALE` con `design-system-changed`; preguntas y simulacros no se regeneran por un cambio puramente visual.

### El profesor no redacta el resumen

Las transcripciones sirven internamente para extraer:

- significado;
- importancia;
- ejemplos;
- errores frecuentes;
- alcance o reglas cuando están realmente respaldados;
- evidencia/timestamps para auditoría.

Pero el redactor trabaja principalmente desde el conocimiento canónico ya destilado. No recibe la transcripción completa por defecto, evitando convertir el resumen en frases del profesor ligeramente limpiadas.

## 5. Handoffs portables

Las etapas se comunican mediante archivos en:

```text
materias/<materia>/.study/runs/<run-id>/
```

Para un resumen:

```text
01-input.json
02-plan.json
03-draft.md
04-humanized.md
05-review.json
06-final.md
09-rendered.html
10-integrity.json
```

Si el primer review falla:

```text
06-repair.md
07-review.json
08-final.md
09-rendered.html
10-integrity.json
```

Esto funciona como frontera de contexto tanto en Claude como en Codex. Un proveedor puede usar subagentes/contextos aislados como optimización, pero el pipeline **no depende** de ellos.

El scaffold y quality gate son determinísticos:

```bash
python scripts/pipeline_run.py start --course programacion-i --pipeline resumen --scope "Unidad 1"
python scripts/pipeline_run.py validate --run <run-dir>
python scripts/pipeline_run.py finish --run <run-dir>
```

Normalmente estas órdenes las ejecuta la skill, no vos.

## 6. Quality gate

El reviewer puntúa de 0 a 5:

- claridad;
- progresión;
- explicación real vs enumeración;
- ejemplos;
- señal/ruido;
- naturalidad;
- cobertura;
- soporte visual.

Además busca errores académicos. Para aprobar, fidelidad debe estar limpia y las dimensiones principales deben tener al menos 4/5.

La consigna del reviewer es **buscar razones para rechazar**, no defender el texto que acaba de producir otro paso. Después del render hay un segundo gate determinístico (`artifact_integrity.py`): no se publica nada si captions, imágenes, registro de figuras, `unit_id` o procedencia no cierran.

## 7. Humanizer

Existe una sola copia canónica:

```text
vendor/humanizer/SKILL.md
```

`sync_agent_assets.py` la instala de forma idéntica en Claude y Codex.

Humanizer puede mejorar ritmo, sintaxis, transiciones y naturalidad. No puede cambiar hechos, definiciones, fórmulas, código, fechas, alcance, condiciones ni niveles `confirmed/likely/unknown/excluded`.

Después de Humanizer siempre hay auditoría académica.

## 8. Reglas separadas por responsabilidad

```text
rules/
├── academic/
│   ├── source-truth.md
│   ├── uncertainty.md
│   └── assessments.md
├── ingestion/
│   ├── material-processing.md
│   ├── transcripts.md
│   ├── concept-graph.md
│   └── figures.md
├── pedagogy/
│   ├── learning-principles.md
│   ├── concept-ordering.md
│   └── examples.md
├── visual/
│   ├── study-document.md
│   ├── figures.md
│   └── active-reading.md
├── writing/
│   ├── student-prose.md
│   ├── summary.md
│   ├── guide.md
│   ├── review.md
│   └── explain.md
└── evaluation/
    ├── academic-fidelity.md
    ├── pedagogy-rubric.md
    └── quality-gates.md
```

Agregar reglas no es gratis. Una regla debe vivir en la responsabilidad correcta y sólo cargarse cuando sea necesaria.

---

# Lectura visual y figuras

## HTML, no Markdown crudo

`/resumen`, `/guia` y `/repaso` publican:

```text
resumenes/
├── unidad-1-resumen.html       ← abrir/leer
└── _source/
    └── unidad-1-resumen.md     ← fuente portable interna
```

Abrir el último HTML:

```bash
python study.py open programacion-i --type summary
```

La hoja de estilo usa una columna legible de ~42rem, cuerpo de ~19px, interlineado generoso, alto contraste y colores semánticos estables. No se usa subrayado para enfatizar; queda reservado para links.

## Figuras de PDFs

Soporte visual opcional:

```bash
python study.py figures preflight programacion-i
# si informa DISABLED:
python -m pip install -r requirements-visual.txt
python study.py figures scan programacion-i --write
```

El scanner sólo detecta páginas visualmente candidatas; **no decide qué imagen es importante académicamente**. Claude/Codex hace esa decisión dentro del pipeline usando los conceptos/fuentes del scope.

Para renderizar una página seleccionada:

```bash
python study.py figures render programacion-i \
  --file "oficiales/arquitectura.pdf" --page 12 --id jerarquia-memoria
```

El asset queda en `materias/<materia>/assets/figures/`. Las figuras derivadas se registran de forma segura con `python study.py figures register-derived ...`: reciben namespace `derived:`, `unit_id` estable y procedencia `based_on`, y el comando rechaza ids o assets que colisionen.

Al migrar una materia ya procesada desde V3.6.2, ejecutá una sola vez:

```bash
python study.py figures migrate programacion-i
```

Esto **no reprocesa PDFs ni transcripciones**; sólo normaliza metadatos legacy de figuras derivadas.

Regla: palabras + imágenes relevantes sí; imágenes decorativas no. La figura se pone al lado de su explicación y se indica qué relación conceptual mirar.

---

# Acciones

| Acción | Claude | Codex | Función |
|---|---|---|---|
| Procesar | `/procesar` | `$procesar` | ingesta y conocimiento |
| Aprender | `/aprender` | `$aprender` | primera comprensión |
| Estudiar | `/estudiar` | `$estudiar` | sesión adaptativa |
| Resumen | `/resumen` | `$resumen` | apuntes normales y claros |
| Guía | `/guia` | `$guia` | dossier exhaustivo pero pedagógico |
| Repaso | `/repaso` | `$repaso` | high-yield 5–10 min |
| Preguntas | `/preguntas` | `$preguntas` | active recall |
| Simulacro | `/simulacro` | `$simulacro` | examen realista |
| Explicar | `/explicar` | `$explicar` | explicación profunda |
| Auditar | `/auditar` | `$auditar` | verificación contra fuentes |
| Estado | `/estado` | `$estado` | progreso, evaluaciones y stale |

## Artefactos STALE

V3.7.2 usa `artifact_contract_version = 7`. Material pedagógico creado con contratos anteriores queda STALE automáticamente aunque las fuentes no hayan cambiado.

```bash
python study.py artifacts programacion-i
```

`/procesar` detecta los STALE pero no los regenera. La acción correspondiente los actualiza cuando realmente los necesitás.

---

# Migrar desde V3.0/V2.9

Copiá tu carpeta de materia completa:

```text
V3.0/materias/programacion-i/
        ↓
V3.7.2/materias/programacion-i/
```

No vuelvas a procesar las fuentes si no cambiaron. Ejecutá `python study.py figures migrate programacion-i` para normalizar metadatos de figuras legacy sin releer fuentes. Los artefactos visuales cuyo scope de figuras estaba mal pueden aparecer STALE y regenerarse normalmente.

Abrí una sesión nueva de Claude Code/Codex sobre la raíz V3.7.2 y probá:

```text
/resumen Programacion-I "Unidad 1"
```

El benchmark del proyecto sigue siendo simple: **el resultado V3 tiene que ser claramente mejor para estudiar que subir los mismos archivos a un modelo y pedir “resumime esto”.** La infraestructura adicional sólo se conserva si mejora ese resultado.
