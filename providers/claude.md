# Claude Code executor notes

The portable pipelines are authoritative. Claude-specific features are optional optimizations only.

When useful, an isolated subagent/context may execute PLAN, REVIEW or other stages, but it must receive exactly the stage inputs described by the pipeline and write the same handoff file. Do not make `context: fork`, subagents or Desktop-specific behavior necessary for correctness.


Project MCP configuration lives in `.mcp.json`. When `university-study` is connected, prefer the shared coarse-grained MCP tools described in `core/ROUTER.md`; do not make MCP availability necessary for correctness.
