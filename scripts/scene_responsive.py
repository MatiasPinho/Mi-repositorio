#!/usr/bin/env python3
"""Upgrade rendered V2 scene <img> tags into responsive <picture> markup."""
from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
from pathlib import Path

_IMG_RE = re.compile(r'(<img\b[^>]*\bsrc=")([^"]+)("[^>]*>)', re.I)
_SCENE_ID_RE = re.compile(r'data-scene-id="([^"]+)"')
_NARROW_RE = re.compile(r'data-narrow-variant="([^"]+)"')


def _remote(src: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I)) or src.startswith("#")


def responsive_html(html_path: Path, text: str) -> tuple[str, list[dict]]:
    rows: list[dict] = []

    def replace(match: re.Match[str]) -> str:
        src = match.group(2)
        if _remote(src):
            return match.group(0)
        wide = (html_path.parent / src).resolve()
        if wide.suffix.lower() != ".svg" or not wide.is_file():
            return match.group(0)
        try:
            head = wide.read_text(encoding="utf-8")[:8192]
        except (OSError, UnicodeError):
            return match.group(0)
        if 'data-study-scene="1"' not in head or 'data-scene-version="2"' not in head:
            return match.group(0)
        narrow_match = _NARROW_RE.search(head)
        scene_match = _SCENE_ID_RE.search(head)
        if not narrow_match or not scene_match:
            raise ValueError(f"V2 wide scene lacks responsive metadata: {wide}")
        narrow_name = html.unescape(narrow_match.group(1))
        if "/" in narrow_name or "\\" in narrow_name or narrow_name in {"", ".", ".."}:
            raise ValueError(f"unsafe narrow scene basename: {narrow_name}")
        narrow = wide.with_name(narrow_name)
        if not narrow.is_file():
            raise ValueError(f"narrow scene variant missing: {narrow}")
        narrow_src = posixpath.join(posixpath.dirname(src), narrow_name)
        original_img = match.group(1) + src + match.group(3)
        picture = (
            f'<picture class="study-scene-picture" data-scene-id="{html.escape(scene_match.group(1), quote=True)}">'
            f'<source media="(max-width: 48rem)" srcset="{html.escape(narrow_src, quote=True)}">'
            f'{original_img}</picture>'
        )
        rows.append({
            "scene_id": scene_match.group(1),
            "wide": src,
            "narrow": narrow_src,
            "wide_file": str(wide),
            "narrow_file": str(narrow),
        })
        return picture

    return _IMG_RE.sub(replace, text), rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Add responsive V2 scene variants to rendered study HTML")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--report")
    args = ap.parse_args()
    inp = Path(args.input).resolve()
    out = Path(args.output).resolve()
    if inp.parent != out.parent:
        raise SystemExit("scene responsive transform requires input/output in the same directory")
    try:
        transformed, scenes = responsive_html(inp, inp.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    out.write_text(transformed, encoding="utf-8")
    report = {"version": 1, "ok": True, "scenes": scenes, "count": len(scenes)}
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
