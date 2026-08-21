#!/usr/bin/env python3
"""Build deterministic stage timing from run milestones.

The report uses the run start timestamp plus filesystem mtimes of canonical
handoff files. It is not an LLM estimate. The goal is operational visibility:
which stage actually consumed wall time in a completed/near-completed summary.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MILESTONES = (
    ("PLAN", "02-plan.json"),
    ("VISUAL_BUILD", "02-visual-build.json"),
    ("DRAFT", "03-draft.md"),
    ("HUMANIZE", "04-humanized.md"),
    ("ACADEMIC_REVIEW", "__accepted__"),
    ("RENDER", "09-rendered.html"),
    ("INTEGRITY", "10-integrity.json"),
    ("BROWSER_AUDIT", "visual-audit/audit.json"),
    ("PUBLISH", "11-publication.json"),
)


def _parse_iso(value: str) -> float:
    text = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text).timestamp()


def _accepted(run: Path) -> Path | None:
    for name in ("08-final.md", "06-final.md"):
        path = run / name
        if path.is_file():
            return path
    return None


def _fmt(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"


def build_report(run: Path) -> dict[str, Any]:
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not manifest.get("started_at"):
        raise ValueError("manifest.started_at is required")
    start = _parse_iso(str(manifest["started_at"]))
    previous = start
    stages: list[dict[str, Any]] = []
    issues: list[str] = []

    for name, rel in MILESTONES:
        path = _accepted(run) if rel == "__accepted__" else run / rel
        if path is None or not path.is_file():
            issues.append(f"missing-milestone:{name}")
            continue
        end = path.stat().st_mtime
        duration = max(0.0, end - previous)
        stages.append({
            "stage": name,
            "seconds": round(duration, 3),
            "display": _fmt(duration),
            "milestone": str(path),
            "completed_at": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        })
        previous = max(previous, end)

    total_end = previous
    total = max(0.0, total_end - start)
    return {
        "version": 1,
        "ok": not issues,
        "run": str(run),
        "started_at": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "stages": stages,
        "total_seconds": round(total, 3),
        "total_display": _fmt(total),
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit deterministic per-stage timing for a study run")
    ap.add_argument("--run", required=True)
    ap.add_argument("--write", required=True)
    args = ap.parse_args()
    try:
        report = build_report(Path(args.run).resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {"version": 1, "ok": False, "issues": [f"runtime-report-error:{exc}"]}
    out = Path(args.write).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
