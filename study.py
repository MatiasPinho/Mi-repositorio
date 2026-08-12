#!/usr/bin/env python3
"""Stable CLI entrypoint for University Study System.

The command implementation lives in :mod:`scripts.study_cli`. Material indexing
is injected from the canonical ``scripts.sync_materials`` module so the CLI,
status/reset paths, Engine QA, and the direct deterministic script all share one
implementation and one idempotence contract.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import study_cli as _impl
from scripts.study_cli import *  # noqa: F401,F403
from scripts import sync_materials as _materials

# ``scripts.study_cli`` was extracted from the historical root entrypoint. Keep
# its root-sensitive constants anchored at the repository root before any
# command executes.
ROOT = Path(__file__).resolve().parent
_impl.ROOT = ROOT
_impl.COURSES_DIR = ROOT / "materias"
_impl.SCRIPTS_DIR = ROOT / "scripts"


def material_kind(relative):
    return _materials.material_kind(relative)


def materials_index_path(course, unit: str = ""):
    return _materials.materials_index_path(course, unit)


def scan_materials(course, unit: str = ""):
    try:
        return _materials.scan_materials(course, unit)
    except (json.JSONDecodeError, OSError) as exc:
        raise _impl.CliError(f"No se pudo leer el índice de materiales: {exc}") from exc


def cmd_materials_scan(args) -> None:
    course = _impl.resolve_course(args.course)
    selected_unit = getattr(args, "unit", None) or ""
    try:
        current, diff, _written = _materials.index_materials(
            course,
            selected_unit,
            write=bool(args.commit),
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise _impl.CliError(f"No se pudo actualizar el índice de materiales: {exc}") from exc

    transcript_count = sum(1 for meta in current.values() if meta.get("kind") == "transcript")

    # --json is a machine contract: stdout contains exactly one JSON document.
    if args.json:
        print(json.dumps(diff, ensure_ascii=False, indent=2))
        return

    print(f"Materiales - {_impl.course_display_name(course)}")
    print(f"  Total:       {diff['total']}")
    print(f"  Nuevos:      {len(diff['added'])}")
    print(f"  Modificados: {len(diff['changed'])}")
    print(f"  Eliminados:  {len(diff['removed'])}")
    if transcript_count:
        print(f"  Transcripciones: {transcript_count}")
    for label, key in (("NUEVOS", "added"), ("MODIFICADOS", "changed"), ("ELIMINADOS", "removed")):
        if diff[key]:
            print(f"\n{label}")
            for item in diff[key]:
                print(f"  - {item}")
    if args.commit:
        print("\nEstado actual de materiales registrado como procesado.")


# The extracted implementation resolves these globals at call time. Patching
# them here makes every caller use the canonical material-index module, including
# status/reset and parser-dispatched ``materials scan``.
_impl.material_kind = material_kind
_impl.materials_index_path = materials_index_path
_impl.scan_materials = scan_materials
_impl.cmd_materials_scan = cmd_materials_scan


if __name__ == "__main__":
    _impl.main()
