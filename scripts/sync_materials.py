#!/usr/bin/env python3
"""Canonical material index for course source files.

All deterministic callers, including ``study.py materials scan`` and Engine QA,
share this module for source metadata, diffs, index paths, and idempotent writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .course_layout import has_unit_layout, iter_source_files, unit_root
else:
    from course_layout import has_unit_layout, iter_source_files, unit_root

IGNORED = {"README.md", ".DS_Store", "Thumbs.db"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def material_kind(relative: str | Path) -> str:
    path = Path(relative)
    parts = [value.lower() for value in path.parts]
    suffix = path.suffix.lower()
    if "transcripciones" in parts or suffix in {".srt", ".vtt"}:
        return "transcript"
    if "oficiales" in parts:
        return "official"
    return "unclassified"


def materials_index_path(course: Path, unit: str = "") -> Path:
    if unit and has_unit_layout(course):
        return unit_root(course, unit) / ".study" / "materials-index.json"
    return course / ".study" / "materials-index.json"


def scan(course: Path, unit: str = "") -> dict[str, dict[str, Any]]:
    """Return the canonical source metadata currently visible to a scope."""
    files: dict[str, dict[str, Any]] = {}
    for path, reference, owner in iter_source_files(course, unit):
        if path.name in IGNORED:
            continue
        if not has_unit_layout(course):
            reference = reference.removeprefix("fuentes/")
        stat = path.stat()
        files[reference] = {
            "sha256": sha256(path),
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "kind": material_kind(reference),
            "unit_id": owner or None,
        }
    return files


def read_previous(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    files = data.get("files", {}) if isinstance(data, dict) else {}
    return files if isinstance(files, dict) else {}


def material_diff(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(
        key
        for key in set(current) & set(previous)
        if current[key].get("sha256") != previous[key].get("sha256")
    )
    return {"added": added, "changed": changed, "removed": removed, "total": len(current)}


def scan_materials(course: Path, unit: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    """Scan current sources and compare them with the persisted canonical index."""
    current = scan(course, unit)
    previous = read_previous(materials_index_path(course, unit))
    return current, material_diff(current, previous)


def should_write_index(index_path: Path, diff: dict[str, Any]) -> bool:
    return not index_path.exists() or any(bool(diff.get(key)) for key in ("added", "changed", "removed"))


def write_index_if_changed(
    course: Path,
    current: dict[str, Any],
    diff: dict[str, Any],
    unit: str = "",
) -> bool:
    """Persist only meaningful source-content changes; return whether bytes changed."""
    index_path = materials_index_path(course, unit)
    if not should_write_index(index_path, diff):
        return False
    index_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "files": current}
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def index_materials(
    course: Path,
    unit: str = "",
    *,
    write: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Canonical scan/diff/write transaction used by every deterministic caller."""
    current, diff = scan_materials(course, unit)
    written = write_index_if_changed(course, current, diff, unit) if write else False
    return current, diff, written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True, help="Course folder, e.g. materias/programacion-1")
    ap.add_argument("--unit")
    ap.add_argument("--write", action="store_true", help="Persist the new index")
    args = ap.parse_args()

    _, result, _ = index_materials(Path(args.course), args.unit or "", write=args.write)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
