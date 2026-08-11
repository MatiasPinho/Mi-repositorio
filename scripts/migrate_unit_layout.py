#!/usr/bin/env python3
"""Migrate a V3 course into the canonical V4 unit-first layout.

The migration is collision-safe and keeps a recovery copy of every legacy
pedagogical root below ``.study/legacy-layout-v3``.  It never guesses the unit
of a knowledge/progress record: those records must already resolve to a stable
academic unit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import resolve_course  # noqa: E402
if __package__:
    from .course_layout import (  # noqa: E402
        LAYOUT_VERSION,
        LayoutError,
        archive_legacy_tree,
        read_json,
        sync_units,
        unit_ids,
        unit_root,
        write_json,
    )
    from .unit_identity import record_unit_id, resolve_unit  # noqa: E402
    from .topic_catalog import normalize as normalize_topic_text  # noqa: E402
else:
    from course_layout import (  # noqa: E402
        LAYOUT_VERSION,
        LayoutError,
        archive_legacy_tree,
        read_json,
        sync_units,
        unit_ids,
        unit_root,
        write_json,
    )
    from unit_identity import record_unit_id, resolve_unit  # noqa: E402
    from topic_catalog import normalize as normalize_topic_text  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def registry(course: Path, relative: str, key: str, version: int = 2) -> dict[str, Any]:
    data = read_json(course / relative, {"version": version, key: {}})
    if not isinstance(data, dict) or not isinstance(data.get(key, {}), dict):
        raise LayoutError(f"Registro inválido: {relative}")
    data.setdefault("version", version)
    data.setdefault(key, {})
    return data


def source_names(value: Any) -> set[str]:
    rows: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"file", "source_file"} and isinstance(item, str):
                rows.add(item.replace("\\", "/").split("#", 1)[0])
            else:
                rows.update(source_names(item))
    elif isinstance(value, list):
        for item in value:
            rows.update(source_names(item))
    elif isinstance(value, str):
        # Academic source fields may contain semicolon-separated locators.
        for match in re.findall(r"(?:oficiales|transcripciones)/[^;#]+", value.replace("\\", "/"), re.I):
            rows.add(match.strip())
    return {row.removeprefix("fuentes/") for row in rows if row}


def source_ownership(
    course: Path,
    concepts: dict[str, Any],
    topics: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for item in (
        list(concepts.get("concepts", {}).values())
        + list(topics.get("topics", {}).values())
        + list(figures.get("figures", {}).values())
    ):
        if not isinstance(item, dict):
            continue
        unit_id = record_unit_id(course, item)
        if not unit_id:
            continue
        for name in source_names(item):
            owners.setdefault(name.casefold(), set()).add(unit_id)

    # Unit rows are useful for shared-program files: a calendar referenced by
    # nine units is course-wide, not duplicated nine times.
    academic = read_json(course / "academico" / "academic.json", {})
    for row in academic.get("units", []) if isinstance(academic, dict) else []:
        if not isinstance(row, dict):
            continue
        unit_id = resolve_unit(course, str(row.get("id") or row.get("name") or "")).get("unit_id", "")
        for name in source_names(row.get("source", "")):
            owners.setdefault(name.casefold(), set()).add(unit_id)
    return owners


def progress_owner(course: Path, key: str, item: Any, concepts: dict[str, Any]) -> str:
    if isinstance(item, dict):
        direct = record_unit_id(course, item)
        if direct:
            return direct
        target = str(item.get("name", key)).casefold()
    else:
        target = key.casefold()
    for concept_key, concept in concepts.get("concepts", {}).items():
        if not isinstance(concept, dict):
            continue
        aliases = {str(concept_key).casefold(), str(concept.get("id", "")).casefold(), str(concept.get("name", "")).casefold()}
        if target in aliases:
            return record_unit_id(course, concept)
    return ""


def partition(course: Path, data: dict[str, Any], key: str, *, progress: bool = False, concepts: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    result = {unit_id: {} for unit_id in unit_ids(course)}
    unassigned: list[str] = []
    for row_key, item in data.get(key, {}).items():
        unit_id = progress_owner(course, row_key, item, concepts or {}) if progress else (
            record_unit_id(course, item) if isinstance(item, dict) else ""
        )
        if unit_id not in result:
            unassigned.append(str(row_key))
        else:
            result[unit_id][row_key] = item
    if unassigned:
        raise LayoutError(f"Registros '{key}' sin unidad estable: {', '.join(unassigned[:12])}")
    return result


def _concept_owner_map(course: Path, concepts: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, item in concepts.get("concepts", {}).items():
        if not isinstance(item, dict):
            continue
        owner = record_unit_id(course, item)
        for value in (key, item.get("id", "")):
            token = str(value).strip().casefold()
            if token and owner:
                result[token] = owner
    return result


def partition_topics(
    course: Path,
    data: dict[str, Any],
    concepts: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    """Partition an optional V3 topic catalog without dropping assignments."""
    ids = unit_ids(course)
    rows = {unit_id: {} for unit_id in ids}
    unassigned = {unit_id: [] for unit_id in ids}
    concept_owners = _concept_owner_map(course, concepts)
    concept_ids: dict[str, str] = {}
    for key, item in concepts.get("concepts", {}).items():
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("id") or key).strip()
        for value in (key, concept_id):
            if str(value).strip():
                concept_ids[str(value).strip().casefold()] = concept_id
    document_owner = str(data.get("unit_id", "")).strip()
    declared_by_unit: dict[str, dict[str, str]] = {unit_id: {} for unit_id in ids}
    academic = read_json(course / "academico" / "academic.json", {})
    for unit_row in academic.get("units", []) if isinstance(academic, dict) else []:
        if not isinstance(unit_row, dict):
            continue
        owner = resolve_unit(course, str(unit_row.get("id") or unit_row.get("name") or "")).get("unit_id", "")
        if owner in declared_by_unit:
            declared_by_unit[owner] = {
                normalize_topic_text(value): value
                for value in unit_row.get("topics", [])
                if isinstance(value, str) and value.strip()
            }
    invalid: list[str] = []

    for key, item in data.get("topics", {}).items():
        if not isinstance(item, dict):
            invalid.append(str(key))
            continue
        if item.get("id") and str(item.get("id")) != str(key):
            invalid.append(f"{key}:id")
            continue
        if any(not isinstance(item.get(field, []), list) for field in ("aliases", "concept_ids", "declared_matches", "evidence")):
            invalid.append(f"{key}:shape")
            continue
        owner = record_unit_id(course, item)
        if not owner and document_owner in rows:
            owner = document_owner
        if not owner:
            inferred = {
                concept_owners.get(str(value).strip().casefold(), "")
                for value in item.get("concept_ids", [])
            } - {""}
            if len(inferred) == 1:
                owner = next(iter(inferred))
        if not owner and len(ids) == 1:
            owner = ids[0]
        if owner not in rows:
            invalid.append(str(key))
            continue
        raw_concepts = item.get("concept_ids", [])
        if not isinstance(raw_concepts, list):
            invalid.append(f"{key}:concept_ids")
            continue
        resolved_concepts: list[str] = []
        for value in raw_concepts:
            token = str(value).strip().casefold()
            concept_id = concept_ids.get(token, "")
            if not concept_id or concept_owners.get(token) != owner:
                invalid.append(f"{key}:{value}")
                continue
            if concept_id not in resolved_concepts:
                resolved_concepts.append(concept_id)
        resolved_declared: list[str] = []
        for value in item.get("declared_matches", []):
            if not isinstance(value, str) or normalize_topic_text(value) not in declared_by_unit[owner]:
                invalid.append(f"{key}:declared:{value}")
                continue
            canonical = declared_by_unit[owner][normalize_topic_text(value)]
            if canonical not in resolved_declared:
                resolved_declared.append(canonical)
        copied = dict(item)
        copied.setdefault("id", str(key))
        copied.setdefault("name", str(key))
        copied.setdefault("aliases", [])
        copied.setdefault("declared_matches", [])
        copied.setdefault("evidence", [])
        copied["unit_id"] = owner
        copied["concept_ids"] = resolved_concepts
        copied["declared_matches"] = resolved_declared
        rows[owner][str(key)] = copied

    for value in data.get("unassigned_concept_ids", []):
        token = str(value).strip().casefold()
        owner = concept_owners.get(token, "")
        concept_id = concept_ids.get(token, "")
        if not owner and len(ids) == 1:
            owner = ids[0]
        if owner not in unassigned or not concept_id:
            invalid.append(f"unassigned:{value}")
            continue
        if concept_id not in unassigned[owner]:
            unassigned[owner].append(concept_id)
    if invalid:
        raise LayoutError(f"Temas/conceptos sin unidad estable: {', '.join(invalid[:12])}")

    assigned_by_unit: dict[str, set[str]] = {unit_id: set() for unit_id in ids}
    for unit_id, unit_topics in rows.items():
        for item in unit_topics.values():
            for value in item.get("concept_ids", []) if isinstance(item, dict) else []:
                assigned_by_unit[unit_id].add(str(value).strip().casefold())
    for key, item in concepts.get("concepts", {}).items():
        if not isinstance(item, dict):
            continue
        owner = record_unit_id(course, item)
        concept_id = str(item.get("id") or key).strip()
        aliases = {str(key).strip().casefold(), concept_id.casefold()}
        if owner in unassigned and not (aliases & assigned_by_unit[owner]):
            if concept_id not in unassigned[owner]:
                unassigned[owner].append(concept_id)
    for values in unassigned.values():
        values.sort()
    return rows, unassigned


def artifact_owner(course: Path, relative: str, manifest: dict[str, Any]) -> str:
    entry = manifest.get("artifacts", {}).get(relative, {})
    scope = str(entry.get("scope", "")) if isinstance(entry, dict) else ""
    if scope:
        unit_id = resolve_unit(course, scope).get("unit_id", "")
        if unit_id in unit_ids(course):
            return unit_id
    match = re.search(r"(?:unidad|u)[-_ ]?(\d+)", relative, re.I)
    if match:
        unit_id = f"unidad-{int(match.group(1))}"
        if unit_id in unit_ids(course):
            return unit_id
    return ""


def rewritten(value: Any, source_moves: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {rewritten(key, source_moves): rewritten(item, source_moves) for key, item in value.items()}
    if isinstance(value, list):
        return [rewritten(item, source_moves) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    for old, new in sorted(source_moves.items(), key=lambda item: -len(item[0])):
        result = result.replace(old, new)
    return result


def run_owner(course: Path, run: Path) -> str:
    manifest = read_json(run / "manifest.json", {})
    scope = str(manifest.get("scope", "")) if isinstance(manifest, dict) else ""
    if scope:
        unit_id = resolve_unit(course, scope).get("unit_id", "")
        if unit_id in unit_ids(course):
            return unit_id
    match = re.search(r"(?:unidad|u)[-_ ]?(\d+)", run.name, re.I)
    if match:
        unit_id = f"unidad-{int(match.group(1))}"
        if unit_id in unit_ids(course):
            return unit_id
    return ""


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def rewrite_json_tree(root: Path, source_moves: dict[str, str]) -> int:
    changed = 0
    if not root.exists():
        return changed
    for path in sorted(root.rglob("*.json")):
        try:
            data = read_json(path, None)
        except json.JSONDecodeError:
            continue
        updated = rewritten(data, source_moves)
        if updated != data:
            write_json(path, updated)
            changed += 1
    return changed


def build_plan(course: Path) -> dict[str, Any]:
    ids = unit_ids(course)
    if not ids:
        raise LayoutError("academic.json no contiene unidades migrables")
    if (course / ".study" / "legacy-layout-v3").exists():
        raise LayoutError("La materia ya posee un archivo de recuperación V3; no se repetirá la migración")

    concepts = registry(course, "conocimiento/concepts.json", "concepts")
    topics = registry(course, "conocimiento/topics.json", "topics", 1)
    figures = registry(course, "conocimiento/figures.json", "figures")
    progress = registry(course, "progreso/progress.json", "concepts")
    concept_parts = partition(course, concepts, "concepts")
    topic_parts, topic_unassigned = partition_topics(course, topics, concepts)
    figure_parts = partition(course, figures, "figures")
    progress_parts = partition(course, progress, "concepts", progress=True, concepts=concepts)
    owners = source_ownership(course, concepts, topics, figures)

    sources: list[dict[str, Any]] = []
    source_root = course / "fuentes"
    if source_root.exists():
        for path in sorted(source_root.rglob("*")):
            if not path.is_file() or path.name in {"README.md", ".DS_Store", "Thumbs.db"}:
                continue
            rel = path.relative_to(source_root).as_posix()
            unit_owners = sorted(owners.get(rel.casefold(), set()))
            owner = unit_owners[0] if len(unit_owners) == 1 else ""
            target = f"unidades/{owner}/fuentes/{rel}" if owner else f"fuentes/{rel}"
            sources.append({"source": f"fuentes/{rel}", "target": target, "unit_id": owner, "sha256": sha256(path)})

    manifest = read_json(course / ".study" / "artifacts.json", {"version": 1, "artifacts": {}})
    artifacts: list[dict[str, str]] = []
    for dirname in ("resumenes", "preguntas", "simulacros"):
        root = course / dirname
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name == "README.md":
                continue
            rel = path.relative_to(course).as_posix()
            owner = artifact_owner(course, rel, manifest)
            if not owner:
                raise LayoutError(f"Artefacto sin unidad resoluble: {rel}")
            artifacts.append({"source": rel, "target": f"unidades/{owner}/{rel}", "unit_id": owner})

    assets: list[dict[str, str]] = []
    figure_assets: dict[str, str] = {}
    for unit_id, rows in figure_parts.items():
        for item in rows.values():
            if isinstance(item, dict) and isinstance(item.get("asset"), str) and item["asset"]:
                figure_assets[str(item["asset"]).replace("\\", "/")] = unit_id
    asset_root = course / "assets" / "figures"
    if asset_root.exists():
        for path in sorted(asset_root.rglob("*")):
            if not path.is_file() or path.name == "README.md":
                continue
            rel = path.relative_to(course).as_posix()
            owner = figure_assets.get(rel)
            if not owner:
                raise LayoutError(f"Asset visual sin figura/unidad resoluble: {rel}")
            assets.append({"source": rel, "target": f"unidades/{owner}/{rel}", "unit_id": owner})

    runs: list[dict[str, str]] = []
    runs_root = course / ".study" / "runs"
    if runs_root.exists():
        for run in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            owner = run_owner(course, run)
            if owner:
                runs.append({
                    "source": run.relative_to(course).as_posix(),
                    "target": f"unidades/{owner}/.study/runs/{run.name}",
                    "unit_id": owner,
                })

    return {
        "layout_version": LAYOUT_VERSION,
        "course": course.name,
        "units": ids,
        "partitions": {
            unit_id: {
                "concepts": len(concept_parts[unit_id]),
                "topics": len(topic_parts[unit_id]),
                "figures": len(figure_parts[unit_id]),
                "progress": len(progress_parts[unit_id]),
            }
            for unit_id in ids
        },
        "sources": sources,
        "artifacts": artifacts,
        "assets": assets,
        "runs": runs,
        "_data": {
            "concepts": concept_parts,
            "topics": topic_parts,
            "topic_unassigned": topic_unassigned,
            "figures": figure_parts,
            "progress": progress_parts,
            "manifest": manifest,
            "concept_version": concepts.get("version", 2),
            "topic_version": topics.get("version", 1),
            "figure_version": figures.get("version", 2),
            "progress_version": progress.get("version", 2),
        },
    }


def _copy_checked(course: Path, row: dict[str, str]) -> None:
    source = course / row["source"]
    target = course / row["target"]
    if target.exists():
        if sha256(source) != sha256(target):
            raise LayoutError(f"Colisión de migración: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if sha256(source) != sha256(target):
        raise LayoutError(f"La copia no conservó el contenido: {source}")


def apply_plan(course: Path, plan: dict[str, Any]) -> dict[str, Any]:
    data = plan["_data"]
    sync_units(course, allow_legacy=True)
    for row in plan["sources"] + plan["artifacts"] + plan["assets"]:
        _copy_checked(course, row)

    for row in plan["runs"]:
        source = course / row["source"]
        target = course / row["target"]
        if target.exists():
            if tree_hashes(source) != tree_hashes(target):
                raise LayoutError(f"Colisión de ejecución: {target}")
        else:
            shutil.copytree(source, target)
            if tree_hashes(source) != tree_hashes(target):
                raise LayoutError(f"La copia no conservó la ejecución: {source}")

    source_moves = {
        row["source"].removeprefix("fuentes/"): row["target"]
        for row in plan["sources"]
    }
    academic_path = course / "academico" / "academic.json"
    academic = rewritten(read_json(academic_path, {}), source_moves)
    write_json(academic_path, academic)

    for unit_id in plan["units"]:
        root = unit_root(course, unit_id)
        write_json(root / "conocimiento" / "concepts.json", {
            "version": data["concept_version"],
            "concepts": rewritten(data["concepts"][unit_id], source_moves),
        })
        write_json(root / "conocimiento" / "topics.json", {
            "version": data["topic_version"],
            "unit_id": unit_id,
            "topics": rewritten(data["topics"][unit_id], source_moves),
            "unassigned_concept_ids": data["topic_unassigned"][unit_id],
        })
        write_json(root / "conocimiento" / "figures.json", {
            "version": data["figure_version"],
            "figures": rewritten(data["figures"][unit_id], source_moves),
        })
        write_json(root / "progreso" / "progress.json", {
            "version": data["progress_version"],
            "concepts": data["progress"][unit_id],
        })

    manifest = data["manifest"]
    migrated_entries: dict[str, Any] = {}
    targets = {row["source"]: row["target"] for row in plan["artifacts"]}
    for rel, entry in manifest.get("artifacts", {}).items():
        migrated_entries[targets.get(rel, rel)] = entry
    manifest["artifacts"] = migrated_entries
    if migrated_entries or (course / ".study" / "artifacts.json").exists():
        write_json(course / ".study" / "artifacts.json", manifest)

    for row in plan["runs"]:
        rewrite_json_tree(course / row["target"], source_moves)

    # Operational indexes remain course-wide aggregation views, but every
    # source key/locator inside them becomes an unambiguous course-relative V4
    # path. Historical unit runs are moved into the same boundary as new runs.
    for path in sorted((course / ".study").glob("*.json")):
        if path.name in {"layout.json", "artifacts.json", "unit-migration.json"}:
            continue
        data_row = read_json(path, None)
        updated = rewritten(data_row, source_moves)
        if updated != data_row:
            write_json(path, updated)

    archive = course / ".study" / "legacy-layout-v3"
    # Unit-specific sources leave the live global source tree, but the archived
    # recovery copy remains exact and independently hash-verifiable.
    for row in plan["sources"]:
        if not row["unit_id"]:
            continue
        source = course / row["source"]
        recovery = archive / row["source"]
        recovery.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, recovery)
        if sha256(source) != sha256(recovery):
            raise LayoutError(f"Falló la copia de recuperación: {source}")
        source.unlink()
    for row in plan["runs"]:
        source = course / row["source"]
        recovery = archive / row["source"]
        recovery.parent.mkdir(parents=True, exist_ok=True)
        if recovery.exists():
            raise LayoutError(f"La recuperación de ejecución ya existe: {recovery}")
        shutil.move(str(source), str(recovery))
    moved = archive_legacy_tree(course)
    write_json(course / ".study" / "unit-migration.json", {
        "version": 1,
        "from_layout": 3,
        "to_layout": LAYOUT_VERSION,
        "units": plan["units"],
        "partitions": plan["partitions"],
        "sources_moved": len([row for row in plan["sources"] if row["unit_id"]]),
        "sources_global": len([row for row in plan["sources"] if not row["unit_id"]]),
        "artifacts_moved": len(plan["artifacts"]),
        "assets_moved": len(plan["assets"]),
        "runs_moved": len(plan["runs"]),
        "runtime_state_finalized": True,
        "archived_roots": moved,
        "recovery_directory": ".study/legacy-layout-v3",
    })
    return {
        "ok": True,
        "course": course.name,
        "layout_version": LAYOUT_VERSION,
        "units": len(plan["units"]),
        "sources_moved": len([row for row in plan["sources"] if row["unit_id"]]),
        "sources_global": len([row for row in plan["sources"] if not row["unit_id"]]),
        "artifacts_moved": len(plan["artifacts"]),
        "assets_moved": len(plan["assets"]),
        "runs_moved": len(plan["runs"]),
        "recovery_directory": ".study/legacy-layout-v3",
    }


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key != "_data"}


def finalize_existing(course: Path) -> dict[str, Any]:
    """Finish runtime-index/run migration for an already partitioned V4 course."""
    report_path = course / ".study" / "unit-migration.json"
    report = read_json(report_path, {})
    if int(report.get("to_layout", 0) or 0) != LAYOUT_VERSION:
        raise LayoutError("No existe una migración V3 → V4 aplicable para finalizar")
    if report.get("runtime_state_finalized"):
        return {
            "ok": True,
            "course": course.name,
            "layout_version": LAYOUT_VERSION,
            "runtime_json_rewritten": 0,
            "runs_moved": 0,
            "already_finalized": True,
        }

    candidates: dict[str, set[str]] = {}
    global_sources = course / "fuentes"
    if global_sources.exists():
        for path in global_sources.rglob("*"):
            if path.is_file() and path.name != "README.md":
                old = path.relative_to(global_sources).as_posix()
                candidates.setdefault(old, set()).add(path.relative_to(course).as_posix())
    for unit_id in unit_ids(course):
        base = unit_root(course, unit_id) / "fuentes"
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.name != "README.md":
                old = path.relative_to(base).as_posix()
                candidates.setdefault(old, set()).add(path.relative_to(course).as_posix())
    source_moves = {old: next(iter(targets)) for old, targets in candidates.items() if len(targets) == 1}

    rewritten_files = 0
    for path in sorted((course / ".study").glob("*.json")):
        if path.name in {"layout.json", "artifacts.json", "unit-migration.json"}:
            continue
        data = read_json(path, None)
        updated = rewritten(data, source_moves)
        if updated != data:
            write_json(path, updated)
            rewritten_files += 1

    moved_runs = 0
    runs_root = course / ".study" / "runs"
    archive = course / ".study" / "legacy-layout-v3"
    if runs_root.exists():
        for run in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            owner = run_owner(course, run)
            if not owner:
                continue
            target = unit_root(course, owner) / ".study" / "runs" / run.name
            if target.exists():
                if tree_hashes(run) != tree_hashes(target):
                    raise LayoutError(f"Colisión de ejecución: {target}")
            else:
                shutil.copytree(run, target)
            rewritten_files += rewrite_json_tree(target, source_moves)
            recovery = archive / ".study" / "runs" / run.name
            recovery.parent.mkdir(parents=True, exist_ok=True)
            if recovery.exists():
                raise LayoutError(f"La recuperación de ejecución ya existe: {recovery}")
            shutil.move(str(run), str(recovery))
            moved_runs += 1

    report["runtime_state_finalized"] = True
    report["runtime_json_rewritten"] = rewritten_files
    report["runs_moved"] = int(report.get("runs_moved", 0) or 0) + moved_runs
    write_json(report_path, report)
    return {
        "ok": True,
        "course": course.name,
        "layout_version": LAYOUT_VERSION,
        "runtime_json_rewritten": rewritten_files,
        "runs_moved": moved_runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course", required=True)
    parser.add_argument("--apply", action="store_true", help="Apply the validated plan; default is dry-run")
    parser.add_argument("--finalize-existing", action="store_true", help="Finish V4 runtime indexes/runs after an earlier migration")
    args = parser.parse_args()
    try:
        course = resolve_course(args.course)
        if args.finalize_existing:
            result = finalize_existing(course)
        else:
            plan = build_plan(course)
            result = apply_plan(course, plan) if args.apply else {"ok": True, "dry_run": True, **public_plan(plan)}
    except (LayoutError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
