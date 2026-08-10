# University Study System V3.7.2

Workspace versionado de la release que estamos usando para iterar infraestructura, MCP, pipelines de generación y control académico del University Study System.

> Este repositorio es el **snapshot de trabajo curado**, no una copia completa del paquete local. El ZIP/local sigue siendo la distribución ejecutable con `study.py`, plantillas, tests completos, adapters y materias. Acá versionamos lo que estamos modificando y revisando activamente sin subir datos académicos privados.

## Release actual

- `VERSION`: 3.7.2
- Study MCP local por `stdio` para Claude Code y Codex
- 12 tools curadas + 4 resources `study://...`
- MCP V3.7.1 llama al core Python **in-process**, sin subprocesses Python para las tools expuestas
- test MCP real por `stdio` con cliente, negociación de sesión, listado de tools y timeout; verificado en Windows
- `study_get_unit_context` agrega unidad, conceptos, figuras, restricciones académicas y progreso en una llamada
- reviewer académico V3.7.2 endurecido con `academic_fidelity`, `fidelity_checks` y `claim_checks`
- segunda pasada de consistencia interna para detectar drift de taxonomías, condiciones, certeza y relaciones dentro del propio resumen
- los quality gates fallan ante claims no soportados o issues concretos aunque el reviewer declare `pass: true`
- `artifact_contract_version = 7`: artefactos pedagógicos anteriores quedan stale sin reprocesar fuentes
- renderer HTML académico y theme determinístico reproducible
- `unit_id` estable para scopes y figuras derivadas con namespace `derived:`
- gate `10-integrity.json` antes de publicar

## MCP local

La configuración versionada está en `.mcp.json` (Claude Code) y `.codex/config.toml` (Codex). Ambas superficies arrancan el mismo adapter local:

```text
Claude Code / Codex
        │
        │ MCP stdio
        ▼
   study_mcp/
        │
        │ llamadas in-process
        ▼
  core Python determinístico
        │
        ▼
 estado canónico local
```

Instalación en el paquete local completo:

```bash
python -m pip install -r requirements-mcp.txt
python study.py mcp preflight
```

El MCP es una interfaz sobre el core, no una fuente de verdad nueva. Ver `docs/mcp.md`.

## Pipeline de resumen

```text
fuentes
  ↓
conocimiento canónico
  ↓
plan pedagógico
  ↓
draft
  ↓
Humanizer
  ↓
review académico adversarial
  ├─ candidato ↔ canonical
  └─ candidato ↔ candidato
  ↓
integrity gate
  ↓
HTML publicado
```

El reviewer debe verificar definiciones, taxonomías y conteos, condiciones y límites, relaciones/orden, certeza y conflictos, reglas de evaluación, consistencia interna y separación entre ejemplos ilustrativos y reglas oficiales.

## Archivos centrales versionados

```text
study_mcp/                   # adapter MCP local
requirements-mcp.txt
.mcp.json
.codex/config.toml
docs/mcp.md
scripts/pipeline_run.py       # runs/handoffs + review gate
scripts/artifact_state.py     # fingerprints + artifact_contract_version
contracts/handoffs.md         # contrato estructurado del reviewer
pipelines/resumen.md          # pipeline pedagógico actual
rules/evaluation/             # fidelidad y quality gates
evals/summary-rubric.json     # rúbrica machine-readable
design/                       # fuente visual canónica
assets/study-theme.css        # theme generado consumido por renderer
```

## Diseño

La superficie de lectura es HTML estático/local con estética de manual universitario contemporáneo. La fuente visual canónica está en `design/`; `assets/study-theme.css` es el build que consume `scripts/render_study.py`.

Tipografía: Source Serif 4 + IBM Plex como mejora progresiva, con fallbacks locales. La prosa usa una medida aproximada de 68 caracteres, gutter académico para secciones/roles semánticos y ancho técnico separado para figuras, tablas y código.

## Principio

La infraestructura interna puede ser rigurosa y trazable; el material que recibe el estudiante debe sentirse como un buen apunte escrito por una persona: claro, didáctico, visualmente sobrio y sin exponer el aparato forense interno.
