# Temas observados por unidad

V4 separa tres capas que antes podían confundirse:

```text
academic.json -> units[].topics   temario declarado/oficial
unidades/<unit-id>/conocimiento/topics.json   temas observados
unidades/<unit-id>/conocimiento/concepts.json conceptos canónicos
```

El temario declarado se transcribe desde el programa y no se modifica al
procesar apuntes, PDFs o clases. Los temas observados son agrupaciones
semánticas reconstruidas desde el material efectivamente procesado.

## Contrato V1

```json
{
  "version": 1,
  "unit_id": "unidad-1",
  "topics": {
    "operadores": {
      "id": "operadores",
      "unit_id": "unidad-1",
      "name": "Operadores",
      "aliases": [],
      "concept_ids": ["suma", "precedencia"],
      "declared_matches": ["Expresiones"],
      "evidence": [
        {"file": "unidades/unidad-1/fuentes/oficiales/clase.pdf", "page": 3}
      ]
    }
  },
  "unassigned_concept_ids": []
}
```

Invariantes:

1. La clave de `topics` coincide con `topic.id` y el id se conserva entre
   reprocesamientos semánticamente equivalentes.
2. Cada `concept_id` existe en el `concepts.json` de esa misma unidad.
3. Un concepto aparece en un único tema principal o en
   `unassigned_concept_ids`, nunca en ambos ni implícitamente en ninguno.
4. `declared_matches` sólo contiene strings exactos del `units[].topics` de la
   unidad. La reconciliación normaliza mayúsculas/acentos hacia el valor oficial
   pero nunca escribe `academic.json`.
5. `evidence` justifica la agrupación. Un encabezado visual puede aportar
   evidencia, pero por sí solo no crea un tema.
6. `topics.json` no contiene mastery, dificultad, peso de examen, grafos ni
   relaciones entre temas.

## Reconciliación estable

`/procesar` actualiza primero conceptos y después presenta propuestas
semánticas al reconciliador:

```bash
python scripts/venv_exec.py study.py topics reconcile <course> \
  --unit unidad-1 --input proposal.json --write
python scripts/venv_exec.py study.py topics validate <course> --unit unidad-1
```

El reconciliador reutiliza un id existente cuando la propuesta usa ese id o
cuando hay una única coincidencia por `name`/`aliases`. Si el nombre preferido
cambia, el nombre anterior se conserva como alias. Una coincidencia ambigua se
rechaza; la capa semántica debe indicar explícitamente el id correcto.

Las propuestas son upserts. Los conceptos asignados se retiran de su tema
anterior, y los incluidos en `unassigned_concept_ids` quedan explícitamente sin
tema. Todo concepto nuevo que no haya sido considerado aparece automáticamente
como unassigned, de manera visible y validable.

## Progreso derivado

```bash
python scripts/venv_exec.py study.py topics progress <course> --unit unidad-1
```

El resultado calcula `tested_concept_count`, `tested_coverage` y
`average_mastery` desde `progress.json`. Es una vista de consulta: nunca duplica
esos valores dentro de `topics.json`.

## Sync y migración

`study.py units sync` crea el archivo faltante en materias V4 existentes. Si la
unidad ya tiene conceptos, los registra como unassigned sin modificar
`concepts.json`.

`study.py units migrate` reconoce un `conocimiento/topics.json` V3 opcional, lo
particiona por `unit_id` (o por la unidad inequívoca de sus conceptos), conserva
aliases/evidencia/asignaciones y archiva el original bajo
`.study/legacy-layout-v3/`. Si no existía catálogo, los conceptos migrados
quedan explícitamente unassigned.
