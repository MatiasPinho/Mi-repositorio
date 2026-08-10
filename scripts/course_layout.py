#!/usr/bin/env python3
"""Canonical course/unit layout and backwards-compatible path resolution.

V4 stores every piece of pedagogical state below ``unidades/<unit-id>/``.
Course-wide academic/administrative material stays at the course root.  This
module is deliberately small and deterministic so CLI, MCP and pipeline tools
cannot invent their own interpretation of a unit path.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable

try:  # package import from study.py / MCP
    from .unit_identity import record_unit_id, resolve_unit, stable_unit_id_from_row
except ImportError:  # direct execution/import by scripts in this directory
    from unit_identity import record_unit_id, resolve_unit, stable_unit_id_from_row

LAYOUT_VERSION = 4
UNITS_DIR = "unidades"
UNIT_DIRECTORIES = (
    "fuentes/oficiales",
    "fuentes/transcripciones",
    "conocimiento",
    "progreso",
    "notas",
    "resumenes/_source",
    "preguntas",
    "simulacros",
    "assets/figures",
    ".study/runs",
)
REGISTRIES = {
    "concepts": ("conocimiento/concepts.json", "concepts", 2),
    "figures": ("conocimiento/figures.json", "figures", 2),
    "progress": ("progreso/progress.json", "concepts", 2),
}
LEGACY_DIRECTORIES = (
    "conocimiento",
    "progreso",
    "notas",
    "resumenes",
    "preguntas",
    "simulacros",
    "assets",
)


class LayoutError(RuntimeError):
    pass


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def academic_units(course: Path) -> list[dict[str, Any]]:
    data = read_json(course / "academico" / "academic.json", {})
    rows = data.get("units", []) if isinstance(data, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def unit_ids(course: Path) -> list[str]:
    rows: list[str] = []
    for row in academic_units(course):
        unit_id = stable_unit_id_from_row(row)
        if unit_id and unit_id not in rows:
            rows.append(unit_id)
    return rows


def units_root(course: Path) -> Path:
    return course / UNITS_DIR


def canonical_unit_id(course: Path, unit: str, *, required: bool = True) -> str:
    resolved = resolve_unit(course, unit)
    unit_id = str(resolved.get("unit_id", "")).strip()
    known = unit_ids(course)
    if required and (not unit_id or (known and unit_id not in known)):
        raise LayoutError(f"Unidad desconocida en academic.json: {unit}")
    return unit_id


def unit_root(course: Path, unit: str, *, required: bool = True) -> Path:
    unit_id = canonical_unit_id(course, unit, required=required)
    if not unit_id:
        raise LayoutError(f"No se pudo resolver la unidad: {unit}")
    return units_root(course) / unit_id


def existing_unit_roots(course: Path) -> list[Path]:
    base = units_root(course)
    if not base.is_dir():
        return []
    return sorted(
        [path for path in base.iterdir() if path.is_dir() and not path.name.startswith("_")],
        key=lambda path: path.name,
    )


def has_unit_layout(course: Path) -> bool:
    marker = course / ".study" / "layout.json"
    if marker.is_file():
        data = read_json(marker, {})
        if int(data.get("version", 0) or 0) >= LAYOUT_VERSION:
            return True
    return bool(existing_unit_roots(course))


def unit_metadata(course: Path, unit_id: str) -> dict[str, Any]:
    for row in academic_units(course):
        if stable_unit_id_from_row(row) == unit_id:
            return {
                "version": 1,
                "unit_id": unit_id,
                "name": str(row.get("name", unit_id)),
                "topics": row.get("topics", []),
                "status": row.get("status", "unknown"),
            }
    return {"version": 1, "unit_id": unit_id, "name": unit_id, "topics": [], "status": "unknown"}


def ensure_unit(course: Path, unit: str) -> Path:
    root = unit_root(course, unit)
    for dirname in UNIT_DIRECTORIES:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    write_json(root / "unidad.json", unit_metadata(course, root.name))
    for kind, (relative, key, version) in REGISTRIES.items():
        path = root / relative
        if not path.exists():
            write_json(path, {"version": version, key: {}})
    return root


def legacy_content_present(course: Path) -> bool:
    for kind in REGISTRIES:
        relative, key, _version = REGISTRIES[kind]
        data = read_json(course / relative, {key: {}})
        if isinstance(data, dict) and data.get(key):
            return True
    for dirname in ("notas", "resumenes", "preguntas", "simulacros", "assets"):
        root = course / dirname
        if root.exists() and any(path.is_file() and path.name != "README.md" for path in root.rglob("*")):
            return True
    return False


def sync_units(course: Path, *, allow_legacy: bool = False) -> dict[str, Any]:
    if not allow_legacy and not has_unit_layout(course) and legacy_content_present(course):
        raise LayoutError(
            "La materia contiene estado V3 en la raíz. Ejecutá 'study.py units migrate <materia>' "
            "antes de sincronizar para no ocultar contenido."
        )
    wanted = unit_ids(course)
    created: list[str] = []
    updated: list[str] = []
    for unit_id in wanted:
        root = units_root(course) / unit_id
        existed = root.is_dir()
        ensure_unit(course, unit_id)
        (updated if existed else created).append(unit_id)
    units_root(course).mkdir(parents=True, exist_ok=True)
    marker = course / ".study" / "layout.json"
    write_json(marker, {"version": LAYOUT_VERSION, "unit_directory": UNITS_DIR, "units": wanted})
    existing = [path.name for path in existing_unit_roots(course)]
    return {
        "version": LAYOUT_VERSION,
        "created": created,
        "updated": updated,
        "orphaned": sorted(set(existing) - set(wanted)),
        "units": wanted,
    }


def registry_path(course: Path, kind: str, unit: str = "", *, for_write: bool = False) -> Path:
    if kind not in REGISTRIES:
        raise LayoutError(f"Registro desconocido: {kind}")
    relative, _, _ = REGISTRIES[kind]
    if unit:
        root = ensure_unit(course, unit) if for_write else unit_root(course, unit)
        return root / relative
    return course / relative


def _empty_registry(kind: str) -> dict[str, Any]:
    _, key, version = REGISTRIES[kind]
    return {"version": version, key: {}}


def registry_paths(course: Path, kind: str, unit: str = "") -> list[Path]:
    relative, _, _ = REGISTRIES[kind]
    if unit:
        canonical = unit_root(course, unit) / relative
        if canonical.exists() or has_unit_layout(course):
            return [canonical]
        legacy = course / relative
        return [legacy] if legacy.exists() else [canonical]
    roots = existing_unit_roots(course)
    if roots:
        return [root / relative for root in roots]
    return [course / relative]


def load_registry(course: Path, kind: str, unit: str = "") -> dict[str, Any]:
    _, key, version = REGISTRIES[kind]
    merged = {"version": version, key: {}}
    owners: dict[str, str] = {}
    for path in registry_paths(course, kind, unit):
        data = read_json(path, _empty_registry(kind))
        rows = data.get(key, {}) if isinstance(data, dict) else {}
        if not isinstance(rows, dict):
            raise LayoutError(f"{path} debe contener un objeto JSON en '{key}'")
        for row_key, row in rows.items():
            if row_key in merged[key] and merged[key][row_key] != row:
                raise LayoutError(
                    f"Clave duplicada entre unidades en {kind}: {row_key} "
                    f"({owners[row_key]} y {path})"
                )
            merged[key][row_key] = row
            owners[row_key] = path.as_posix()
        merged["version"] = max(int(merged.get("version", version)), int(data.get("version", version) or version))
    return merged


def _progress_unit_id(course: Path, key: str, item: Any, concepts: dict[str, Any]) -> str:
    if isinstance(item, dict):
        unit_id = record_unit_id(course, item)
        if unit_id:
            return unit_id
        name = str(item.get("name", key))
    else:
        name = key
    candidates = [concepts.get(key)]
    candidates += [row for row in concepts.values() if isinstance(row, dict) and str(row.get("name", "")).casefold() == name.casefold()]
    for row in candidates:
        if isinstance(row, dict):
            unit_id = record_unit_id(course, row)
            if unit_id:
                return unit_id
    return ""


def save_registry(course: Path, kind: str, data: dict[str, Any], unit: str = "") -> None:
    """Save a registry, partitioning merged data when a V4 layout is active."""
    relative, key, version = REGISTRIES[kind]
    rows = data.get(key, {}) if isinstance(data, dict) else {}
    if not isinstance(rows, dict):
        raise LayoutError(f"El registro {kind} debe contener un objeto '{key}'")
    if unit:
        write_json(registry_path(course, kind, unit, for_write=True), {"version": data.get("version", version), key: rows})
        return
    if not has_unit_layout(course):
        write_json(course / relative, {"version": data.get("version", version), key: rows})
        return

    concepts = load_registry(course, "concepts").get("concepts", {}) if kind == "progress" else {}
    partitions = {unit_id: {} for unit_id in unit_ids(course)}
    unassigned: list[str] = []
    for row_key, item in rows.items():
        unit_id = _progress_unit_id(course, row_key, item, concepts) if kind == "progress" else (
            record_unit_id(course, item) if isinstance(item, dict) else ""
        )
        if unit_id not in partitions:
            unassigned.append(str(row_key))
            continue
        partitions[unit_id][row_key] = item
    if unassigned:
        raise LayoutError(
            f"No se puede guardar {kind}: registros sin unidad canónica: {', '.join(unassigned[:8])}"
        )
    for unit_id, partition in partitions.items():
        root = ensure_unit(course, unit_id)
        write_json(root / relative, {"version": data.get("version", version), key: partition})


def iter_source_files(course: Path, unit: str = "") -> Iterable[tuple[Path, str, str]]:
    """Yield ``(path, source ref, unit_id)`` with V3-compatible legacy refs."""
    v4 = has_unit_layout(course)
    if unit:
        roots = [(unit_root(course, unit) / "fuentes", canonical_unit_id(course, unit))]
    else:
        roots = [(course / "fuentes", "")]
        roots += [(root / "fuentes", root.name) for root in existing_unit_roots(course)]
    seen: set[Path] = set()
    for base, unit_id in roots:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            resolved = path.resolve()
            if not path.is_file() or resolved in seen:
                continue
            seen.add(resolved)
            if not v4 and base.resolve() == (course / "fuentes").resolve():
                ref = path.relative_to(base).as_posix()
            else:
                ref = path.relative_to(course).as_posix()
            yield path, ref, unit_id


def resolve_source(course: Path, value: str, unit: str = "") -> Path:
    raw = Path(value)
    candidates: list[Path] = [raw] if raw.is_absolute() else []
    if not raw.is_absolute():
        normalized = value.replace("\\", "/")
        if normalized.startswith(("unidades/", "fuentes/")):
            candidates.append(course / raw)
        if unit:
            candidates.extend([unit_root(course, unit) / "fuentes" / raw, unit_root(course, unit) / raw])
        candidates.extend([course / "fuentes" / raw, course / raw])
    allowed = [course / "fuentes"] + [root / "fuentes" for root in existing_unit_roots(course)]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_file() and any(resolved.is_relative_to(root.resolve()) for root in allowed):
                return resolved
        except OSError:
            continue
    raise LayoutError(f"Fuente no encontrada dentro de la materia: {value}")


def source_ref(course: Path, path: Path, unit: str = "") -> str:
    resolved = path.resolve()
    if unit:
        base = (unit_root(course, unit) / "fuentes").resolve()
        if resolved.is_relative_to(base):
            return resolved.relative_to(base).as_posix()
    return resolved.relative_to(course.resolve()).as_posix()


def content_path(course: Path, unit: str, relative: str) -> Path:
    """Resolve a path stored in a unit registry (unit-relative or course-relative)."""
    raw = Path(relative)
    if raw.is_absolute():
        return raw.resolve()
    normalized = relative.replace("\\", "/")
    if normalized.startswith(("unidades/", "fuentes/")):
        return (course / raw).resolve()
    return (unit_root(course, unit) / raw).resolve()


def artifact_directories(course: Path, unit: str = "") -> list[Path]:
    names = ("resumenes", "preguntas", "simulacros")
    if unit:
        return [unit_root(course, unit) / name for name in names]
    roots = existing_unit_roots(course)
    if roots:
        return [root / name for root in roots for name in names]
    return [course / name for name in names]


def run_root(course: Path, pipeline: str, scope: str, timestamp: str) -> Path:
    unit_id = canonical_unit_id(course, scope, required=False) if scope else ""
    if unit_id and has_unit_layout(course):
        return ensure_unit(course, unit_id) / ".study" / "runs" / f"{timestamp}-{pipeline}"
    return course / ".study" / "runs" / f"{timestamp}-{pipeline}"


def archive_legacy_tree(course: Path, names: Iterable[str] = LEGACY_DIRECTORIES) -> list[str]:
    """Move legacy pedagogical roots to a non-scanned recovery area."""
    archive = course / ".study" / "legacy-layout-v3"
    moved: list[str] = []
    for name in names:
        source = course / name
        if not source.exists():
            continue
        target = archive / name
        if target.exists():
            raise LayoutError(f"El archivo de recuperación ya existe: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        moved.append(name)
    return moved
