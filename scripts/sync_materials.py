#!/usr/bin/env python3
"""Index course source files and report added/changed/removed material."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .course_layout import has_unit_layout, iter_source_files, unit_root
else:
    from course_layout import has_unit_layout, iter_source_files, unit_root

IGNORED = {"README.md", ".DS_Store", "Thumbs.db"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(course: Path, unit: str = "") -> dict:
    files = {}
    for p, rel, owner in iter_source_files(course, unit):
        if p.name not in IGNORED:
            if not has_unit_layout(course):
                rel = rel.removeprefix("fuentes/")
            stat = p.stat()
            files[rel] = {
                "sha256": sha256(p),
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "unit_id": owner or None,
            }
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True, help="Course folder, e.g. materias/programacion-1")
    ap.add_argument("--unit")
    ap.add_argument("--write", action="store_true", help="Persist the new index")
    args = ap.parse_args()

    course = Path(args.course)
    study_dir = unit_root(course, args.unit) / ".study" if args.unit and has_unit_layout(course) else course / ".study"
    index_path = study_dir / "materials-index.json"
    current = scan(course, args.unit or "")
    previous = {}
    if index_path.exists():
        previous = json.loads(index_path.read_text(encoding="utf-8")).get("files", {})

    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(k for k in set(current) & set(previous) if current[k]["sha256"] != previous[k]["sha256"])

    result = {"added": added, "changed": changed, "removed": removed, "total": len(current)}
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.write:
        study_dir.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "files": current}
        index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
