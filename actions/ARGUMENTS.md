# Shared action argument resolution

1. Use an explicitly supplied course slug/name.
2. If omitted and exactly one real course exists (excluding `_plantilla`), use it.
3. Reuse immediate unambiguous course context when available.
4. Otherwise run `python study.py course list` and ask only for the missing course.

Use deterministic CLI for administration. Do not infer academic rules or assessment scope from convention.
