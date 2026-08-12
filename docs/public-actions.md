# Public study actions

University Study exposes **nine** student-facing actions. The public surface is intentionally small; different commands should represent genuinely different jobs, not minor variations of the same workflow.

| Action | Purpose |
|---|---|
| `procesar` | ingest new/changed unit sources into canonical knowledge |
| `aprender` | learn either one observed topic or one canonical concept interactively |
| `estudiar` | start an adaptive study session from progress, due reviews and assessment context |
| `resumen` | generate the unit's main long-form study document, standard or explicitly detailed |
| `repaso` | generate a compact 5–10 minute high-yield review |
| `preguntas` | conversational active recall with meaningful mastery updates |
| `quiz` | persistent offline multiple-choice HTML with Practice/Exam modes |
| `simulacro` | assessment-scoped mock exam for one registered evaluation and unit |
| `estado` | inspect mastery, untested concepts, due reviews and CURRENT/STALE artifacts |

## Consolidated legacy intents

### `guia` → `resumen detallado`
There is no separate public guide action. Requests for a guide, dossier or more exhaustive explanation route to `resumen` with `depth=detailed`. Academic scope and quality gates remain identical; only explanatory depth changes.

### `explicar` → `aprender`
There is no separate public concept-explanation action. `aprender` resolves either an observed topic or a canonical concept. Exact target collisions require `tema:<target>` or `concepto:<target>`; fuzzy selection is forbidden.

### `auditar` → internal maintenance
`pipelines/auditar.md` remains available to developers/maintainers for explicit source-vs-canonical audits, but it is not exposed as a Claude/Codex study command. Normal study actions already carry their own validation/reviewer gates.

## Product rule

Adding a new public action requires a distinct user job that cannot be expressed cleanly by an existing action plus an explicit mode/argument. Convenience aliases, implementation details and maintenance operations should not expand the public command list.
