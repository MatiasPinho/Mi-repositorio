#!/usr/bin/env python3
"""Deterministic pre-publication integrity gate for student-facing artifacts."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import resolve_course  # noqa: E402
from scripts.figure_assets import load_registry, registry_issues  # noqa: E402
from scripts.course_layout import has_unit_layout, unit_root  # noqa: E402
from scripts.render_study import validate_caption_comments, validate_images  # noqa: E402
from scripts.unit_identity import record_unit_id, resolve_unit  # noqa: E402


def safe_file(value: str, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    if must_exist and not path.is_file():
        raise SystemExit(f"File not found: {value}")
    return path


def markdown_images(md_path: Path, text: str) -> list[tuple[str, Path | None]]:
    rows: list[tuple[str, Path | None]] = []
    for _alt, src in re.findall(r"!\[([^\]]*)\]\(([^)\s]+)", text):
        if re.match(r"^[a-z]+://", src) or src.startswith("data:"):
            rows.append((src, None))
        else:
            rows.append((src, (md_path.parent / src).resolve()))
    return rows


def html_image_issues(html_path: Path, text: str) -> list[str]:
    issues: list[str] = []
    for src in re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', text, re.I):
        if re.match(r"^[a-z]+://", src) or src.startswith("data:"):
            continue
        if not (html_path.parent / src).resolve().is_file():
            issues.append(f"rendered-image-missing:{src}")
    if "<!-- caption:" in text.lower():
        issues.append("caption-comment-leaked-to-html")
    return issues


def check(course: Path, md_path: Path, html_path: Path, scope: str, artifact_type: str) -> dict[str, Any]:
    issues: list[str] = []
    md_text = md_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    if not md_text.strip():
        issues.append("markdown-empty")
    if not html_text.strip():
        issues.append("html-empty")
    issues.extend(validate_images(md_path, md_text))
    issues.extend(validate_caption_comments(md_text))
    issues.extend(html_image_issues(html_path, html_text))

    registry = load_registry(course)
    reg_issues = registry_issues(course, registry)
    issues.extend(f"figure-registry:{x.get('figure','?')}:{x.get('reason','issue')}" for x in reg_issues)
    figures = registry.get("figures", {}) if isinstance(registry, dict) else {}
    by_asset: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    for key, item in figures.items():
        if isinstance(item, dict) and item.get("asset"):
            by_asset.setdefault((record_unit_id(course, item), str(item["asset"])), []).append((key, item))

    resolved = resolve_unit(course, scope)
    unit_id = resolved.get("unit_id", "")
    scoped = {
        key: item for key, item in figures.items()
        if isinstance(item, dict) and unit_id and record_unit_id(course, item) == unit_id
    }
    used_registered: set[str] = set()
    asset_base = unit_root(course, unit_id) if unit_id and has_unit_layout(course) else course
    for src, target in markdown_images(md_path, md_text):
        if target is None:
            continue
        try:
            rel = target.relative_to(asset_base.resolve()).as_posix()
        except ValueError:
            continue
        if not rel.startswith("assets/figures/"):
            continue
        matches = by_asset.get((unit_id, rel), [])
        if not matches and not has_unit_layout(course):
            matches = by_asset.get(("", rel), []) + [
                row for (owner, asset), values in by_asset.items() if asset == rel for row in values
            ]
        if not matches:
            issues.append(f"unregistered-figure-asset:{rel}")
            continue
        if len(matches) != 1:
            issues.append(f"ambiguous-figure-asset:{rel}")
            continue
        key, item = matches[0]
        used_registered.add(key)
        item_unit = record_unit_id(course, item)
        if unit_id and item_unit != unit_id:
            issues.append(f"figure-wrong-unit:{key}:{item_unit or 'missing'}!={unit_id}")

    if used_registered and not scoped:
        issues.append("scope-figure-count-zero-with-used-figures")
    if len(used_registered) > len(scoped):
        issues.append(f"scope-figure-count-too-small:{len(scoped)}<{len(used_registered)}")

    result = {
        "ok": not issues,
        "artifact_type": artifact_type,
        "scope": scope,
        "unit_id": unit_id,
        "used_figure_count": len(used_registered),
        "scoped_figure_count": len(scoped),
        "issues": issues,
    }
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a rendered study artifact before publication")
    ap.add_argument("--course", required=True)
    ap.add_argument("--markdown", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--scope", default="")
    ap.add_argument("--type", default="summary", choices=["summary", "guide", "rapid-review"])
    ap.add_argument("--write")
    args = ap.parse_args()
    course = resolve_course(args.course)
    md = safe_file(args.markdown)
    html = safe_file(args.html)
    result = check(course, md, html, args.scope, args.type)
    if args.write:
        out = Path(args.write)
        if not out.is_absolute():
            out = (ROOT / out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
