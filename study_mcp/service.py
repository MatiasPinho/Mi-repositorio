"""Transport-agnostic service layer exposed by the local Study MCP server.

All state mutations delegate to the same deterministic scripts used by study.py.
The MCP adapter never writes academic JSON registries directly.
"""
from __future__ import annotations

import json
import os
import subprocess
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


def _run(script: str, *args: str) -> dict[str, Any] | list[Any] | str:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    cp = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if cp.returncode != 0:
        message = (cp.stderr or cp.stdout or f"Fallo {script}").strip()
        raise StudyMCPError(message)
    text = cp.stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _unit_row(course: Path, unit_id: str) -> dict[str, Any] | None:
    academic = _read(course / "academico" / "academic.json", {})
    for row in academic.get("units", []) if isinstance(academic, dict) else []:
        if isinstance(row, dict) and stable_unit_id_from_row(row) == unit_id:
            return row
    return None


def _progress_rows(course: Path, unit: str = "") -> dict[str, Any]:
    data = _read(course / "progreso" / "progress.json", {"concepts": {}})
    concepts = data.get("concepts", {}) if isinstance(data, dict) else {}
    if not unit:
        return concepts if isinstance(concepts, dict) else {}
    target = resolve_unit(course, unit).get("unit_id", "")
    graph = _read(course / "conocimiento" / "concepts.json", {"concepts": {}})
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


def material_changes(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    _, changes = study.scan_materials(course)
    return {"course": course.name, **changes}


def get_course_context(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    academic = _read(course / "academico" / "academic.json", {})
    concepts = _read(course / "conocimiento" / "concepts.json", {"concepts": {}})
    figures = _read(course / "conocimiento" / "figures.json", {"figures": {}})
    context_path = course / "contexto.md"
    context_text = context_path.read_text(encoding="utf-8") if context_path.exists() else ""
    _, changes = study.scan_materials(course)
    return {
        "course": course.name,
        "display_name": study.course_display_name(course),
        "academic": academic,
        "context": context_text,
        "material_changes": changes,
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
    data = _read(course / "conocimiento" / "figures.json", {"figures": {}})
    rows = data.get("figures", {}) if isinstance(data, dict) else {}
    return {"course": course.name, "unit_id": None, "count": len(rows), "figures": rows}


def verify_figures(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    result = _run("figure_assets.py", "verify", "--course", str(course))
    if not isinstance(result, dict):
        raise StudyMCPError("figure_assets.py verify no devolvió JSON")
    return result


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
    if not based_on:
        raise StudyMCPError("based_on debe contener al menos una referencia canónica")
    course = _course(course_name)
    args = [
        "register-derived", "--course", str(course), "--id", figure_id,
        "--unit", unit, "--asset", asset, "--kind", kind, "--role", role,
        "--description", description,
    ]
    for value in concepts or []:
        args += ["--concept", value]
    for value in learner_focus or []:
        args += ["--learner-focus", value]
    for value in based_on:
        args += ["--based-on", value]
    result = _run("figure_assets.py", *args)
    if not isinstance(result, dict):
        raise StudyMCPError("register-derived no devolvió JSON")
    return result


def list_artifacts(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    result = _run("artifact_state.py", "status", "--course", str(course))
    rows = result if isinstance(result, list) else []
    return {"course": course.name, "count": len(rows), "artifacts": rows}


def validate_artifact(
    course_name: str,
    markdown: str,
    html: str,
    scope: str,
    artifact_type: str,
) -> dict[str, Any]:
    course = _course(course_name)
    result = _run(
        "artifact_integrity.py",
        "--course", str(course),
        "--markdown", markdown,
        "--html", html,
        "--scope", scope,
        "--type", artifact_type,
    )
    if not isinstance(result, dict):
        raise StudyMCPError("artifact_integrity.py no devolvió JSON")
    return result


def mark_artifact(course_name: str, file: str, artifact_type: str, scope: str = "") -> dict[str, Any]:
    course = _course(course_name)
    result = _run(
        "artifact_state.py", "mark", "--course", str(course), "--file", file,
        "--type", artifact_type, "--scope", scope,
    )
    if not isinstance(result, dict):
        raise StudyMCPError("artifact_state.py mark no devolvió JSON")
    return result


def validate_course(course_name: str) -> dict[str, Any]:
    course = _course(course_name)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    cp = subprocess.run(
        [sys.executable, str(ROOT / "study.py"), "validate", course.name],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return {
        "ok": cp.returncode == 0,
        "course": course.name,
        "stdout": cp.stdout.strip(),
        "stderr": cp.stderr.strip(),
    }
