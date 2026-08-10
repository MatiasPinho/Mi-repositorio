# University Study System V3.7.2

Sistema local para estudiar materias universitarias con **Claude Code o Codex** sobre el mismo núcleo metodológico, con conocimiento canónico trazable, pipelines compartidos, MCP local opcional y salida visual pensada para lectura real.

La infraestructura puede ser estricta y auditable; el material que recibe el estudiante debe seguir siendo **normal, humano, claro y didáctico**.

> Mapa técnico y protocolos de mantenimiento: [`docs/README.md`](docs/README.md)

## Principio central

```text
                         FUENTES
                            │
                            ▼
                   EVIDENCIA LOCALIZADA
              hashes + páginas + timestamps
                            │
                            ▼
                  CONOCIMIENTO CANÓNICO
           academic + concepts + claims + evidence
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
                       mismo contrato
```

Claude y Codex son **motores de ejecución**. La metodología, las reglas, los contratos, la policy académica y el estado canónico viven fuera del proveedor.

---

# Inicio rápido

En Windows podés abrir `INICIAR-STUDY.bat`, o desde terminal:

```bash
python study.py
```

Activar el MCP local, opcional pero recomendado:

```bash
python -m pip install -r requirements-mcp.txt
python study.py mcp preflight
```

La release incluye `.mcp.json` y `.codex/config.toml`. Ambos arrancan el mismo adapter con `python study.py mcp serve`; el core sigue funcionando por CLI si MCP no está disponible.

Crear una materia:

```bash
python study.py course add "Programación I"
```

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

Resetear una materia para reprocesarla desde cero, conservando fuentes e identidad básica:

```bash
python study.py course reset programacion-i
```

El reset elimina conocimiento derivado, progreso, artefactos, figuras generadas y `.study/`; las fuentes vuelven a aparecer como nuevas para `/procesar`. Requiere confirmar exactamente el slug salvo que se use `--yes`.

---

# Arquitectura

## 1. Core portable

```text
core/                    router mínimo
rules/                   reglas por responsabilidad
pipelines/               orden de ejecución
contracts/               contratos entre etapas
vendor/humanizer/        Humanizer canónico
config/actions.json      definición de acciones
config/*_policy.json     policies determinísticas versionadas
```

`.claude/skills/` y `.agents/skills/` contienen adaptadores finos generados, no metodología duplicada.

Regenerar y verificar adapters:

```bash
python scripts/sync_agent_assets.py generate
python scripts/sync_agent_assets.py verify
```

## 2. Progressive disclosure

Cada acción carga sólo las reglas necesarias. `/resumen` carga pedagogía, escritura y evaluación; `/procesar` carga fuentes, ingesta y auditoría, pero no Humanizer ni reglas de prosa.

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

El MCP no reemplaza el core ni los pipelines. Expone herramientas gruesas y acotadas; no ofrece borrado libre, reset remoto, JSON arbitrario ni publicación de archivos sin contrato. Si MCP no está conectado, las mismas operaciones siguen disponibles por `study.py` y scripts.

Ver [`docs/mcp.md`](docs/mcp.md).

---

# `/procesar`: ingesta, no generación

`/procesar` no genera resumen, guía, repaso, preguntas ni simulacro. Su trabajo es convertir fuentes nuevas o modificadas en conocimiento canónico trazable.

Flujo vigente:

```text
FUENTES NUEVAS / MODIFICADAS
        ↓
scan + SHA-256
        ↓
PDF health / visual preflight
        ↓
claim candidate extraction
        ↓
claim_candidates
(página/timestamp + excerpt)
        ↓
REVISIÓN SEMÁNTICA
   ↙                ↘
reject              accept
                      ↓
               claims canónicos
                      ↓
          semantic contradiction resolver
              ┌───────┴────────┐
              │                │
       academic_truth   assessment_expectation
              └───────┬────────┘
                      ↓
academic.json + concepts.json + contexto.md
                      ↓
auditoría + tracker + hashes + estado STALE
```

