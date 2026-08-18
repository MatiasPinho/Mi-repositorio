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
    from . import scene_figure, scene_render, scene_spec, visual_policy, visual_review
    from .course_layout import has_unit_layout, unit_root
    from .figure_assets import derived_key, load_registry
    from .unit_identity import record_unit_id, resolve_unit
except ImportError:
    import scene_figure  # type: ignore
    import scene_render  # type: ignore
    import scene_spec  # type: ignore
    import visual_policy  # type: ignore
    import visual_review  # type: ignore
    from course_layout import has_unit_layout, unit_root  # type: ignore
    from figure_assets import derived_key, load_registry  # type: ignore
    from unit_identity import record_unit_id, resolve_unit  # type: ignore

NEEDS = {"visual_required", "visual_helpful", "visual_not_needed"}
TREATMENTS = {"reinterpret", "preserve", "preserve+derived_sketch"}
DERIVED = {"reinterpret", "preserve+derived_sketch"}
FINALIZER_ID = "visual-plan-v2-finalize-v2"


class VisualPlanV2Error(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_sha(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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


def _content_base(course: Path, unit_id: str) -> Path:
    return unit_root(course, unit_id) if has_unit_layout(course) else course


def _asset_ok(base: Path, asset: str, digest: Any) -> bool:
    if not asset:
        return False
    path = (base / asset).resolve()
    if not path.is_file():
        return False
    return not digest or sha256(path) == str(digest)


def _assert_registered_v2_scene_is_same_revision(
    course: Path,
    unit_id: str,
    figures: dict[str, Any],
    *,
    loc: str,
    scene: dict[str, Any],
) -> None:
    """Keep derived V2 revisions append-only instead of overwriting old pixels.

    Re-reviewing an identical registered scene under a newer policy is allowed.
    Changing its geometry/semantics under the same id is not: the repaired scene
    must receive a new id so the old reviewed asset remains immutable history.
    """
    key = derived_key(scene["id"])
    match = _registry_match(figures, key)
    if match is None:
        return
    _, record = match
    if record.get("origin") != "derived" or record_unit_id(course, record) != unit_id:
        return
    generation = record.get("scene_generation")
    if not isinstance(generation, dict) or generation.get("schema_version") != 2:
        return
    old_sha = _text(generation.get("scene_sha256"))
    new_sha = scene_spec.scene_sha256(scene)
    if old_sha == new_sha:
        return
    suggestion = f"{scene['id']}-r{visual_policy.current_fingerprint()[:8]}"
    raise VisualPlanV2Error(
        f"{loc}: registered V2 scene id {scene['id']} already belongs to a different immutable scene; "
        f"use a new scene id + derived_figure_id for the repair (for example {suggestion})"
    )


def _registered_derived_reuse(
    course: Path,
    unit_id: str,
    figures: dict[str, Any],
    *,
    loc: str,
    treatment: str,
    derived_id: str,
    based_on: list[str],
    source_id: str,
) -> dict[str, Any]:
    """Validate an immutable registered legacy deterministic sketch.

    Legacy V1 derived figures can be reused as immutable registered assets in a
    mixed V2 run. Registered V2 scenes deliberately cannot use this shortcut:
    they need a current run-local scene_spec so cross-run PASS reuse can bind the
    exact current scene plus prior independently reviewed PNG evidence.
    """
    key = derived_key(derived_id)
    match = _registry_match(figures, key)
    if match is None:
        raise VisualPlanV2Error(
            f"{loc}.scene_spec required for a new derived figure; registered figure not found: {key}"
        )
    key, record = match
    if record.get("origin") != "derived":
        raise VisualPlanV2Error(f"{loc}.derived_figure_id must identify a derived figure")
    if record_unit_id(course, record) != unit_id:
        raise VisualPlanV2Error(f"{loc}.derived_figure_id belongs to another unit")
    if _text(record.get("visual_treatment")) != treatment:
        raise VisualPlanV2Error(f"{loc}.visual_treatment does not match registered derived figure")
    if set(map(str, record.get("based_on", []))) != set(based_on):
        raise VisualPlanV2Error(f"{loc}.based_on does not match registered derived provenance")
    if treatment == "preserve+derived_sketch" and _text(record.get("source_figure_id")) != source_id:
        raise VisualPlanV2Error(f"{loc}.source_figure_id does not match registered derived companion")

    base = _content_base(course, unit_id)
    asset = _text(record.get("asset"))
    if not _asset_ok(base, asset, record.get("asset_sha256")):
        raise VisualPlanV2Error(f"{loc}.derived_figure_id asset missing or hash-mismatched")

    scene_generation = record.get("scene_generation")
    if isinstance(scene_generation, dict) and scene_generation.get("schema_version") == 2:
        raise VisualPlanV2Error(
            f"{loc}.scene_spec required for registered V2 reuse; materialize the exact registered "
            "scene under the current run's 02-scenes/ so prior PASS evidence can be hash-bound"
        )

    generation = record.get("generation")
    if not isinstance(generation, dict) or generation.get("method") != "deterministic-svg":
        raise VisualPlanV2Error(f"{loc}.registered derived figure has unsupported generation metadata")
    spec_rel = _text(generation.get("spec"))
    spec_hash = _text(generation.get("spec_sha256"))
    if spec_rel:
        spec_path = (base / spec_rel).resolve()
        if not spec_path.is_file() or (spec_hash and sha256(spec_path) != spec_hash):
            raise VisualPlanV2Error(f"{loc}.registered legacy sketch spec missing or changed")
    return {
        "derived_figure_id": key,
        "based_on": based_on,
        "reuse_registered": True,
        "reuse_kind": "legacy",
        "registered_asset": asset,
        "registered_asset_sha256": _text(record.get("asset_sha256")),
    }


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
            based_on_raw = item.get("based_on")
            if not derived_id or not isinstance(based_on_raw, list) or not based_on_raw:
                raise VisualPlanV2Error(f"{loc}: derived_figure_id and based_on are required")
            based_on = list(map(str, based_on_raw))
            if spec_value:
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
                if set(based_on) != set(scene["based_on"]):
                    raise VisualPlanV2Error(f"{loc}.based_on must match scene provenance")
                if treatment == "preserve+derived_sketch" and scene.get("source_figure_id") != source_id:
                    raise VisualPlanV2Error(f"{loc}.source_figure_id does not match scene companion")
                _assert_registered_v2_scene_is_same_revision(
                    course, unit_id, figures, loc=loc, scene=scene
                )
                row.update({
                    "derived_figure_id": derived_key(scene["id"]),
                    "scene_spec": spec_rel.as_posix(),
                    "scene_path": spec_path,
                    "scene": scene,
                    "based_on": based_on,
                    "reuse_registered": False,
                    "reuse_kind": None,
                })
            else:
                row.update(_registered_derived_reuse(
                    course,
                    unit_id,
                    figures,
                    loc=loc,
                    treatment=treatment,
                    derived_id=derived_id,
                    based_on=based_on,
                    source_id=row["source_figure_id"],
                ))
        else:
            if item.get("scene_spec") or item.get("derived_figure_id"):
                raise VisualPlanV2Error(f"{loc}: preserve must not declare a scene")
        selected.append(row)
    return selected


def preview_plan(course: Path, unit_value: str, plan_path: Path) -> dict[str, Any]:
    rows = inspect_plan(course, unit_value, plan_path)
    entries = []
    preserved = []
    reused_registered = []
    for row in rows:
        if row["visual_treatment"] in DERIVED and not row.get("reuse_registered"):
            entries.append(scene_figure.preview_scene(course, unit_value, row["scene"], plan_path.parent))
        elif row.get("reuse_registered"):
            reused_registered.append({
                "concept_id": row["concept_id"],
                "visual_treatment": row["visual_treatment"],
                "derived_figure_id": row["derived_figure_id"],
                "source_figure_id": row.get("source_figure_id") or None,
                "asset": row["registered_asset"],
                "asset_sha256": row["registered_asset_sha256"],
                "reuse_kind": row["reuse_kind"],
            })
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
        "visual_policy_sha256": visual_policy.current_fingerprint(),
        "entries": entries,
        "preserved": preserved,
        "reused_registered": reused_registered,
    }


def _require_current_policy(preview: dict[str, Any]) -> str:
    current = visual_policy.current_fingerprint()
    if preview.get("visual_policy_sha256") != current:
        raise VisualPlanV2Error("preview visual policy is missing or stale against current figure/rubric rules")
    return current


def _verified_scene_output(
    course: Path,
    unit_id: str,
    row: dict[str, Any],
    preview_row: dict[str, Any],
    review_row: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    scene = row["scene"]
    scene_id = scene["id"]
    key = row["derived_figure_id"]
    record = figures.get(key)
    if not isinstance(record, dict) or record.get("origin") != "derived":
        raise VisualPlanV2Error(f"finalized scene not registered: {key}")
    if record_unit_id(course, record) != unit_id:
        raise VisualPlanV2Error(f"finalized scene belongs to another unit: {key}")
    if record.get("visual_treatment") != row["visual_treatment"]:
        raise VisualPlanV2Error(f"finalized scene treatment mismatch: {key}")
    if set(map(str, record.get("based_on", []))) != set(map(str, row.get("based_on", []))):
        raise VisualPlanV2Error(f"finalized scene provenance mismatch: {key}")

    generation = record.get("scene_generation")
    if not isinstance(generation, dict):
        raise VisualPlanV2Error(f"finalized scene generation missing: {key}")
    if generation.get("method") != "deterministic-scene-svg" or generation.get("schema_version") != 2:
        raise VisualPlanV2Error(f"finalized scene generation invalid: {key}")
    scene_sha = scene_spec.scene_sha256(scene)
    if generation.get("scene_sha256") != scene_sha or preview_row.get("scene_sha256") != scene_sha:
        raise VisualPlanV2Error(f"finalized scene hash mismatch: {key}")

    base = _content_base(course, unit_id)
    scene_rel = _text(generation.get("scene"))
    scene_path = (base / scene_rel).resolve() if scene_rel else None
    if scene_path is None or not scene_path.is_file() or sha256(scene_path) != scene_sha:
        raise VisualPlanV2Error(f"finalized scene spec missing or changed: {key}")

    narrow_name = f"{scene_id}-narrow.svg"
    rendered = {
        "wide": scene_render.render_variant(scene, "wide", narrow_asset=narrow_name)[0],
        "narrow": scene_render.render_variant(scene, "narrow")[0],
    }
    variants = generation.get("variants")
    if not isinstance(variants, dict):
        raise VisualPlanV2Error(f"finalized scene variants missing: {key}")
    for variant in ("wide", "narrow"):
        rendered_sha = hashlib.sha256(rendered[variant]).hexdigest()
        preview_variant = preview_row.get("variants", {}).get(variant, {})
        registered_variant = variants.get(variant, {})
        if preview_variant.get("svg_sha256") != rendered_sha:
            raise VisualPlanV2Error(f"{scene_id}:{variant}: finalizer replay differs from reviewed SVG")
        if not isinstance(registered_variant, dict) or registered_variant.get("asset_sha256") != rendered_sha:
            raise VisualPlanV2Error(f"{scene_id}:{variant}: registered asset differs from finalizer replay")
        asset = _text(registered_variant.get("asset"))
        asset_path = (base / asset).resolve() if asset else None
        if asset_path is None or not asset_path.is_file() or sha256(asset_path) != rendered_sha:
            raise VisualPlanV2Error(f"{scene_id}:{variant}: registered finalized asset missing or changed")

    inspected = {
        item["variant"]: item
        for item in review_row.get("inspected", [])
        if isinstance(item, dict) and item.get("variant") in {"wide", "narrow"}
    }
    if set(inspected) != {"wide", "narrow"}:
        raise VisualPlanV2Error(f"{scene_id}: current review bindings incomplete")

    return {
        "concept_id": row["concept_id"],
        "visual_treatment": row["visual_treatment"],
        "source_figure_id": row.get("source_figure_id") or None,
        "derived_figure_id": key,
        "asset": record["asset"],
        "asset_sha256": record["asset_sha256"],
        "scene_sha256": scene_sha,
        "scene": scene_rel,
        "variants": variants,
        "review_attempt": review_row["attempt"],
        "review_png_sha256": {
            "wide": inspected["wide"]["sha256"],
            "narrow": inspected["narrow"]["sha256"],
        },
    }


def expected_build_report(
    course: Path,
    unit_value: str,
    plan_path: Path,
    preview_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    """Reconstruct the only acceptable V2 build report without mutating state."""
    rows = inspect_plan(course, unit_value, plan_path)
    preview = _json(preview_path)
    if preview.get("ok") is not True or preview.get("plan_sha256") != sha256(plan_path):
        raise VisualPlanV2Error("preview is failed or stale against 02-plan.json")
    policy_sha = _require_current_policy(preview)
    review_raw = _json(review_path)
    binding = visual_review.bind_review_to_preview(review_raw, preview)
    review = binding["review"]
    if review.get("visual_policy_sha256") != policy_sha:
        raise VisualPlanV2Error("review visual policy is stale")
    review_by_id = {item["scene_id"]: item for item in review["figures"]}
    preview_by_id = {item["scene_id"]: item for item in preview["entries"]}
    figures = load_registry(course).get("figures", {})
    if not isinstance(figures, dict):
        raise VisualPlanV2Error("figure registry invalid during finalization replay")
    unit_id = _text(resolve_unit(course, unit_value).get("unit_id"))
    if not unit_id:
        raise VisualPlanV2Error(f"could not resolve unit: {unit_value}")

    built: list[dict[str, Any]] = []
    for row in rows:
        if row["visual_treatment"] in DERIVED and not row.get("reuse_registered"):
            scene_id = row["scene"]["id"]
            if scene_id not in preview_by_id or scene_id not in review_by_id:
                raise VisualPlanV2Error(f"finalized current scene missing preview/review: {scene_id}")
            built.append(_verified_scene_output(
                course, unit_id, row, preview_by_id[scene_id], review_by_id[scene_id], figures
            ))
        elif row.get("reuse_registered"):
            record = figures.get(row["derived_figure_id"])
            if not isinstance(record, dict):
                raise VisualPlanV2Error(f"registered figure disappeared during finalize: {row['derived_figure_id']}")
            built.append({
                "concept_id": row["concept_id"],
                "visual_treatment": row["visual_treatment"],
                "source_figure_id": row.get("source_figure_id") or None,
                "derived_figure_id": row["derived_figure_id"],
                "asset": record["asset"],
                "asset_sha256": record.get("asset_sha256"),
                "reused_registered": True,
                "reuse_kind": row["reuse_kind"],
            })
        else:
            built.append({
                "concept_id": row["concept_id"],
                "visual_treatment": row["visual_treatment"],
                "source_figure_id": row.get("source_figure_id") or None,
                "asset": row["source_asset"],
            })

    report: dict[str, Any] = {
        "version": 2,
        "ok": True,
        "producer": FINALIZER_ID,
        "plan_sha256": sha256(plan_path),
        "preview_sha256": sha256(preview_path),
        "visual_review_sha256": sha256(review_path),
        "visual_policy_sha256": policy_sha,
        "vision_verified": True,
        "entries": built,
    }
    report["finalization_attestation_sha256"] = _json_sha(report)
    return report


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
    _require_current_policy(preview)
    review_raw = _json(review_path)
    binding = visual_review.bind_review_to_preview(review_raw, preview)
    review = binding["review"]
    review_by_id = {row["scene_id"]: row for row in review["figures"]}
    preview_by_id = {row["scene_id"]: row for row in preview["entries"]}
    figures = load_registry(course).get("figures", {})

    for row in rows:
        if row["visual_treatment"] in DERIVED and not row.get("reuse_registered"):
            scene_id = row["scene"]["id"]
            scene_figure.finalize_scene(
                course, unit_value, row["scene"], preview_by_id[scene_id], review_by_id[scene_id]
            )
        elif row.get("reuse_registered"):
            record = figures.get(row["derived_figure_id"])
            if not isinstance(record, dict):
                raise VisualPlanV2Error(f"registered figure disappeared during finalize: {row['derived_figure_id']}")

    # Build is generated only after the mutating finalizer succeeded, then
    # reconstructed from canonical state. Integrity performs the same pure
    # reconstruction later, so hand-writing a superficially plausible JSON is
    # not a substitute for successful finalization.
    return expected_build_report(course, unit_value, plan_path, preview_path, review_path)


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
