# University Study V4 — Portable Core Router

This directory is the **single methodological source of truth** for Claude Code and Codex.
Provider wrappers must stay thin. They route an action to a pipeline; they do not duplicate methodology.

## Core principle

Optimize for **understanding, retention and exam performance** while preserving academic truth.
The system has two intentionally different faces:

- **Internal academic layer:** evidence-heavy, traceable, explicit about uncertainty and contradictions.
- **Student-facing layer:** natural, clear, pedagogically ordered and visually designed for learning, with evidence mostly invisible unless it helps learning or is requested. Markdown is semantic source; rendered HTML is the normal reading surface.

Never expose internal evidence merely to prove that the agent read it.

## Load only what the current pipeline requires

Do not read every rule file for every task. Follow the pipeline's `READ` section and load only those files plus the canonical course state it names.

Shared pipeline contracts are also opt-in: load them only when the owning pipeline names them. `pipelines/_shared/semantic-document-lifecycle.md` currently owns the common staged review/render/publication lifecycle for `resumen` and `repaso`; it is orchestration infrastructure, not a public action and not a reason to load unrelated pipeline rules.

### Academic truth
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/academic/assessments.md`

### Ingestion
- `rules/ingestion/material-processing.md`
- `rules/ingestion/transcripts.md`
- `rules/ingestion/concept-graph.md`
- `rules/ingestion/topics.md`

### Pedagogy
- `rules/pedagogy/learning-principles.md`
- `rules/pedagogy/concept-ordering.md`
- `rules/pedagogy/examples.md`

### Visual learning
- `rules/visual/study-document.md`
- `rules/visual/figures.md`
- `rules/visual/active-reading.md`

### Writing
- `rules/writing/student-prose.md`
- artifact-specific writing rules under `rules/writing/`
- canonical Humanizer under `vendor/humanizer/SKILL.md`

### Evaluation
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/pedagogy-rubric.md`
- `rules/evaluation/quality-gates.md`
- `rules/evaluation/multiple-choice.md`

## Deterministic work
Use `study.py` and scripts for directory creation, hashes, stale status, due review, assessment listings, run manifests and structural validation. Do not spend model reasoning on deterministic administration.

## MCP fast path
When the local `university-study` MCP server is connected, prefer its coarse-grained read tools (`study_get_course_context`, `study_get_unit_context`, `study_list_units`, `study_list_artifacts`, etc.) instead of reopening and filtering the same canonical JSON files manually. Prefer MCP write tools for operations they explicitly cover, especially `study_generate_sketch_figure`, `study_register_derived_figure` and `study_mark_artifact`; do not bypass them by editing registries directly.

MCP is an adapter, not a new source of truth. Pipelines, handoffs and deterministic scripts remain authoritative. Do not fan out into many tiny MCP calls when one context call is sufficient. Topic/concept lookup must follow the exact resolution rules defined by the owning pipeline; never use fuzzy matching to silently choose an academic scope.

## Portable execution
Unit-scoped semantic pipelines use explicit handoff files under
`unidades/<unit-id>/.study/runs/<run-id>/`. A truly course-wide action may use
the course's `.study/runs/<run-id>/`. Those files are the portable isolation
boundary; never place a unit run in another unit or infer scope from a filename.

## Canonical unit boundary

Resolve every pedagogical request that produces/evaluates unit material to a stable `unit_id` before reading or writing content. Sources, observed topics, concepts, figures, progress, notes, summaries, questions, simulations, assets and run state live below `materias/<course>/unidades/<unit-id>/`. Only identity, academic unit catalog, assessments, rules and genuinely cross-unit sources stay at course level.

`academic.json -> units[].topics` is the declared syllabus. `unidades/<unit-id>/conocimiento/topics.json` is the observed canonical thematic structure reconstructed from processed material. They are deliberately separate.

Use `study_get_unit_context` (or `scripts/course_layout.py` through the deterministic CLI) as the path authority. V3 root registries are read-only compatibility inputs until `study.py units migrate` is applied.

Provider-specific isolation (Claude subagents/context forks, Codex parallel agents/worktrees, etc.) is optional. If used, it must consume and produce the same handoff contracts and may not change the pipeline semantics.

## Public actions
Exactly nine student-facing actions are exposed through generated Claude/Codex adapters:

`procesar`, `aprender`, `estudiar`, `resumen`, `repaso`, `preguntas`, `quiz`, `simulacro`, `estado`.

Keep the public surface small:
- `aprender` resolves either an observed topic or one canonical concept; concept explanation is not a separate public action.
- `resumen` owns both standard and explicitly requested detailed/guide depth; do not expose a parallel `guia` action.
- `auditar` is maintenance-only and must not appear as a student-facing adapter.

## Internal compatibility and maintenance
- `pipelines/guia.md` is a compatibility wrapper that routes legacy guide intent to detailed `resumen`.
- `pipelines/explicar.md` is a compatibility wrapper that routes legacy concept-explanation intent to `aprender`.
- `pipelines/auditar.md` remains an explicit maintenance/debugging pipeline for developers, not a public study command.
