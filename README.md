# University Study System V3.7.0

Workspace versionado de la release que estamos usando para iterar diseño, renderer e infraestructura del University Study System.

> Este repositorio es el **snapshot de trabajo curado**, no una copia completa del paquete local. El ZIP/local sigue siendo la distribución ejecutable con `study.py`, plantillas, tests, adapters y materias. Acá versionamos lo que estamos modificando y revisando activamente para no mezclarlo con datos académicos locales.

## Release actual

- `VERSION`: 3.7.0
- nuevo **Study MCP local por stdio** para Claude Code y Codex
- 12 tools curadas + 4 resources `study://...`
- `study_get_unit_context` agrega unidad, conceptos, figuras, restricciones académicas y progreso en una sola llamada
- escrituras MCP limitadas a operaciones seguras que delegan en el core determinístico
- sin tools V1 de borrado, reset, edición JSON arbitraria ni publicación libre
- fallback completo a `study.py`/scripts si MCP no está disponible
- diseño Claude integrado y estabilizado
- renderer HTML académico actual
- títulos específicos de callouts preservados dentro del cuerpo
- `unit_id` estable para scopes
- figuras derivadas con namespace `derived:` y procedencia obligatoria
- gate `10-integrity.json` antes de publicar
- CLI/contratos JSON robustos en UTF-8
- 79/79 tests de release pasando

## MCP V1

La configuración versionada está en `.mcp.json` (Claude Code) y `.codex/config.toml` (Codex). Ambas superficies arrancan el mismo adapter local:

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

Instalación en el paquete local completo:

```bash
python -m pip install -r requirements-mcp.txt
python study.py mcp preflight
```

El MCP es un adapter, no una nueva fuente de verdad. Ver `docs/mcp.md`.

## Archivos centrales versionados

```text
study_mcp/                  # adapter MCP local
requirements-mcp.txt
.mcp.json
.codex/config.toml
docs/mcp.md
design/                     # fuente visual canónica
assets/study-theme.css       # theme generado consumido por el renderer
scripts/render_study.py      # Markdown semántico -> HTML
scripts/figure_assets.py     # scan/render/registro/migración de figuras
scripts/unit_identity.py     # identidad estable de unidades
scripts/artifact_integrity.py# gate previo a publicación
scripts/pipeline_run.py      # runs/handoffs + 10-integrity.json
pipelines/                   # flujo semántico de los artefactos
contracts/handoffs.md
rules/ingestion/figures.md
```

## Diseño

La superficie de lectura es HTML estático/local con estética de manual universitario contemporáneo. La fuente visual canónica está en `design/`; `assets/study-theme.css` es el build que consume `scripts/render_study.py`.

Tipografía: Source Serif 4 + IBM Plex como mejora progresiva, con fallbacks locales. La prosa usa una medida aproximada de 68 caracteres, gutter académico para secciones/roles semánticos y ancho técnico separado para figuras, tablas y código.

## Principio

La infraestructura interna puede ser rigurosa y trazable; el material que recibe el estudiante debe sentirse como un buen apunte escrito por una persona: claro, didáctico, visualmente sobrio y sin exponer el aparato forense interno.
