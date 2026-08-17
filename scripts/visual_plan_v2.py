#!/usr/bin/env python3
"""Preview/review/finalize orchestrator for Visual System V2."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
try:
    from . import scene_figure, scene_spec, visual_review
    from .figure_assets import derived_key, load_registry
    from .unit_identity import record_unit_id, resolve_unit
except ImportError:
    import scene_figure  # type: ignore
    import scene_spec  # type: ignore
    import visual_review  # type: ignore
    from figure_assets import derived_key, load_registry  # type: ignore
    from unit_identity import record_unit_id, resolve_unit  # type: ignore

NEEDS = {"visual_required", "visual_helpful", "visual_not_needed"}
TREATMENTS = {"reinterpret", "preserve", "preserve+derived_sketch"}
DERIVED = {"reinterpret", "preserve+derived_sketch"}


class VisualPlanV2Error(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VisualPlanV2Error(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VisualPlanV2Error(f"must be a JSON object: {path}")
    return value


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("visuals", [])
    if isinstance(raw, dict):
        result = []
        for key, value in raw.items():
            if not isinstance(value, dict):
                raise VisualPlanV2Error(f"visuals.{key} must be object")
            row = dict(value)
            row.setdefault("concept_id", str(key))
            result.append(row)
        return result
    if isinstance(raw, list):
        if any(not isinstance(item, dict) for item in raw):
            raise VisualPlanV2Error("visuals items must be objects")
        return [dict(item) for item in raw]
    raise VisualPlanV2Error("visuals must be an array or object")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _registry_match(figures: dict[str, Any], figure_id: str) -> tuple[str, dict[str, Any]] | None:
    direct = figures.get(figure_id)
    if isinstance(direct, dict):
        return figure_id, direct
    for key, item in figures.items():
        if isinstance(item, dict) and _text(item.get("id")) == figure_id:
            return key, item
    return None


def inspect_plan(course: Path, unit_value: str, plan_path: Path) -> list[dict[str, Any]]:
    plan = _json(plan_path)
    unit_id = _text(resolve_unit(course, unit_value).get("unit_id"))
    if not unit_id:
        raise VisualPlanV2Error(f"could not resolve unit: {unit_value}")
    figures = load_registry(course).get("figures", {})
    if not isinstance(figures, dict):
        raise VisualPlanV2Error("figure registry invalid")
    selected = []
    for index, item in enumerate(_rows(plan)):
        loc = f"visuals[{index}]"
        need = _text(item.get("need"))
        if need not in NEEDS:
            raise VisualPlanV2Error(f"{loc}.need invalid")
        if need == "visual_not_needed":
            continue
        concept_id = _text(item.get("concept_id"))
        if not concept_id:
            raise VisualPlanV2Error(f"{loc}.concept_id required")
        treatment = _text(item.get("visual_treatment"))
        if treatment not in TREATMENTS:
            raise VisualPlanV2Error(f"{loc}.visual_treatment invalid")
        reason = _text(item.get("reason"))
        if not reason:
            raise VisualPlanV2Error(f"{loc}.reason required")
        row = {
            "concept_id": concept_id,
            "need": need,
            "visual_treatment": treatment,
            "reason": reason,
            "fidelity_reason": _text(item.get("fidelity_reason")),
            "source_figure_id": "",
            "source_asset": "",
        }
        source_id = _text(item.get("source_figure_id"))
        if treatment in {"preserve", "preserve+derived_sketch"}:
            if not source_id or not row["fidelity_reason"]:
                raise VisualPlanV2Error(f"{loc}: source_figure_id and fidelity_reason required for {treatment}")
            match = _registry_match(figures, source_id)
            if match is None or match[1].get("origin") != "source":
                raise VisualPlanV2Error(f"{loc}.source_figure_id must name registered source figure")
            if record_unit_id(course, match[1]) != unit_id:
                raise VisualPlanV2Error(f"{loc}.source_figure_id belongs to another unit")
            if not _text(match[1].get("asset")):
                raise VisualPlanV2Error(f"{loc}.source_figure_id has no reusable asset")
            row["source_figure_id"] = match[0]
            row["source_asset"] = _text(match[1]["asset"])
        elif source_id:
            raise VisualPlanV2Error(f"{loc}.source_figure_id only valid when source pixels are preserved")

        if treatment in DERIVED:
            spec_value = _text(item.get("scene_spec"))
            derived_id = _text(item.get("derived_figure_id"))
            based_on = item.get("based_on")
            if not spec_value or not derived_id or not isinstance(based_on, list) or not based_on:
                raise VisualPlanV2Error(f"{loc}: derived_figure_id, scene_spec and based_on are required")
            spec_rel = Path(spec_value)
            if spec_rel.is_absolute():
                raise VisualPlanV2Error(f"{loc}.scene_spec must be run-relative")
            spec_path = (plan_path.parent / spec_rel).resolve()
            scene_root = (plan_path.parent / "02-scenes").resolve()
            if not spec_path.is_relative_to(scene_root) or spec_path.suffix.lower() != ".json":
                raise VisualPlanV2Error(f"{loc}.scene_spec must stay under 02-scenes/")
            scene = scene_spec.load_scene(spec_path)
            if derived_key(derived_id) != derived_key(scene["id"]):
                raise VisualPlanV2Error(f"{loc}.derived_figure_id does not match scene id")
            if scene["visual_treatment"] != treatment:
                raise VisualPlanV2Error(f"{loc}.visual_treatment does not match scene")
            if set(map(str, based_on)) != set(scene["based_on"]):
                raise VisualPlanV2Error(f"{loc}.based_on must match scene provenance")
            if treatment == "preserve+derived_sketch" and scene.get("source_figure_id") != source_id:
                raise VisualPlanV2Error(f"{loc}.source_figure_id does not match scene companion")
            row.update({
                "derived_figure_id": derived_key(scene["id"]),
                "scene_spec": spec_rel.as_posix(),
                "scene_path": spec_path,
                "scene": scene,
                "based_on": list(map(str, based_on)),
            })
        else:
            if item.get("scene_spec") or item.get("derived_figure_id"):
                raise VisualPlanV2Error(f"{loc}: preserve must not declare a scene")
        selected.append(row)
    return selected


def preview_plan(course: Path, unit_value: str, plan_path: Path) -> dict[str, Any]:
    rows = inspect_plan(course, unit_value, plan_path)
    entries = []
    preserved = []
    for row in rows:
        if row["visual_treatment"] in DERIVED:
            entries.append(scene_figure.preview_scene(course, unit_value, row["scene"], plan_path.parent))
        else:
            preserved.append({
                "concept_id": row["concept_id"],
                "visual_treatment": "preserve",
                "source_figure_id": row["source_figure_id"],
                "asset": row["source_asset"],
            })
    return {
        "version": 1,
        "ok": all(entry.get("ok") is True for entry in entries),
        "plan_sha256": sha256(plan_path),
        "entries": entries,
        "preserved": preserved,
    }


def finalize_plan(
    course: Path,
    unit_value: str,
    plan_path: Path,
    preview_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    rows = inspect_plan(course, unit_value, plan_path)
    preview = _json(preview_path)
    if preview.get("ok") is not True or preview.get("plan_sha256") != sha256(plan_path):
        raise VisualPlanV2Error("preview is failed or stale against 02-plan.json")
    review_raw = _json(review_path)
    binding = visual_review.bind_review_to_preview(review_raw, preview)
    review = binding["review"]
    review_by_id = {row["scene_id"]: row for row in review["figures"]}
    preview_by_id = {row["scene_id"]: row for row in preview["entries"]}

    built = []
    for row in rows:
        output = {
            "concept_id": row["concept_id"],
            "visual_treatment": row["visual_treatment"],
            "source_figure_id": row.get("source_figure_id") or None,
        }
        if row["visual_treatment"] in DERIVED:
            scene_id = row["scene"]["id"]
            result = scene_figure.finalize_scene(
                course, unit_value, row["scene"], preview_by_id[scene_id], review_by_id[scene_id]
            )
            record = result["record"]
            output.update({
                "derived_figure_id": result["key"],
                "asset": record["asset"],
                "asset_sha256": record["asset_sha256"],
                "scene_sha256": record["scene_generation"]["scene_sha256"],
                "scene": record["scene_generation"]["scene"],
                "variants": record["scene_generation"]["variants"],
                "review_attempt": record["scene_generation"]["visual_review"]["attempt"],
            })
        else:
            output.update({"asset": row["source_asset"]})
        built.append(output)
    return {
        "version": 2,
        "ok": True,
        "plan_sha256": sha256(plan_path),
        "preview_sha256": sha256(preview_path),
        "visual_review_sha256": sha256(review_path),
        "vision_verified": True,
        "entries": built,
    }


def _path(value: str, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    if must_exist and not path.is_file():
        raise VisualPlanV2Error(f"file not found: {value}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Visual System V2 preview/review/finalize orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preview")
    p.add_argument("--course", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--write", required=True)
    p = sub.add_parser("finalize")
    p.add_argument("--course", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--preview", required=True)
    p.add_argument("--review", required=True)
    p.add_argument("--write", required=True)
    args = ap.parse_args()
    try:
        course = resolve_course(args.course)
        plan = _path(args.plan)
        if args.cmd == "preview":
            report = preview_plan(course, args.unit, plan)
        else:
            report = finalize_plan(course, args.unit, plan, _path(args.preview), _path(args.review))
        out = Path(args.write)
        if not out.is_absolute():
            out = (ROOT / out).resolve()
        _write(out, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1
    except (VisualPlanV2Error, scene_figure.SceneFigureError, scene_spec.SceneSpecError, visual_review.VisualReviewError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
