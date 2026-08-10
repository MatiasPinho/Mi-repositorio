# University Study System V3.7.2

Sistema local para estudiar materias universitarias con **Claude Code o Codex** sobre el mismo núcleo metodológico, con conocimiento canónico trazable, pipelines compartidos, MCP local y salida visual pensada para lectura real.

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

Claude y Codex son **motores de ejecución**. La metodología, las reglas, los contratos, las policies y el estado canónico viven fuera del proveedor.

---

# Instalación e inicio

## Windows: instalar una vez

Después de clonar/copiar el proyecto, ejecutá:

```text
INSTALAR-STUDY.bat
```

Ese instalador prepara el entorno completo:

- Python packages de MCP;
- PyMuPDF para PDFs y figuras;
- Pillow;
- Playwright;
- Chromium de Playwright;
- verificación de dependencias y lanzamiento real del navegador headless.

Después, para usar el sistema normalmente:

```text
INICIAR-STUDY.bat
```

`INICIAR-STUDY.bat` hace un preflight antes de abrir el menú. Si falta una dependencia o Chromium no puede arrancar, se detiene inmediatamente y pide volver a ejecutar `INSTALAR-STUDY.bat`; no espera hasta el final de un `/resumen` para descubrir el problema.

## Instalación manual / otros sistemas

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m pip check
python scripts/setup_env.py check
```

`requirements.txt` es el entrypoint del entorno completo e incluye `requirements-mcp.txt`, `requirements-visual.txt` y `requirements-design.txt`.

Preflight en JSON:

```bash
python scripts/setup_env.py check --json
```

Ver detalles en [`docs/setup.md`](docs/setup.md).

## Inicio por terminal

```bash
python study.py
```

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

---

# Arquitectura

## Core portable

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

```bash
python scripts/sync_agent_assets.py generate
python scripts/sync_agent_assets.py verify
```

## Progressive disclosure

Cada acción carga sólo las reglas necesarias. `/resumen` carga pedagogía, escritura y evaluación; `/procesar` carga fuentes, ingesta y auditoría, pero no Humanizer ni reglas de prosa.

## MCP local

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

El MCP expone herramientas acotadas sobre el mismo core. No ofrece borrado libre, reset remoto, JSON arbitrario ni publicación de archivos sin contrato. Ver [`docs/mcp.md`](docs/mcp.md).

---

# `/procesar`: ingesta, no generación

`/procesar` no genera resumen, guía, repaso, preguntas ni simulacro. Convierte fuentes nuevas o modificadas en conocimiento canónico trazable.

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

`scripts/claim_candidates.py` detecta señales de alto valor y las registra en `academico/academic.json -> claim_candidates` con evidencia localizable. Un candidato puede ser `semantic_ready` y aun así **no ser verdadero**: sólo la revisión semántica puede aceptarlo y convertirlo en claim canónico.

Una transcripción cruda conserva `teacher_transcript`; no se promociona automáticamente a `teacher_explicit` ni puede declarar por sí sola `supersedes`.

Ver [`docs/claim-extraction.md`](docs/claim-extraction.md).

## Dos vistas cuando las fuentes chocan

- `academic_truth`: qué valor está mejor respaldado como conocimiento académico.
- `assessment_expectation`: qué valor está mejor respaldado como lo que la cátedra espera.

```text
bibliografía fuerte  → A
profesor confirmado  → B

academic_truth         = A
assessment_expectation = B
status                 = split-view
```

Si la evidencia no permite resolver con suficiente autoridad, queda `unresolved`; el sistema no elige silenciosamente. Ver [`docs/semantic-contradictions.md`](docs/semantic-contradictions.md).

---

# Pipeline de `/resumen`, `/guia` y `/repaso`

```text
CONOCIMIENTO CANÓNICO + FIGURAS
        ↓
PLAN PEDAGÓGICO
        ↓
BORRADOR SEMÁNTICO
        ↓
HUMANIZER (sólo prosa)
        ↓
REVIEW ACADÉMICO + PEDAGÓGICO + VISUAL
        ↓
PASS ───────────────→ FINAL MD
 │
FAIL
 ↓
UNA REPARACIÓN + SEGUNDO REVIEW
        ↓
RENDER DETERMINÍSTICO
        ↓
INTEGRITY GATE
        ↓
CHROMIUM VISUAL AUDIT
 desktop + tablet + mobile + print
        ↓
