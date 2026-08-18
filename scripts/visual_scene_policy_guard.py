#!/usr/bin/env python3
"""Reject policy-stale registered V2 compositions before preview/reuse.

A registered V2 scene is immutable history. When the visual pedagogy/reviewer
policy changes, byte-identical old geometry must not become the default current
candidate merely because it is technically valid. The designer must reconsider
that composition and create a new append-only scene revision unless the exact
scene has already received an independent PASS under the current visual policy.
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

from study import resolve_course  # noqa: E402
try:
    from . import scene_spec, visual_plan_v2, visual_policy, visual_review
    from .figure_assets import load_registry
    from .unit_identity import record_unit_id, resolve_unit
except ImportError:
    import scene_spec  # type: ignore
    import visual_plan_v2  # type: ignore
    import visual_policy  # type: ignore
    import visual_review  # type: ignore
    from figure_assets import load_registry  # type: ignore
    from unit_identity import record_unit_id, resolve_unit  # type: ignore


class VisualScenePolicyGuardError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _matching_current_policy_pass(course: Path, scene_id: str, scene_sha: str) -> bool:
    """Return true only for real bound PASS evidence under the current policy."""
    policy_sha = visual_policy.current_fingerprint()
    for preview_path in course.rglob("02-visual-preview.json"):
        run = preview_path.parent
        review_path = run / "02-visual-review.json"
        if not review_path.is_file():
            continue
        preview = _read_json(preview_path)
        if preview.get("visual_policy_sha256") != policy_sha:
            continue
        entry = next(
            (
                item
                for item in preview.get("entries", [])
                if isinstance(item, dict)
                and item.get("scene_id") == scene_id
                and item.get("scene_sha256") == scene_sha
            ),
            None,
        )
        if entry is None:
            continue
        try:
            binding = visual_review.bind_review_to_preview(_read_json(review_path), preview)
        except (ValueError, OSError, visual_review.VisualReviewError):
            continue
        review = binding.get("review", {})
        if review.get("visual_policy_sha256") != policy_sha:
            continue
        row = next(
            (
                item
                for item in review.get("figures", [])
                if isinstance(item, dict)
                and item.get("scene_id") == scene_id
                and item.get("attempt") == entry.get("attempt")
            ),
            None,
        )
        if row is not None and row.get("status") == "pass":
            return True
    return False


def check(course: Path, unit_value: str, plan_path: Path) -> dict[str, Any]:
    rows = visual_plan_v2.inspect_plan(course, unit_value, plan_path)
    unit_id = str(resolve_unit(course, unit_value).get("unit_id") or "")
    if not unit_id:
        raise VisualScenePolicyGuardError(f"could not resolve unit: {unit_value}")
    registry = load_registry(course)
    figures = registry.get("figures", {}) if isinstance(registry, dict) else {}
    if not isinstance(figures, dict):
        raise VisualScenePolicyGuardError("figure registry invalid")

    policy_sha = visual_policy.current_fingerprint()
    issues: list[dict[str, Any]] = []
    for row in rows:
        scene = row.get("scene")
        derived_id = str(row.get("derived_figure_id") or "")
        if not isinstance(scene, dict) or not derived_id:
            continue
        record = figures.get(derived_id)
        if not isinstance(record, dict) or record.get("origin") != "derived":
            continue
        if record_unit_id(course, record) != unit_id:
            continue
        generation = record.get("scene_generation")
        if not isinstance(generation, dict) or generation.get("schema_version") != 2:
            continue

        scene_sha = scene_spec.scene_sha256(scene)
        if str(generation.get("scene_sha256") or "") != scene_sha:
            # visual_plan_v2 already rejects changed geometry under an immutable id.
            continue
        if _matching_current_policy_pass(course, scene["id"], scene_sha):
            continue

        suggestion = f"{scene['id']}-r{policy_sha[:8]}"
        issues.append({
            "code": "registered-v2-composition-stale-under-current-policy",
            "scene_id": scene["id"],
            "scene_sha256": scene_sha,
            "derived_figure_id": derived_id,
            "required_action": "reconsider-composition-and-create-new-append-only-revision",
            "suggested_scene_id": suggestion,
            "message": (
                "This byte-identical registered V2 composition has no independent PASS under the current "
                "visual policy. Treat the old scene only as historical reference; redesign from the canonical "
                "concept under the current figures/rubric rules and use a new scene id + derived_figure_id."
            ),
        })

    return {
        "version": 1,
        "ok": not issues,
        "plan_sha256": visual_plan_v2.sha256(plan_path),
        "visual_policy_sha256": policy_sha,
        "issues": issues,
    }


def _path(value: str, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    if must_exist and not path.is_file():
        raise VisualScenePolicyGuardError(f"file not found: {value}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Reject policy-stale registered V2 scene compositions")
    ap.add_argument("--course", required=True)
    ap.add_argument("--unit", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--write", required=True)
    args = ap.parse_args()
    try:
        course = resolve_course(args.course)
        plan_path = _path(args.plan)
        report = check(course, args.unit, plan_path)
        out = _path(args.write, must_exist=False)
        _write_json(out, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1
    except (VisualScenePolicyGuardError, visual_plan_v2.VisualPlanV2Error, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
