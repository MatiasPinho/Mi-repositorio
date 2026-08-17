#!/usr/bin/env python3
"""Seed a new V2 summary run from an older exact hash-bound visual PASS.

This is a cross-run cache, not a new review. It only reuses evidence when the
current scene spec, registered wide/narrow SVGs and a prior independent PASS all
still match byte-for-byte. The prior PNG evidence is copied into the new run and
its PASS row is mechanically rebound to those copied bytes. Normal preview,
finalize, integrity and finish gates still run afterwards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
try:
    from . import scene_spec, visual_plan_v2, visual_review
    from .course_layout import has_unit_layout, unit_root
    from .figure_assets import load_registry
    from .unit_identity import record_unit_id, resolve_unit
except ImportError:
    import scene_spec  # type: ignore
    import visual_plan_v2  # type: ignore
    import visual_review  # type: ignore
    from course_layout import has_unit_layout, unit_root  # type: ignore
    from figure_assets import load_registry  # type: ignore
    from unit_identity import record_unit_id, resolve_unit  # type: ignore


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _content_base(course: Path, unit_id: str) -> Path:
    return unit_root(course, unit_id) if has_unit_layout(course) else course


def _registered_rows(course: Path, unit_id: str, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]] | None:
    figures = load_registry(course).get("figures", {})
    if not isinstance(figures, dict):
        return None
    base = _content_base(course, unit_id)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("visual_treatment") not in visual_plan_v2.DERIVED:
            continue
        key = str(row.get("derived_figure_id") or "")
        record = figures.get(key)
        if not isinstance(record, dict) or record.get("origin") != "derived":
            return None
        if record_unit_id(course, record) != unit_id:
            return None
        if record.get("visual_treatment") != row.get("visual_treatment"):
            return None
        if set(map(str, record.get("based_on", []))) != set(map(str, row.get("based_on", []))):
            return None
        generation = record.get("scene_generation")
        if not isinstance(generation, dict) or generation.get("schema_version") != 2:
            return None
        if generation.get("scene_sha256") != scene_spec.scene_sha256(row["scene"]):
            return None
        review_meta = generation.get("visual_review")
        if not isinstance(review_meta, dict) or not review_meta.get("wide_png_sha256") or not review_meta.get("narrow_png_sha256"):
            return None
        variants = generation.get("variants")
        if not isinstance(variants, dict):
            return None
        for variant in ("wide", "narrow"):
            meta = variants.get(variant)
            if not isinstance(meta, dict):
                return None
            asset = str(meta.get("asset") or "")
            path = (base / asset).resolve()
            if not asset or not path.is_file() or _sha(path) != meta.get("asset_sha256"):
                return None
        result[row["scene"]["id"]] = record
    return result


def _candidate_runs(course: Path, current_run: Path) -> list[Path]:
    candidates: list[Path] = []
    for preview in course.rglob("02-visual-preview.json"):
        run = preview.parent.resolve()
        if run == current_run.resolve() or ".study" not in run.parts or "runs" not in run.parts:
            continue
        if (run / "02-visual-review.json").is_file():
            candidates.append(run)
    return sorted(candidates, key=lambda path: (path / "02-visual-review.json").stat().st_mtime, reverse=True)


def _matching_prior(
    course: Path,
    current_run: Path,
    rows: list[dict[str, Any]],
    registered: dict[str, dict[str, Any]],
) -> tuple[Path, dict[str, Any], dict[str, Any]] | None:
    wanted = {row["scene"]["id"]: row for row in rows if row.get("visual_treatment") in visual_plan_v2.DERIVED}
    if not wanted:
        return None
    for run in _candidate_runs(course, current_run):
        try:
            preview = _read(run / "02-visual-preview.json")
            review_raw = _read(run / "02-visual-review.json")
            binding = visual_review.bind_review_to_preview(review_raw, preview)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, visual_review.VisualReviewError):
            continue
        by_id = {
            str(item.get("scene_id") or ""): item
            for item in preview.get("entries", [])
            if isinstance(item, dict) and item.get("scene_id")
        }
        if not set(wanted).issubset(by_id):
            continue
        ok = True
        for scene_id, row in wanted.items():
            entry = by_id[scene_id]
            record = registered.get(scene_id, {})
            generation = record.get("scene_generation", {}) if isinstance(record, dict) else {}
            if entry.get("scene_sha256") != scene_spec.scene_sha256(row["scene"]):
                ok = False
                break
            variants = entry.get("variants", {})
            registered_variants = generation.get("variants", {}) if isinstance(generation, dict) else {}
            for variant in ("wide", "narrow"):
                pv = variants.get(variant, {}) if isinstance(variants, dict) else {}
                rv = registered_variants.get(variant, {}) if isinstance(registered_variants, dict) else {}
                svg = Path(str(pv.get("svg") or ""))
                png = Path(str(pv.get("png") or ""))
                if (
                    not svg.is_file()
                    or not png.is_file()
                    or _sha(svg) != pv.get("svg_sha256")
                    or _sha(png) != pv.get("png_sha256")
                    or pv.get("svg_sha256") != rv.get("asset_sha256")
                ):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return run, preview, binding["review"]
    return None


def prepare(course: Path, unit_value: str, plan_path: Path, review_write: Path) -> dict[str, Any]:
    current_run = plan_path.parent.resolve()
    rows = visual_plan_v2.inspect_plan(course, unit_value, plan_path)
    derived = [row for row in rows if row.get("visual_treatment") in visual_plan_v2.DERIVED]
    unit_id = str(resolve_unit(course, unit_value).get("unit_id") or "")
    if not derived:
        return {"version": 1, "ok": True, "all_reused": False, "reason": "no-derived-scenes", "scene_ids": []}
    registered = _registered_rows(course, unit_id, rows)
    if registered is None or set(registered) != {row["scene"]["id"] for row in derived}:
        return {"version": 1, "ok": True, "all_reused": False, "reason": "registered-scene-or-hash-mismatch", "scene_ids": []}
    prior = _matching_prior(course, current_run, rows, registered)
    if prior is None:
        return {"version": 1, "ok": True, "all_reused": False, "reason": "no-prior-hash-bound-pass", "scene_ids": []}

    prior_run, preview, review = prior
    preview_by_id = {row["scene_id"]: row for row in preview["entries"] if isinstance(row, dict) and row.get("scene_id")}
    review_by_id = {row["scene_id"]: row for row in review["figures"]}
    seeded_rows: list[dict[str, Any]] = []

    for row in derived:
        scene_id = row["scene"]["id"]
        source = preview_by_id[scene_id]
        target_dir = current_run / "02-visual-attempts" / scene_id / "01"
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=False)

        scene_path = target_dir / "scene.json"
        scene_path.write_bytes(scene_spec.scene_bytes(row["scene"]))
        old_preflight = Path(str(source.get("preflight") or ""))
        preflight_path = target_dir / "preflight.json"
        if old_preflight.is_file():
            shutil.copy2(old_preflight, preflight_path)
        else:
            _write(preflight_path, {"ok": True, "reused_from": str(prior_run)})

        variants: dict[str, Any] = {}
        for variant in ("wide", "narrow"):
            old = source["variants"][variant]
            old_svg = Path(old["svg"])
            old_png = Path(old["png"])
            svg_path = target_dir / old_svg.name
            png_path = target_dir / f"{variant}.png"
            shutil.copy2(old_svg, svg_path)
            shutil.copy2(old_png, png_path)
            variants[variant] = {
                **{key: value for key, value in old.items() if key not in {"svg", "png"}},
                "svg": str(svg_path),
                "png": str(png_path),
                "svg_sha256": _sha(svg_path),
                "png_sha256": _sha(png_path),
            }

        seeded_preview = {
            "version": 1,
            "ok": True,
            "unit_id": unit_id,
            "scene_id": scene_id,
            "scene_sha256": scene_spec.scene_sha256(row["scene"]),
            "scene_file": str(scene_path),
            "attempt": 1,
            "attempt_dir": str(target_dir),
            "reused": True,
            "reused_cross_run": True,
            "reused_from_run": str(prior_run),
            "preflight": str(preflight_path),
            "variants": variants,
            "review_reuse_key": {
                "scene_sha256": scene_spec.scene_sha256(row["scene"]),
                "wide_png_sha256": variants["wide"]["png_sha256"],
                "narrow_png_sha256": variants["narrow"]["png_sha256"],
            },
        }
        _write(target_dir / "preview.json", seeded_preview)

        old_review = review_by_id[scene_id]
        inspected = []
        for variant in ("wide", "narrow"):
            inspected.append({
                "variant": variant,
                "file": variants[variant]["png"],
                "sha256": variants[variant]["png_sha256"],
            })
        seeded_rows.append({
            **old_review,
            "attempt": 1,
            "inspected": inspected,
        })

    seeded_review = {
        "version": 1,
        "vision_verified": True,
        "reviewer": review["reviewer"],
        "figures": seeded_rows,
    }
    # Validate before exposing it as current-run evidence.
    visual_review.validate_review(seeded_review)
    _write(review_write, seeded_review)
    return {
        "version": 1,
        "ok": True,
        "all_reused": True,
        "reason": "prior-hash-bound-pass-reused",
        "prior_run": str(prior_run),
        "scene_ids": [row["scene"]["id"] for row in derived],
        "review_file": str(review_write),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Reuse an exact prior V2 visual PASS in a new summary run")
    ap.add_argument("--course", required=True)
    ap.add_argument("--unit", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--review-write", required=True)
    ap.add_argument("--write", required=True)
    args = ap.parse_args()
    try:
        course = resolve_course(args.course)
        plan = Path(args.plan).resolve()
        report = prepare(course, args.unit, plan, Path(args.review_write).resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, visual_plan_v2.VisualPlanV2Error, visual_review.VisualReviewError) as exc:
        report = {"version": 1, "ok": False, "all_reused": False, "reason": "reuse-error", "error": str(exc)}
    _write(Path(args.write).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
