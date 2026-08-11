# Unidades de la materia

Cada unidad académica declarada en `academico/academic.json` tiene un directorio
estable `unidades/<unit-id>/`. Ejecutá `python study.py units sync <materia>`
después de agregar o modificar unidades para crear o actualizar su estructura.

Dentro de cada unidad viven, sin mezclarse con las demás:

- `fuentes/oficiales/` y `fuentes/transcripciones/`;
- `conocimiento/concepts.json`, `conocimiento/topics.json` y `conocimiento/figures.json`;
- `progreso/progress.json`;
- `notas/`, `resumenes/`, `preguntas/` y `simulacros/`;
- `assets/figures/` y las ejecuciones de pipeline en `.study/runs/`.

`unidad.json` es un espejo navegable de la identidad de la unidad. La fuente de
verdad para nombres, temas y estado sigue siendo `academico/academic.json`.
