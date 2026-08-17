#!/usr/bin/env python3
"""Resolve whether a unit summary is actually published on disk.

Run history is intentionally ignored. A finished `.study/runs/...` directory is
execution evidence/cache, not proof that the canonical published artifact still
exists. The summary pipeline uses this before deciding whether an existing
artifact can be surfaced instead of generating a new one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
try:
    from .course_layout import has_unit_layout, unit_root
    from .unit_identity import resolve_unit
except ImportError:
    from course_layout import has_unit_layout, unit_root  # type: ignore
    from unit_identity import resolve_unit  # type: ignore


def inspect_summary(course: Path, scope: str) -> dict[str, Any]:
    resolved = resolve_unit(course, scope)
    unit_id = str(resolved.get("unit_id") or "")
    if not unit_id:
        raise ValueError(f"Could not resolve stable unit id from: {scope}")

    base = unit_root(course, unit_id) if has_unit_layout(course) else course
    publish_dir = base / "resumenes"
    markdown = {
        path.stem: path
        for path in publish_dir.glob("*.md")
        if path.is_file() and "_source" not in path.parts
    } if publish_dir.is_dir() else {}
    html = {
        path.stem: path
        for path in publish_dir.glob("*.html")
        if path.is_file() and "_source" not in path.parts
    } if publish_dir.is_dir() else {}
    stems = sorted(set(markdown) & set(html))
    pairs = [
        {
            "stem": stem,
            "markdown": str(markdown[stem]),
            "html": str(html[stem]),
        }
        for stem in stems
    ]
    return {
        "version": 1,
        "unit_id": unit_id,
        "published": bool(pairs),
        "publish_dir": str(publish_dir),
        "pairs": pairs,
        "reason": "published-pair-present" if pairs else "published-pair-missing",
        "run_history_considered": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check whether a unit summary is actually published")
    ap.add_argument("--course", required=True)
    ap.add_argument("--scope", required=True)
    args = ap.parse_args()
    try:
        report = inspect_summary(resolve_course(args.course), args.scope)
    except (ValueError, OSError) as exc:
        print(json.dumps({"version": 1, "published": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
