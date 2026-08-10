# University Study System V3.7.2 — Claude Code

This project uses a portable shared core. Do not duplicate methodology here.

1. Read `core/ROUTER.md` when a university-study task is active.
2. Explicit slash skills under `.claude/skills/` route to the corresponding file in `pipelines/`.
3. `rules/`, `pipelines/`, `contracts/` and `vendor/` are the canonical source of truth shared with Codex.
4. Claude-specific isolation/subagents are optional optimizations described in `providers/claude.md`; correctness must not depend on them.
5. Use `study.py`/scripts for deterministic administration.

6. Student-facing summaries/guides/reviews use semantic Markdown internally and rendered HTML as the normal reading artifact. Do not bypass the shared visual rules/renderer.

7. Design-system maintenance uses `study-design` + `study-design-reviewer` and may consult vendored `frontend-design`. Normal study actions must not load those design-time skills; they consume the frozen renderer/theme.
8. When the local `university-study` MCP server is connected, prefer its coarse-grained context tools and safe write tools over manually reopening/filtering canonical JSON or editing registries. MCP is optional: CLI/scripts remain the deterministic fallback and source of truth.