## Candidatos no son verdad

`scripts/claim_candidates.py` detecta señales de alto valor —por ejemplo alcance de examen, notas mínimas, definiciones explícitas y señales de cambio— y las registra bajo:

```text
academico/academic.json -> claim_candidates
```

Cada candidato conserva evidencia localizable como:

```text
transcripciones/clase-08.srt#00:47:21
oficiales/programa.pdf#page=3
```

Un candidato puede ser `semantic_ready` y aun así **no ser verdadero**. Sólo la revisión semántica de `/procesar` puede aceptarlo o rechazarlo y convertirlo en un claim canónico.

Una transcripción cruda conserva su clasificación `teacher_transcript`; no se transforma automáticamente en `teacher_explicit` y nunca puede declarar por sí sola que otra fuente quedó reemplazada.

Ver [`docs/claim-extraction.md`](docs/claim-extraction.md).

## Dos vistas cuando las fuentes chocan

El resolver semántico separa dos preguntas:

- `academic_truth`: qué valor está mejor respaldado como conocimiento académico;
- `assessment_expectation`: qué valor está mejor respaldado como lo que la cátedra espera en una evaluación.

Ejemplo:

```text
bibliografía fuerte  → A
profesor confirmado  → B

academic_truth         = A
assessment_expectation = B
status                 = split-view
```

Si la evidencia no permite resolver con suficiente separación de autoridad, el estado queda `unresolved`. El sistema no elige silenciosamente.

Ver [`docs/semantic-contradictions.md`](docs/semantic-contradictions.md).

---

# Pipeline de artefactos

## `/resumen`, `/guia` y `/repaso`

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
        ↓
8. INTEGRITY GATE
```

No hay loops infinitos: máximo dos reviews.

El Markdown es la fuente portable entre Claude y Codex. **El HTML es el artefacto normal de lectura.** Layout, tipografía, callouts, impresión y estilos provienen de `scripts/render_study.py` y `assets/study-theme.css`, no de improvisación del modelo.

## Quality gate versionado

El reviewer genera scores, fidelity checks, claim checks e issues estructurados. La aceptación final no queda librada al mismo modelo: `pipeline_run.review_gate()` delega en `config/academic_eval_policy.json`.

La policy exige, entre otras cosas:

- score mínimo en dimensiones principales;
- fidelity checks completos;
- claims representativos respaldados;
- ausencia de `academic_issues`, `pedagogy_issues`, `visual_issues` y `contradiction_issues`;
- `pass: true`.

Después del render existe un segundo gate determinístico de integridad para captions, imágenes, `unit_id`, procedencia y registros de figuras.

Ver [`docs/academic-eval.md`](docs/academic-eval.md).

## Humanizer

Existe una sola fuente canónica:

```text
vendor/humanizer/SKILL.md
```

Puede mejorar ritmo, sintaxis, transiciones y naturalidad. No puede cambiar hechos, definiciones, fórmulas, código, fechas, alcance, condiciones ni nivel de certeza. Después de Humanizer siempre hay revisión académica.

---

# Stress testing y CI

El proyecto mantiene benchmarks congelados para convertir fallos reales en regresiones reproducibles sin subir material privado.

## Stressed Materials

Cubre Unicode, renombres, contenido del mismo tamaño con hash distinto, duplicados, archivos vacíos, cambios sólo de `mtime`, CP1252, UTF-16 y VTT malformado.

```bash
python scripts/stressed_materials.py benchmark
```

Ver [`docs/stressed-materials.md`](docs/stressed-materials.md).

## PDF Stress

Cubre capa de texto, image-only/likely scanned, rotación, páginas vacías, vectores/tablas, PDFs corruptos, cifrados, Unicode y lotes mixtos. No hace OCR.

```bash
python scripts/pdf_stress.py benchmark
```

Ver [`docs/pdf-stress.md`](docs/pdf-stress.md).

## Semantic Contradictions

Congela reglas de autoridad, `split-view`, conflictos no resueltos y supersession autorizada.

```bash
python scripts/semantic_claims.py benchmark
```

## Claim Extraction

Congela qué frases generan candidatos, cuáles quedan ambiguas y cuáles no deben convertirse en claims.

```bash
python scripts/claim_candidates.py benchmark
```

## Academic Evaluation

Congela casos aceptados/rechazados por la policy académica.

```bash
python scripts/academic_eval.py benchmark
```

## Release suite

```bash
python tests/run_release_tests.py
```

GitHub Actions ejecuta los benchmarks y la release suite en **Ubuntu y Windows con Python 3.11**. Una regresión nueva debe reducirse a un fixture sintético, demostrar el fallo y quedar protegida por CI.

---

# Design system y lectura visual

El theme aprobado es un **contemporary technical manual**: columna de lectura estable, gutter semántico, figuras/tablas/código con ancho adicional y roles visuales consistentes.

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

Regenerar theme:

```bash
python scripts/build_design.py
```

Skills de diseño:

```text
Claude: /study-design
Codex:  $study-design

