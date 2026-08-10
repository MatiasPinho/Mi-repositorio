"""Transport-agnostic service layer exposed by the local Study MCP server.

MCP calls the deterministic Python core in-process. It never spawns child Python
processes and never edits academic registries directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import study  # noqa: E402
import academic_context  # noqa: E402
import artifact_integrity  # noqa: E402
import artifact_state  # noqa: E402
import concept_graph  # noqa: E402
import figure_assets  # noqa: E402
import course_layout  # noqa: E402
from artifact_state import scoped_concepts, scoped_figures  # noqa: E402
from unit_identity import record_unit_id, resolve_unit, stable_unit_id_from_row  # noqa: E402


class StudyMCPError(RuntimeError):
    """Safe, concise error surfaced to an MCP client."""


def _course(value: str) -> Path:
    try:
        return study.resolve_course(value, interactive=False)
    except Exception as exc:  # study.CliError plus filesystem edge cases
        raise StudyMCPError(str(exc)) from exc


def _read(path: Path, default: Any) -> Any:
    try:
        return study.read_json(path, default)
    except Exception as exc:
        raise StudyMCPError(str(exc)) from exc


def _unit_row(course: Path, unit_id: str) -> dict[str, Any] | None:
    academic = _read(course / "academico" / "academic.json", {})
    for row in academic.get("units", []) if isinstance(academic, dict) else []:
        if isinstance(row, dict) and stable_unit_id_from_row(row) == unit_id:
            return row
    return None


def _progress_rows(course: Path, unit: str = "") -> dict[str, Any]:
    data = course_layout.load_registry(course, "progress")
    concepts = data.get("concepts", {}) if isinstance(data, dict) else {}
    if not unit:
        return concepts if isinstance(concepts, dict) else {}
    target = resolve_unit(course, unit).get("unit_id", "")
    graph = course_layout.load_registry(course, "concepts")
    graph_rows = graph.get("concepts", {}) if isinstance(graph, dict) else {}
    allowed: set[str] = set()
    for key, item in graph_rows.items():
        if isinstance(item, dict) and record_unit_id(course, item) == target:
            allowed.update({str(key), str(item.get("id", "")), str(item.get("name", ""))})
    return {
        key: value
        for key, value in concepts.items()
        if str(key) in allowed
        or (isinstance(value, dict) and (str(value.get("id", "")) in allowed or str(value.get("name", "")) in allowed))
    }


def _artifact_file(course: Path, value: str) -> Path:
    """Resolve artifact candidates from absolute, project-relative or course-relative paths."""
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [ROOT / raw, course / raw]
    for candidate in candidates:
        path = candidate.resolve()
        if path.is_file():
            return path
    raise StudyMCPError(f"File not found: {value}")


def list_courses() -> dict[str, Any]:
    rows = []
    for course in study.course_dirs():
        academic = _read(course / "academico" / "academic.json", {})
        rows.append({
            "slug": course.name,
            "name": study.course_display_name(course),
            "units": len(academic.get("units", [])) if isinstance(academic, dict) else 0,
            "assessments": len(academic.get("assessments", [])) if isinstance(academic, dict) else 0,
        })
    return {"count": len(rows), "courses": rows}


def material_changes(course_name: str, unit: str = "") -> dict[str, Any]:
    course = _course(course_name)
    _, changes = study.scan_materials(course, unit)
    return {"course": course.name, "unit": resolve_unit(course, unit) if unit else None, **changes}


def list_units(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    existing = {path.name for path in course_layout.existing_unit_roots(course)}
    rows = []
    for row in course_layout.academic_units(course):
        unit_id = stable_unit_id_from_row(row)
        rows.append({
            "unit_id": unit_id,
            "name": row.get("name", unit_id),
            "topics": row.get("topics", []),
            "status": row.get("status", "unknown"),
            "ready": unit_id in existing,
            "path": f"unidades/{unit_id}",
        })
    return {"course": course.name, "layout_version": 4 if course_layout.has_unit_layout(course) else 3, "count": len(rows), "units": rows}


def get_course_context(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    academic = _read(course / "academico" / "academic.json", {})
    concepts = course_layout.load_registry(course, "concepts")
    figures = course_layout.load_registry(course, "figures")
    context_path = course / "contexto.md"
    context_text = context_path.read_text(encoding="utf-8") if context_path.exists() else ""
    _, changes = study.scan_materials(course)
    return {
        "course": course.name,
        "display_name": study.course_display_name(course),
        "academic": academic,
        "context": context_text,
        "material_changes": changes,
        "layout": list_units(course.name),
        "knowledge_counts": {
            "concepts": len(concepts.get("concepts", {})) if isinstance(concepts, dict) else 0,
            "figures": len(figures.get("figures", {})) if isinstance(figures, dict) else 0,
        },
    }


def get_unit_context(course_name: str, unit: str) -> dict[str, Any]:
    course = _course(course_name)
    resolved = resolve_unit(course, unit)
    unit_id = resolved.get("unit_id", "")
    if not unit_id:
        raise StudyMCPError(f"No se pudo resolver la unidad: {unit}")
    row = _unit_row(course, unit_id)
    if row is None:
        raise StudyMCPError(f"La unidad no existe en academic.json: {unit}")

    concepts, scope_mode = scoped_concepts(course, unit)
    figures = scoped_figures(course, unit)
    academic = _read(course / "academico" / "academic.json", {})
    return {
        "course": course.name,
        "display_name": study.course_display_name(course),
        "unit": {"unit_id": unit_id, "label": resolved.get("label", ""), "record": row},
        "paths": {
            "root": f"unidades/{unit_id}",
            "official_sources": f"unidades/{unit_id}/fuentes/oficiales",
            "transcripts": f"unidades/{unit_id}/fuentes/transcripciones",
            "summaries": f"unidades/{unit_id}/resumenes",
        },
        "concept_scope_mode": scope_mode,
        "concepts": concepts,
        "figures": figures,
        "academic_constraints": {
            "rules": academic.get("rules", []) if isinstance(academic, dict) else [],
            "assessments": academic.get("assessments", []) if isinstance(academic, dict) else [],
            "conflicts": academic.get("conflicts", []) if isinstance(academic, dict) else [],
            "open_questions": academic.get("open_questions", []) if isinstance(academic, dict) else [],
        },
        "progress": _progress_rows(course, unit),
    }


def get_progress(course_name: str, unit: str = "") -> dict[str, Any]:
    course = _course(course_name)
    rows = _progress_rows(course, unit)
    return {"course": course.name, "unit": resolve_unit(course, unit) if unit else None, "concepts": rows, "count": len(rows)}


def list_figures(course_name: str, unit: str = "") -> dict[str, Any]:
    course = _course(course_name)
    if unit:
        resolved = resolve_unit(course, unit)
        rows = scoped_figures(course, unit)
        return {"course": course.name, "unit_id": resolved.get("unit_id"), "count": len(rows), "figures": rows}
    data = course_layout.load_registry(course, "figures")
    rows = data.get("figures", {}) if isinstance(data, dict) else {}
    return {"course": course.name, "unit_id": None, "count": len(rows), "figures": rows}


def verify_figures(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    try:
        return figure_assets.verify_registry(course)
    except (ValueError, SystemExit, OSError, json.JSONDecodeError) as exc:
        raise StudyMCPError(str(exc)) from exc


def register_derived_figure(
    course_name: str,
    figure_id: str,
    unit: str,
    asset: str,
    description: str,
    based_on: list[str],
    concepts: list[str] | None = None,
    learner_focus: list[str] | None = None,
    kind: str = "diagram",
    role: str = "supporting",
) -> dict[str, Any]:
    course = _course(course_name)
    try:
        return figure_assets.register_derived(
            course, figure_id, unit, asset, description, based_on,
            concepts=concepts, learner_focus=learner_focus, kind=kind, role=role,
        )
    except (ValueError, SystemExit, OSError, json.JSONDecodeError) as exc:
        raise StudyMCPError(str(exc)) from exc


def list_artifacts(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    try:
        rows = artifact_state.all_status(course)
    except (ValueError, SystemExit, OSError, json.JSONDecodeError) as exc:
        raise StudyMCPError(str(exc)) from exc
    return {"course": course.name, "count": len(rows), "artifacts": rows}


def validate_artifact(
    course_name: str,
    markdown: str,
    html: str,
    scope: str,
    artifact_type: str,
) -> dict[str, Any]:
    course = _course(course_name)
    if artifact_type not in {"summary", "guide", "rapid-review"}:
        raise StudyMCPError(f"Unsupported artifact type for integrity gate: {artifact_type}")
    md_path = _artifact_file(course, markdown)
    html_path = _artifact_file(course, html)
    try:
        return artifact_integrity.check(course, md_path, html_path, scope, artifact_type)
    except (ValueError, SystemExit, OSError, json.JSONDecodeError) as exc:
        raise StudyMCPError(str(exc)) from exc


def mark_artifact(course_name: str, file: str, artifact_type: str, scope: str = "") -> dict[str, Any]:
    course = _course(course_name)
    try:
        return artifact_state.mark_artifact(course, file, artifact_type, scope)
    except (ValueError, SystemExit, OSError, json.JSONDecodeError) as exc:
        raise StudyMCPError(str(exc)) from exc


def validate_course(course_name: str) -> dict[str, Any]:
    """Run structural/academic/knowledge/figure/artifact validation in-process."""
    course = _course(course_name)
    structural: list[str] = []
    canonical = course_layout.has_unit_layout(course)
    required_dirs = ["academico", "fuentes", "unidades"] if canonical else [
        "academico", "conocimiento", "fuentes", "notas", "preguntas", "progreso", "resumenes", "simulacros"
    ]
    for dirname in required_dirs:
        if not (course / dirname).is_dir():
            structural.append(f"falta carpeta requerida: {dirname}/")

    required_json = [course / "academico" / "academic.json"]
    if canonical:
        expected = set(course_layout.unit_ids(course))
        existing = {path.name for path in course_layout.existing_unit_roots(course)}
        for unit_id in sorted(expected):
            root = course / "unidades" / unit_id
            if not root.is_dir():
                structural.append(f"falta unidad canónica: unidades/{unit_id}/")
                continue
            for dirname in course_layout.UNIT_DIRECTORIES:
                if not (root / dirname).is_dir():
                    structural.append(f"falta carpeta de unidad: unidades/{unit_id}/{dirname}/")
            required_json += [root / "unidad.json", root / "conocimiento/concepts.json", root / "conocimiento/figures.json", root / "progreso/progress.json"]
        for orphan in sorted(existing - expected):
            structural.append(f"unidad huérfana no declarada en academic.json: unidades/{orphan}/")
        for kind, row_key in (("concepts", "concepts"), ("figures", "figures"), ("progress", "concepts")):
            for path in course_layout.registry_paths(course, kind):
                data = _read(path, {row_key: {}})
                owner = path.parents[1].name
                for key, item in data.get(row_key, {}).items() if isinstance(data, dict) else []:
                    if isinstance(item, dict) and record_unit_id(course, item) != owner:
                        structural.append(f"registro en unidad incorrecta: {path.relative_to(course)}#{key}")
    else:
        required_json += [course / "conocimiento/concepts.json", course / "progreso/progress.json"]
    for path in required_json:
        if not path.exists():
            structural.append(f"falta archivo requerido: {path.relative_to(course)}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            structural.append(f"JSON invalido: {path.relative_to(course)}")
    if not (course / "contexto.md").exists():
        structural.append("falta archivo requerido: contexto.md")

    academic_issues: list[dict[str, Any]] = []
    academic_path = course / "academico" / "academic.json"
    if academic_path.exists():
        try:
            academic_data = json.loads(academic_path.read_text(encoding="utf-8"))
            academic_issues = academic_context.validate_data(academic_data).get("issues", [])
        except (json.JSONDecodeError, OSError, ValueError, SystemExit) as exc:
            structural.append(f"no se pudo validar academic.json: {exc}")

    stale: list[dict[str, Any]] = []
    if any(path.exists() for path in course_layout.registry_paths(course, "concepts")):
        try:
            stale = concept_graph.stale_rows(course)
        except (json.JSONDecodeError, OSError, ValueError, SystemExit) as exc:
            structural.append(f"no se pudo validar concepts.json: {exc}")

    figure_issues: list[dict[str, Any]] = []
    if any(path.exists() for path in course_layout.registry_paths(course, "figures")):
        try:
            figure_issues = figure_assets.verify_registry(course).get("issues", [])
        except (json.JSONDecodeError, OSError, ValueError, SystemExit) as exc:
            structural.append(f"no se pudo validar figures.json: {exc}")

    try:
        stale_artifacts = [row for row in artifact_state.all_status(course) if row.get("stale")]
    except (json.JSONDecodeError, OSError, ValueError, SystemExit) as exc:
        structural.append(f"no se pudo validar artefactos: {exc}")
        stale_artifacts = []

    academic_errors = [row for row in academic_issues if str(row.get("severity", row.get("level", ""))).lower() == "error"]
    return {
        "ok": not structural and not academic_errors and not stale and not figure_issues and not stale_artifacts,
        "course": course.name,
        "structural": structural,
        "academic_issues": academic_issues,
        "stale_concepts": stale,
        "figure_issues": figure_issues,
        "stale_artifacts": stale_artifacts,
    }