INSPECCIÓN DE CAPTURAS
        ↓
PUBLICACIÓN HTML
```

No hay loops infinitos: máximo dos reviews académicos.

El Markdown es la fuente portable entre Claude y Codex. **El HTML es el artefacto normal de lectura.** Layout, tipografía, callouts, impresión y estilos provienen de `scripts/render_study.py` y `assets/study-theme.css`.

## Quality gate académico

`pipeline_run.review_gate()` delega la aceptación en `config/academic_eval_policy.json`. Exige scores, fidelity checks, claims respaldados y ausencia de `academic_issues`, `pedagogy_issues`, `visual_issues` y `contradiction_issues`.

Ver [`docs/academic-eval.md`](docs/academic-eval.md).

## Integrity gate vs browser visual gate

Son controles distintos:

- **integrity**: rutas, alt text, captions, `unit_id`, procedencia y registro de figuras;
- **browser visual**: Chromium renderiza el HTML real y `visual_audit.py` verifica overflow, tipografía, line-height, contraste y vistas desktop/tablet/mobile/print.

`pipeline_run.py finish` exige `visual-audit/audit.json -> ok: true` y capturas desktop/mobile. Una validación de rutas no puede presentarse como revisión visual completa.

Si Playwright o Chromium faltan, es un error de instalación: el pipeline no debe publicar ni afirmar visual PASS.

---

# Humanizer

Fuente canónica:

```text
vendor/humanizer/SKILL.md
```

Puede mejorar ritmo, sintaxis, transiciones y naturalidad. No puede cambiar hechos, definiciones, fórmulas, código, fechas, alcance, condiciones ni nivel de certeza. Después de Humanizer siempre hay revisión académica.

---

# Stress testing y CI

CI instala el mismo entorno completo que una máquina de uso:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/setup_env.py check --json
```

Después ejecuta los benchmarks congelados:

```bash
python scripts/stressed_materials.py benchmark
python scripts/pdf_stress.py benchmark
python scripts/semantic_claims.py benchmark
python scripts/claim_candidates.py benchmark
python scripts/academic_eval.py benchmark
```

Release suite:

```bash
python tests/run_release_tests.py
```

La suite incluye un smoke test real de Chromium que renderiza y audita un documento sintético. GitHub Actions valida **Windows y Ubuntu con Python 3.11**.

Documentación:

- [`docs/stressed-materials.md`](docs/stressed-materials.md)
- [`docs/pdf-stress.md`](docs/pdf-stress.md)
- [`docs/semantic-contradictions.md`](docs/semantic-contradictions.md)
- [`docs/claim-extraction.md`](docs/claim-extraction.md)
- [`docs/academic-eval.md`](docs/academic-eval.md)

---

# Design system y lectura visual

El theme aprobado es un **contemporary technical manual**: columna de lectura estable, gutter semántico, figuras/tablas/código con ancho adicional y roles visuales consistentes.

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

El escritor usa roles semánticos como `DEFINITION`, `EXAMPLE`, `WARNING`, `CONNECTION` o `RECALL`, nunca colores o márgenes.

## Figuras de PDFs

Con el setup completo, PyMuPDF ya está instalado:

```bash
python study.py figures preflight programacion-i
python study.py figures scan programacion-i --write
```

Renderizar una página seleccionada:

```bash
python study.py figures render programacion-i \
  --file "oficiales/arquitectura.pdf" --page 12 --id jerarquia-memoria
```

Las figuras derivadas usan namespace `derived:`, `unit_id` estable y procedencia `based_on`.

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

`/procesar` detecta artefactos STALE pero no los regenera.

---

# Migración

Copiá la carpeta de la materia bajo `materias/`. Si las fuentes no cambiaron, no hace falta reprocesarlas sólo por migrar.

```bash
python study.py figures migrate programacion-i
```

Esto normaliza metadatos legacy de figuras sin releer PDFs ni transcripciones.

---

# Documentación técnica

El índice canónico está en [`docs/README.md`](docs/README.md). Ahí se indica qué documento actualizar cuando cambia un contrato de instalación, ingesta, PDF, claims, contradicciones, evaluación, visuales o MCP.

El criterio del proyecto sigue siendo simple: **la infraestructura sólo se conserva si mejora de forma comprobable la calidad, fidelidad o robustez del material de estudio frente a subir los mismos archivos y pedir “resumime esto”.**
