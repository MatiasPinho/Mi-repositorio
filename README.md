# University Study System V3.6.4

Estado actual del sistema universitario portable para Claude Code y Codex.

La superficie de lectura es HTML estático/local con diseño de manual universitario contemporáneo. El conocimiento académico se construye desde fuentes, se organiza en estado canónico y recién después pasa por planificación pedagógica, redacción, Humanizer, review e integridad determinística antes de publicar.

## Release actual

- `VERSION`: 3.6.4
- diseño Claude integrado y estabilizado
- `unit_id` estable para scopes
- figuras derivadas con namespace `derived:` y procedencia obligatoria
- migración de registros legacy sin reprocesar fuentes
- source figures con `asset: null` válidas hasta su extracción visual
- captions robustos
- gate `10-integrity.json` antes de publicar
- preflight de PyMuPDF
- 70 tests de release

## Flujo normal

```bash
python study.py
python study.py course add "Programación I"
python study.py figures migrate programacion-i
python study.py figures preflight programacion-i
python study.py validate programacion-i
```

En Claude Code:

```text
/procesar Programacion-I
/resumen Programacion-I "Unidad 1"
```

En Codex se usan las acciones equivalentes con `$`.

## Diseño

La fuente visual canónica está en `design/`. `assets/study-theme.css` es el build consumido por `scripts/render_study.py`.

Tipografía: Source Serif 4 + IBM Plex como mejora progresiva, con fallbacks locales. Prosa alrededor de 68 caracteres, gutter académico para secciones/roles semánticos y ancho técnico separado para figuras, tablas y código.

## Principio

La infraestructura interna puede ser rigurosa y trazable; el material que recibe el estudiante debe sentirse como un buen apunte escrito por una persona: claro, didáctico, visualmente sobrio y sin exponer el aparato forense interno.