Claude: /study-design-reviewer
Codex:  $study-design-reviewer
```

No se cargan durante un resumen normal. El escritor usa roles semánticos como `DEFINITION`, `EXAMPLE`, `WARNING`, `CONNECTION` o `RECALL`, nunca colores o márgenes.

Los HTML guardan fingerprint del design system. Si cambia el theme, resumen/guía/repaso pueden pasar a `STALE` con `design-system-changed`; preguntas y simulacros no se invalidan por cambios puramente visuales.

## Figuras de PDFs

```bash
python study.py figures preflight programacion-i
# si informa DISABLED:
python -m pip install -r requirements-visual.txt
python study.py figures scan programacion-i --write
```

El scanner encuentra páginas visualmente candidatas; no decide relevancia académica. Una página seleccionada puede renderizarse con:

```bash
python study.py figures render programacion-i \
  --file "oficiales/arquitectura.pdf" --page 12 --id jerarquia-memoria
```

Las figuras derivadas usan namespace `derived:`, `unit_id` estable y procedencia `based_on`.

---

# Reglas y responsabilidades

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
├── visual/
├── writing/
└── evaluation/
```

Agregar reglas no es gratis. Cada regla debe vivir en la responsabilidad correcta y cargarse sólo cuando la acción la necesita.

---

# Acciones

| Acción | Claude | Codex | Función |
|---|---|---|---|
| Procesar | `/procesar` | `$procesar` | ingesta, evidencia y conocimiento canónico |
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

---

# Artefactos STALE

V3.7.2 usa `artifact_contract_version = 7`. Material pedagógico creado con contratos anteriores queda STALE automáticamente aunque las fuentes no hayan cambiado.

```bash
python study.py artifacts programacion-i
```

`/procesar` detecta artefactos STALE pero no los regenera. La acción correspondiente los actualiza cuando realmente se necesitan.

---

# Migración

Para una materia de una versión anterior, copiá la carpeta completa bajo `materias/`. No reproceses fuentes sólo por migrar si no cambiaron.

Para normalizar metadatos legacy de figuras derivadas:

```bash
python study.py figures migrate programacion-i
```

Esto no relee PDFs ni transcripciones.

Abrí una sesión nueva de Claude Code/Codex en la raíz y probá una acción normal:

```text
/resumen Programacion-I "Unidad 1"
```

---

# Documentación técnica

El índice canónico está en [`docs/README.md`](docs/README.md). Ahí se indica qué documento modificar cuando cambia un contrato de ingesta, PDF, claims, contradicciones, evaluación o MCP.

El criterio del proyecto sigue siendo simple: **la infraestructura sólo se conserva si mejora de forma comprobable la calidad, fidelidad o robustez del material de estudio frente a subir los mismos archivos y pedir “resumime esto”.**
