#!/usr/bin/env python3
"""Unit-scoped visual-build entrypoint for guarded Hybrid V1 summaries.

Legacy figure registration loads a merged V4 registry and, when saved without an
explicit unit, can rewrite every unit registry.  During `/resumen` only the
resolved unit is an allowed write boundary.  This entrypoint temporarily
replaces the registry saver with a collision-safe unit-scoped writer, then
delegates all normal lock/build/metadata checks to ``resumen_guard``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import figure_assets, illustration_figure, resumen_guard  # noqa: E402
from scripts.unit_identity import record_unit_id  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Unit-scoped guarded Hybrid V1 visual build")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()

    try:
        run = resumen_guard._run(args.run)
        course, unit_id, _base = resumen_guard._context(run)
        figures_path = resumen_guard._figure_registry_path(run)
        before = resumen_guard.load(figures_path, {})
        if not isinstance(before, dict) or not isinstance(before.get("figures", {}), dict):
            raise resumen_guard.GuardError("active unit figures registry is invalid")
        before_meta = resumen_guard._root_metadata(before)

        original_figure_save = figure_assets.save_registry
        original_illustration_save = illustration_figure.save_registry

        def save_active_unit(course_value: Path, data: dict[str, Any], unit: str = "") -> None:
            # Explicit callers retain their original behavior.  The problematic
            # legacy path is the implicit merged save used by derived generators.
            if unit:
                original_figure_save(course_value, data, unit)
                return
            rows = data.get("figures", {}) if isinstance(data, dict) else {}
            if not isinstance(rows, dict):
                raise resumen_guard.GuardError("merged figures registry has invalid rows")
            scoped = {
                key: row
                for key, row in rows.items()
                if isinstance(row, dict) and record_unit_id(course, row) == unit_id
            }
            document = dict(before_meta)
            document["version"] = max(
                int(before.get("version", 2) or 2),
                int(data.get("version", 2) or 2),
            )
            document["figures"] = scoped
            resumen_guard.save(figures_path, document)

        figure_assets.save_registry = save_active_unit  # type: ignore[assignment]
        illustration_figure.save_registry = save_active_unit  # type: ignore[assignment]
        try:
            resumen_guard.cmd_build(argparse.Namespace(run=str(run)))
        finally:
            figure_assets.save_registry = original_figure_save  # type: ignore[assignment]
            illustration_figure.save_registry = original_illustration_save  # type: ignore[assignment]
        return 0
    except resumen_guard.GuardError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
