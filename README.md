# University Study System V3.6.5

Workspace versionado de la release que estamos usando para iterar diseño, renderer e infraestructura de publicación del University Study System.

> Este repositorio es el **snapshot de trabajo curado**, no una copia completa del paquete local. El ZIP/local sigue siendo la distribución ejecutable con `study.py`, plantillas, tests, adapters y materias. Acá versionamos lo que estamos modificando y revisando activamente para no mezclarlo con datos académicos locales.

## Release actual

- `VERSION`: 3.6.5
- diseño Claude integrado y estabilizado
- renderer HTML académico actual
- títulos específicos de `WARNING`, `EXAM`, `RECALL`, `EXAMPLE` y demás callouts preservados dentro del cuerpo, sin reemplazar la categoría del gutter
- `unit_id` estable para scopes
- figuras derivadas con namespace `derived:` y procedencia obligatoria
- migración de registros legacy sin reprocesar fuentes
- source figures con `asset: null` válidas hasta su extracción visual
- captions robustos
- gate `10-integrity.json` antes de publicar
- preflight de PyMuPDF
- contratos JSON endurecidos para que warnings de dependencias no contaminen `stdout`
- `/procesar` consume explícitamente las variantes `--json` de scans/preflight estructurados
- CLI local V3.6.5 fuerza UTF-8 en Windows y subprocesses determinísticos
- 73/73 tests de release pasando

## Archivos centrales versionados

```text
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
