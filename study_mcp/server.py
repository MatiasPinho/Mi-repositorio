"""Local stdio MCP server for University Study System.

The adapter intentionally targets the maintained MCP Python SDK 1.x line so it
works with Claude Code and current Codex clients that still use the classic
initialize lifecycle. The transport is local stdio only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
except ImportError as exc:  # pragma: no cover - exercised by mcp preflight instead
    raise SystemExit(
        "Falta el SDK MCP compatible. Ejecutá: python -m pip install -r requirements-mcp.txt"
    ) from exc

from study_mcp import service

mcp = FastMCP(
    "university-study",
    instructions=(
        "Acceso local y controlado al estado canónico del University Study System. "
        "Preferí herramientas de lectura para obtener contexto y las operaciones MCP "
        "de escritura para figuras/artefactos en lugar de editar registries JSON a mano."
    ),
)

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE_SAFE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
WRITE_IDEMPOTENT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=READ)
def study_list_courses() -> dict:
    """Listar materias disponibles con slug y conteos básicos."""
    return service.list_courses()


@mcp.tool(annotations=READ)
def study_material_changes(course: str, unit: str = "") -> dict:
    """Ver fuentes nuevas, modificadas o eliminadas sin escribir hashes."""
    return service.material_changes(course, unit)


@mcp.tool(annotations=READ)
def study_list_units(course: str) -> dict:
    """Listar unidades estables, estado estructural y rutas canónicas."""
    return service.list_units(course)


@mcp.tool(annotations=READ)
def study_get_course_context(course: str) -> dict:
    """Obtener contexto académico global, material pendiente y conteos de conocimiento."""
    return service.get_course_context(course)


@mcp.tool(annotations=READ)
def study_get_unit_context(course: str, unit: str) -> dict:
    """Obtener unidad, temas observados, conceptos, figuras, restricciones y progreso."""
    return service.get_unit_context(course, unit)


@mcp.tool(annotations=READ)
def study_get_progress(course: str, unit: str = "") -> dict:
    """Consultar progreso; por unidad incluye la agregación derivada por tema."""
    return service.get_progress(course, unit)


@mcp.tool(annotations=READ)
def study_list_figures(course: str, unit: str = "") -> dict:
    """Listar figuras registradas, opcionalmente filtradas por unidad."""
    return service.list_figures(course, unit)


@mcp.tool(annotations=READ)
def study_verify_figures(course: str) -> dict:
    """Verificar IDs, assets, procedencia y colisiones del registro de figuras."""
    return service.verify_figures(course)


@mcp.tool(annotations=WRITE_SAFE)
def study_register_derived_figure(
    course: str,
    figure_id: str,
    unit: str,
    asset: str,
    description: str,
    based_on: list[str],
    concepts: list[str] | None = None,
    learner_focus: list[str] | None = None,
    kind: str = "diagram",
    role: str = "supporting",
) -> dict:
    """Registrar una figura derivada mediante el core collision-safe; nunca sobrescribe."""
    return service.register_derived_figure(
        course, figure_id, unit, asset, description, based_on,
        concepts=concepts, learner_focus=learner_focus, kind=kind, role=role,
    )


@mcp.tool(annotations=READ)
def study_list_artifacts(course: str) -> dict:
    """Listar artefactos derivados y su estado current/stale."""
    return service.list_artifacts(course)


@mcp.tool(annotations=READ)
def study_validate_artifact(course: str, markdown: str, html: str, scope: str, artifact_type: str) -> dict:
    """Ejecutar el gate determinístico de integridad sobre un candidato ya renderizado."""
    return service.validate_artifact(course, markdown, html, scope, artifact_type)


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def study_mark_artifact(course: str, file: str, artifact_type: str, scope: str = "") -> dict:
    """Marcar un artefacto publicado contra los fingerprints canónicos actuales."""
    return service.mark_artifact(course, file, artifact_type, scope)


@mcp.tool(annotations=READ)
def study_validate_course(course: str) -> dict:
    """Ejecutar la validación estructural completa de una materia."""
    return service.validate_course(course)


@mcp.resource("study://courses")
def resource_courses() -> str:
    """Catálogo local de materias."""
    return json.dumps(service.list_courses(), ensure_ascii=False, indent=2)


@mcp.resource("study://course/{course}/academic")
def resource_academic(course: str) -> str:
    """Contexto académico global de una materia."""
    return json.dumps(service.get_course_context(course), ensure_ascii=False, indent=2)


@mcp.resource("study://course/{course}/unit/{unit}/context")
def resource_unit_context(course: str, unit: str) -> str:
    """Contexto canónico agregado de una unidad."""
    return json.dumps(service.get_unit_context(course, unit), ensure_ascii=False, indent=2)


@mcp.resource("study://course/{course}/units")
def resource_units(course: str) -> str:
    """Catálogo navegable de unidades de una materia."""
    return json.dumps(service.list_units(course), ensure_ascii=False, indent=2)


@mcp.resource("study://course/{course}/progress")
def resource_progress(course: str) -> str:
    """Progreso completo de una materia."""
    return json.dumps(service.get_progress(course), ensure_ascii=False, indent=2)


def main() -> None:
    # stdio is the default FastMCP transport. Never print to stdout here: it is
    # the JSON-RPC wire.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
