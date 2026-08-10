# Unit-first course layout (V4)

V4 uses the academic unit as the storage and execution boundary. The goal is
that a human or an agent can resolve `Unidad 1`, `U1` or `unidad-1` once and
then read a complete, isolated context without filtering mixed course files.

## Canonical tree

```text
materias/<course>/
├── academico/academic.json          # identity, unit catalog, assessments, rules
├── contexto.md                      # course-wide context
├── fuentes/                         # only genuinely cross-unit sources
├── unidades/
│   └── <unit-id>/
│       ├── unidad.json              # navigable mirror; academic.json is authoritative
│       ├── fuentes/
│       │   ├── oficiales/
│       │   └── transcripciones/
│       ├── conocimiento/
│       │   ├── concepts.json
│       │   └── figures.json
│       ├── progreso/progress.json
│       ├── notas/
│       ├── resumenes/_source/
│       ├── preguntas/
│       ├── simulacros/
│       ├── assets/figures/
│       └── .study/runs/
└── .study/                          # course indexes/manifests and migration audit
```

## Invariants

1. Directory names use the stable id derived from `academic.json`, for example
   `unidad-1`; display labels never determine filesystem paths by fuzzy match.
2. Every concept and figure stored in a unit resolves back to that same
   `unit_id`. Progress is placed with its owning concept.
3. A source used by one unit lives in that unit. A source shared by several
   units stays in the course-level `fuentes/` tree and is referenced, not
   duplicated.
4. Summaries, guides, reviews, question banks, mock assessments, figures and
   pipeline runs are written inside their unit.
5. Cross-unit prerequisites may be loaded explicitly into a scoped read. They
   do not move into, or become owned by, the requesting unit.
6. Course identity, evaluations and academic rules remain global but reference
   stable unit ids and course-relative evidence paths.
7. Root V3 knowledge/progress/artifact directories are compatibility inputs,
   never a second source of truth after a V4 layout marker exists.

## Administration

```bash
python study.py units list <course>
python study.py units sync <course>
python study.py materials scan <course> --unit unidad-1
python study.py status <course> --unit unidad-1
python study.py validate <course>
```

`units sync` is idempotent: it creates missing unit directories and empty
registries, updates `unidad.json`, and reports directories no longer declared
in `academic.json` without deleting them. If it detects non-empty V3 root
registries/artifacts, it stops and requires `units migrate` so no content can be
hidden behind a new layout marker.

## V3 migration

```bash
python study.py units migrate <course>          # dry-run
python study.py units migrate <course> --apply  # apply validated plan
```

The migration partitions registries by stable `unit_id`, maps progress through
its concept, classifies sources by references, moves scoped artifacts/assets,
rewrites academic evidence paths, and updates the artifact manifest. It stops
before writing if any record, artifact or visual asset has no resolvable unit.

Every legacy pedagogical root and every moved unit source has a recovery copy
under `.study/legacy-layout-v3/`. This directory is excluded from normal scans,
so recovery data cannot be mistaken for live canonical content.

## Compatibility boundary

`scripts/course_layout.py` is the only path authority. CLI, MCP and pipelines
use its merged read view for course status and its scoped paths for writes. A
legacy matter without a V4 marker still reads its root registries; once migrated,
writes without a resolvable unit fail instead of falling back to the root.
