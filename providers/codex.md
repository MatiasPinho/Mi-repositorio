# Codex executor notes

The portable pipelines are authoritative. Codex may use its native agent/parallel execution capabilities when available, but each stage must consume/produce the same handoff contracts.

Do not encode Codex-only behavior in `rules/` or `pipelines/`. Project skills under `.agents/skills/` are adapters to the shared core.


Project MCP configuration lives in `.codex/config.toml`. When `university-study` is connected, prefer the shared coarse-grained MCP tools described in `core/ROUTER.md`; do not make MCP availability necessary for correctness.
