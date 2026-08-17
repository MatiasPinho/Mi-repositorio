#!/usr/bin/env python3
"""Pre-publication integrity gate for Visual System V2 artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
try:
    from . import artifact_integrity, scene_spec, visual_plan_v2, visual_review
    from .course_layout import has_unit_layout, unit_root
    from .figure_assets import load_registry
    from .unit_identity import record_unit_id, resolve_unit
except ImportError:
    import artifact_integrity  # type: ignore
    import scene_spec  # type: ignore
    import visual_plan_v2  # type: ignore
    import visual_review  # type: ignore
    from course_layout import has_unit_layout, unit_root  # type: ignore
    from figure_assets import load_registry  # type: ignore
    from unit_identity import record_unit_id, resolve_unit  # type: ignore


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _markdown_sources(md: Path) -> list[str]:
    text = md.read_text(encoding="utf-8")
    return [src for _alt, src in re.findall(r"!\[([^\]]*)\]\(([^)\s]+)", text)]


def _used_ids(course: Path, scope: str, md: Path) -> tuple[set[str], list[str]]:
    unit_id = str(resolve_unit(course, scope).get("unit_id") or "")
    base = unit_root(course, unit_id) if unit_id and has_unit_layout(course) else course
    figures = load_registry(course).get("figures", {})
    by_asset = {
        str(row.get("asset")): key
        for key, row in figures.items()
        if isinstance(row, dict) and record_unit_id(course, row) == unit_id and row.get("asset")
    }
    used: set[str] = set()
    issues: list[str] = []
    for src in _markdown_sources(md):
        if re.match(r"^[a-z]+://", src) or src.startswith("data:"):
            continue
        target = (md.parent / src).resolve()
        try:
            rel = target.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
        if rel.startswith("assets/figures/"):
            key = by_asset.get(rel)
            if key:
                used.add(key)
            else:
                issues.append(f"unregistered-figure-asset:{rel}")
    return used, issues


def _html_scene_sources(html_path: Path) -> dict[str, dict[str, str]]:
    text = html_path.read_text(encoding="utf-8")
    rows: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r'<picture\b[^>]*data-scene-id="([^"]+)"[^>]*>\s*'
        r'<source\b[^>]*srcset="([^"]+)"[^>]*>\s*'
        r'<img\b[^>]*src="([^"]+)"[^>]*>\s*</picture>',
        re.I,
    )
    for scene_id, narrow, wide in pattern.findall(text):
        rows[scene_id] = {"wide": wide, "narrow": narrow}
    return rows


def _scene_html_variant_issues(
    html_path: Path,
    content_base: Path,
    derived_id: str,
    variant: str,
    src: str,
    variant_meta: dict[str, Any],
) -> list[str]:
    """Bind final responsive markup to the exact registered reviewed variant."""
    issues: list[str] = []
    asset = str(variant_meta.get("asset") or "")
    expected = (content_base / asset).resolve() if asset else None
    actual = (html_path.parent / src).resolve()
    if expected is None or actual != expected:
        issues.append(f"scene-html-variant-mismatch:{derived_id}:{variant}:{src}")
        return issues
    if not actual.is_file():
        issues.append(f"scene-html-variant-broken:{derived_id}:{variant}:{src}")
        return issues
    if sha256(actual) != variant_meta.get("asset_sha256"):
        issues.append(f"scene-html-variant-hash-mismatch:{derived_id}:{variant}:{src}")
    return issues


def _legacy_reuse_issues(
    course: Path,
    scope: str,
    row: dict[str, Any],
    record: dict[str, Any] | None,
) -> list[str]:
    """Validate an already-registered V1 sketch used inside a mixed V2 run."""
    derived_id = row["derived_figure_id"]
    issues: list[str] = []
    if not isinstance(record, dict) or record.get("origin") != "derived":
        return [f"planned-legacy-derived-not-registered:{derived_id}"]
    if record.get("visual_treatment") != row["visual_treatment"]:
        issues.append(f"planned-legacy-treatment-mismatch:{derived_id}")
    if set(map(str, record.get("based_on", []))) != set(map(str, row.get("based_on", []))):
        issues.append(f"planned-legacy-provenance-mismatch:{derived_id}")
    if row["visual_treatment"] == "preserve+derived_sketch" and record.get("source_figure_id") != row.get("source_figure_id"):
        issues.append(f"planned-legacy-source-mismatch:{derived_id}")
    generation = record.get("generation")
    if not isinstance(generation, dict) or generation.get("method") != "deterministic-svg":
        issues.append(f"planned-legacy-generation-invalid:{derived_id}")
        return issues
    unit_id = str(resolve_unit(course, scope).get("unit_id") or "")
    content_base = unit_root(course, unit_id) if unit_id and has_unit_layout(course) else course
    asset = str(record.get("asset") or "")
    asset_path = (content_base / asset).resolve() if asset else None
    if asset_path is None or not asset_path.is_file() or (
        record.get("asset_sha256") and sha256(asset_path) != record.get("asset_sha256")
    ):
        issues.append(f"planned-legacy-asset-missing-or-changed:{derived_id}")
    spec = str(generation.get("spec") or "")
    if spec:
        spec_path = (content_base / spec).resolve()
        if not spec_path.is_file() or (
            generation.get("spec_sha256") and sha256(spec_path) != generation.get("spec_sha256")
        ):
            issues.append(f"planned-legacy-spec-missing-or-changed:{derived_id}")
    return issues


def check(
    course: Path,
    md_path: Path,
    html_path: Path,
    scope: str,
    artifact_type: str,
    plan_path: Path,
    preview_path: Path,
    review_path: Path,
    build_path: Path,
) -> dict[str, Any]:
    base = artifact_integrity.check(course, md_path, html_path, scope, artifact_type, None)
    issues = list(base.get("issues", []))
    try:
        rows = visual_plan_v2.inspect_plan(course, scope, plan_path)
    except Exception as exc:
        rows = []
        issues.append(f"visual-v2-plan-invalid:{exc}")

    preview = _json(preview_path)
    review = _json(review_path)
    build = _json(build_path)
    if preview.get("ok") is not True or preview.get("plan_sha256") != sha256(plan_path):
        issues.append("visual-v2-preview-missing-failed-or-stale")
    try:
        visual_review.bind_review_to_preview(review, preview)
    except Exception as exc:
        issues.append(f"visual-v2-review-invalid:{exc}")
    if build.get("ok") is not True or build.get("version") != 2 or build.get("vision_verified") is not True:
        issues.append("visual-v2-build-invalid")
    else:
        if build.get("plan_sha256") != sha256(plan_path):
            issues.append("visual-v2-build-plan-stale")
        if build.get("preview_sha256") != sha256(preview_path):
            issues.append("visual-v2-build-preview-stale")
        if build.get("visual_review_sha256") != sha256(review_path):
            issues.append("visual-v2-build-review-stale")

    used, used_issues = _used_ids(course, scope, md_path)
    issues.extend(used_issues)
    figures = load_registry(course).get("figures", {})
    html_scenes = _html_scene_sources(html_path)
    planned_scene_ids: set[str] = set()

    for row in rows:
        treatment = row["visual_treatment"]
        concept = row["concept_id"]
        if treatment == "preserve":
            if row["source_figure_id"] not in used:
                issues.append(f"planned-preserve-source-not-used:{concept}:{row['source_figure_id']}")
            continue
        derived_id = row["derived_figure_id"]
        record = figures.get(derived_id)
        if derived_id not in used:
            issues.append(f"planned-scene-not-used:{concept}:{derived_id}")
        if treatment == "preserve+derived_sketch" and row["source_figure_id"] not in used:
            issues.append(f"planned-companion-source-not-used:{concept}:{row['source_figure_id']}")

        if row.get("reuse_registered") and row.get("reuse_kind") == "legacy":
            issues.extend(_legacy_reuse_issues(course, scope, row, record if isinstance(record, dict) else None))
            continue

        planned_scene_ids.add(derived_id)
        if not isinstance(record, dict) or record.get("origin") != "derived":
            issues.append(f"planned-scene-not-registered:{derived_id}")
            continue
        generation = record.get("scene_generation")
        if not isinstance(generation, dict) or generation.get("method") != "deterministic-scene-svg" or generation.get("schema_version") != 2:
            issues.append(f"scene-generation-metadata-invalid:{derived_id}")
            continue
        scene_file = generation.get("scene")
        unit_id = str(resolve_unit(course, scope).get("unit_id") or "")
        content_base = unit_root(course, unit_id) if unit_id and has_unit_layout(course) else course
        scene_path = (content_base / str(scene_file)).resolve()
        if not scene_path.is_file() or sha256(scene_path) != generation.get("scene_sha256"):
            issues.append(f"scene-spec-missing-or-changed:{derived_id}")
            continue
        try:
            canonical = scene_spec.load_scene(scene_path)
        except Exception as exc:
            issues.append(f"scene-spec-invalid:{derived_id}:{exc}")
            continue
        if canonical["id"] != derived_id.removeprefix("derived:"):
            issues.append(f"scene-id-mismatch:{derived_id}")
        if scene_spec.scene_sha256(canonical) != generation.get("scene_sha256"):
            issues.append(f"scene-normalized-hash-mismatch:{derived_id}")
        if scene_spec.scene_sha256(row["scene"]) != generation.get("scene_sha256"):
            issues.append(f"planned-scene-hash-mismatch:{derived_id}")

        variants = generation.get("variants", {})
        for variant in ("wide", "narrow"):
            v = variants.get(variant, {}) if isinstance(variants, dict) else {}
            asset = str(v.get("asset") or "")
            path = (content_base / asset).resolve()
            if not asset or not path.is_file() or sha256(path) != v.get("asset_sha256"):
                issues.append(f"scene-variant-missing-or-changed:{derived_id}:{variant}")
        scene_id = canonical["id"]
        markup = html_scenes.get(scene_id)
        if not markup:
            issues.append(f"scene-responsive-markup-missing:{derived_id}")
        else:
            for variant in ("wide", "narrow"):
                v = variants.get(variant, {}) if isinstance(variants, dict) else {}
                issues.extend(
                    _scene_html_variant_issues(
                        html_path, content_base, derived_id, variant, markup[variant], v
                    )
                )

    # A V2 generated scene cannot enter the student artifact without being in this plan/review.
    for used_id in sorted(used):
        record = figures.get(used_id)
        if isinstance(record, dict) and isinstance(record.get("scene_generation"), dict) and used_id not in planned_scene_ids:
            issues.append(f"unplanned-reviewed-scene-used:{used_id}")

    result = dict(base)
    result.update({
        "ok": not issues,
        "visual_v2": True,
        "vision_verified": not any(issue.startswith("visual-v2-review-invalid") for issue in issues),
        "planned_scene_count": len(planned_scene_ids),
        "issues": issues,
    })
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Artifact integrity gate with Visual System V2 binding")
    ap.add_argument("--course", required=True)
    ap.add_argument("--markdown", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--scope", required=True)
    ap.add_argument("--type", default="summary", choices=["summary", "guide", "rapid-review"])
    ap.add_argument("--plan", required=True)
    ap.add_argument("--preview", required=True)
    ap.add_argument("--review", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--write", required=True)
    args = ap.parse_args()
    course = resolve_course(args.course)
    result = check(
        course,
        Path(args.markdown).resolve(), Path(args.html).resolve(), args.scope, args.type,
        Path(args.plan).resolve(), Path(args.preview).resolve(), Path(args.review).resolve(), Path(args.build).resolve(),
    )
    out = Path(args.write).resolve()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
