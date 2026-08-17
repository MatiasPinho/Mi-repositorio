#!/usr/bin/env python3
"""Preview and collision-safe finalization for schema-2 scene figures."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from . import scene_preflight, scene_render, scene_spec
    from .course_layout import has_unit_layout, unit_root
    from .figure_assets import derived_key, load_registry, register_derived, save_registry
    from .unit_identity import resolve_unit, record_unit_id
except ImportError:
    import scene_preflight  # type: ignore
    import scene_render  # type: ignore
    import scene_spec  # type: ignore
    from course_layout import has_unit_layout, unit_root  # type: ignore
    from figure_assets import derived_key, load_registry, register_derived, save_registry  # type: ignore
    from unit_identity import resolve_unit, record_unit_id  # type: ignore

MAX_ATTEMPTS = 3


class SceneFigureError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _safe_run_dir(course: Path, run_dir: Path) -> Path:
    run = run_dir.resolve()
    course = course.resolve()
    if not run.is_dir() or not run.is_relative_to(course):
        raise SceneFigureError(f"run directory must exist inside course: {run}")
    if ".study" not in run.parts or "runs" not in run.parts:
        raise SceneFigureError("scene attempts must live inside a .study/runs directory")
    return run


def _next_attempt(run: Path, scene_id: str) -> tuple[int, Path]:
    root = run / "02-visual-attempts" / scene_id
    existing = sorted(
        int(path.name) for path in root.iterdir()
        if path.is_dir() and path.name.isdigit()
    ) if root.is_dir() else []
    attempt = (max(existing) + 1) if existing else 1
    if attempt > MAX_ATTEMPTS:
        raise SceneFigureError(f"{scene_id}: maximum {MAX_ATTEMPTS} visual attempts exceeded")
    return attempt, root / f"{attempt:02d}"


def _reusable_preview(run: Path, scene: dict[str, Any], unit_id: str) -> dict[str, Any] | None:
    """Reuse the latest exact preview instead of burning a new attempt.

    Repair loops often change one scene while every other scene is byte-identical.
    Those unchanged scenes must not be re-rendered, re-screenshot or promoted to a
    fake new attempt.  SHA-256 is authoritative here; vision is only needed again
    for a scene whose rendered evidence changed.
    """
    root = run / "02-visual-attempts" / scene["id"]
    if not root.is_dir():
        return None
    wanted_scene_sha = scene_spec.scene_sha256(scene)
    wanted_scene_bytes = scene_spec.scene_bytes(scene)
    attempts = sorted(
        (path for path in root.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
        reverse=True,
    )
    for attempt_dir in attempts:
        report = _read_json(attempt_dir / "preview.json")
        if report.get("ok") is not True:
            continue
        if report.get("unit_id") != unit_id or report.get("scene_id") != scene["id"]:
            continue
        if report.get("scene_sha256") != wanted_scene_sha:
            continue
        scene_path = Path(str(report.get("scene_file") or ""))
        if not scene_path.is_file() or scene_path.read_bytes() != wanted_scene_bytes:
            continue
        variants = report.get("variants")
        if not isinstance(variants, dict):
            continue
        valid = True
        for variant in scene_spec.VARIANTS:
            row = variants.get(variant)
            if not isinstance(row, dict):
                valid = False
                break
            svg = Path(str(row.get("svg") or ""))
            png = Path(str(row.get("png") or ""))
            if (
                not svg.is_file()
                or not png.is_file()
                or sha256_file(svg) != row.get("svg_sha256")
                or sha256_file(png) != row.get("png_sha256")
            ):
                valid = False
                break
        if valid:
            reused = dict(report)
            reused["reused"] = True
            reused["review_reuse_key"] = {
                "scene_sha256": wanted_scene_sha,
                "wide_png_sha256": variants["wide"]["png_sha256"],
                "narrow_png_sha256": variants["narrow"]["png_sha256"],
            }
            return reused
    return None


def _screenshot_svg(svg_bytes: bytes, out_path: Path, *, variant: str) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise SceneFigureError(
            "Visual preview requires Playwright Chromium; run the project setup environment"
        ) from exc
    target = int(scene_render.TARGET_DISPLAY_WIDTH[variant])
    viewport_width = 900 if variant == "wide" else 390
    data = base64.b64encode(svg_bytes).decode("ascii")
    css = """
      *{box-sizing:border-box} html,body{margin:0;background:#fbf9f4;color:#29323b}
      body{padding:24px;font-family:Arial,sans-serif}
      .paper{margin:0 auto;padding:22px 18px;width:VARIANT_WIDTHpx;max-width:calc(100vw - 32px);
        background-color:#fbf9f4;
        background-image:repeating-linear-gradient(to bottom,transparent 0,transparent 30px,rgba(80,110,140,.14) 31px,transparent 32px)}
      figure{margin:0} img{display:block;width:100%;height:auto}
    """.replace("VARIANT_WIDTH", str(target))
    document = (
        '<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head>'
        '<body><div class="paper"><figure id="preview">'
        f'<img alt="scene preview" src="data:image/svg+xml;base64,{data}">'
        '</figure></div></body></html>'
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": viewport_width, "height": 1000})
        page.set_content(document, wait_until="load")
        page.locator("#preview img").evaluate("img => img.decode ? img.decode() : Promise.resolve()")
        page.locator("#preview").screenshot(path=str(out_path))
        browser.close()


def preview_scene(course: Path, unit_value: str, scene_value: Any, run_dir: Path) -> dict[str, Any]:
    run = _safe_run_dir(course, run_dir)
    scene = scene_spec.validate_scene(scene_value)
    resolved = resolve_unit(course, unit_value)
    unit_id = str(resolved.get("unit_id") or "")
    if not unit_id:
        raise SceneFigureError(f"Could not resolve stable unit id from: {unit_value}")

    cached = _reusable_preview(run, scene, unit_id)
    if cached is not None:
        return cached

    attempt, attempt_dir = _next_attempt(run, scene["id"])
    attempt_dir.mkdir(parents=True, exist_ok=False)
    scene_path = attempt_dir / "scene.json"
    scene_path.write_bytes(scene_spec.scene_bytes(scene))

    preflight = scene_preflight.preflight_scene(scene)
    _write_json(attempt_dir / "preflight.json", preflight)

    narrow_name = f"{scene['id']}-narrow.svg"
    wide_name = f"{scene['id']}.svg"
    variants: dict[str, Any] = {}
    for variant, filename in (("wide", wide_name), ("narrow", narrow_name)):
        svg_bytes, render_report = scene_render.render_variant(
            scene, variant, narrow_asset=narrow_name if variant == "wide" else ""
        )
        svg_path = attempt_dir / filename
        svg_path.write_bytes(svg_bytes)
        variants[variant] = {
            "svg": str(svg_path),
            "svg_sha256": sha256_bytes(svg_bytes),
            "width": render_report["width"],
            "height": render_report["height"],
            "target_display_width": render_report["target_display_width"],
            "pencil_metrics": render_report["pencil_metrics"],
        }

    if preflight["ok"]:
        for variant in scene_spec.VARIANTS:
            png_path = attempt_dir / f"{variant}.png"
            _screenshot_svg(Path(variants[variant]["svg"]).read_bytes(), png_path, variant=variant)
            variants[variant]["png"] = str(png_path)
            variants[variant]["png_sha256"] = sha256_file(png_path)
    report = {
        "version": 1,
        "ok": bool(preflight["ok"]),
        "unit_id": unit_id,
        "scene_id": scene["id"],
        "scene_sha256": scene_spec.scene_sha256(scene),
        "scene_file": str(scene_path),
        "attempt": attempt,
        "attempt_dir": str(attempt_dir),
        "reused": False,
        "preflight": str(attempt_dir / "preflight.json"),
        "variants": variants,
    }
    _write_json(attempt_dir / "preview.json", report)
    return report


def _same_or_write(path: Path, data: bytes) -> bool:
    """Write new immutable bytes; exact retry is safe, different bytes fail."""
    if path.exists():
        if path.read_bytes() != data:
            raise SceneFigureError(f"asset collision; refusing overwrite: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)
    return True


def _existing_scene_record(course: Path, key: str, unit_id: str) -> dict[str, Any] | None:
    record = load_registry(course).get("figures", {}).get(key)
    if not isinstance(record, dict):
        return None
    if record.get("origin") != "derived" or record_unit_id(course, record) != unit_id:
        raise SceneFigureError(f"existing figure id belongs to incompatible record: {key}")
    return record


def finalize_scene(
    course: Path,
    unit_value: str,
    scene_value: Any,
    preview: dict[str, Any],
    review_row: dict[str, Any],
) -> dict[str, Any]:
    scene = scene_spec.validate_scene(scene_value)
    resolved = resolve_unit(course, unit_value)
    unit_id = str(resolved.get("unit_id") or "")
    if not unit_id:
        raise SceneFigureError(f"Could not resolve stable unit id from: {unit_value}")
    if preview.get("scene_id") != scene["id"] or preview.get("scene_sha256") != scene_spec.scene_sha256(scene):
        raise SceneFigureError(f"{scene['id']}: preview was produced from a different scene")
    if review_row.get("scene_id") != scene["id"] or review_row.get("status") != "pass":
        raise SceneFigureError(f"{scene['id']}: independent visual PASS is required")
    if review_row.get("attempt") != preview.get("attempt"):
        raise SceneFigureError(f"{scene['id']}: review refers to a stale attempt")
    inspected = {item.get("variant"): item for item in review_row.get("inspected", []) if isinstance(item, dict)}
    if set(inspected) != {"wide", "narrow"}:
        raise SceneFigureError(f"{scene['id']}: review must bind wide and narrow screenshots")
    for variant in ("wide", "narrow"):
        expected = preview.get("variants", {}).get(variant, {})
        row = inspected[variant]
        if row.get("file") != expected.get("png") or row.get("sha256") != expected.get("png_sha256"):
            raise SceneFigureError(f"{scene['id']}:{variant}: review screenshot binding is stale")
        shot = Path(str(row.get("file") or ""))
        if not shot.is_file() or sha256_file(shot) != row.get("sha256"):
            raise SceneFigureError(f"{scene['id']}:{variant}: reviewed screenshot missing or changed")

    narrow_name = f"{scene['id']}-narrow.svg"
    rendered: dict[str, tuple[bytes, dict[str, Any]]] = {
        "wide": scene_render.render_variant(scene, "wide", narrow_asset=narrow_name),
        "narrow": scene_render.render_variant(scene, "narrow"),
    }
    for variant in scene_spec.VARIANTS:
        expected = preview.get("variants", {}).get(variant, {}).get("svg_sha256")
        actual = sha256_bytes(rendered[variant][0])
        if expected != actual:
            raise SceneFigureError(f"{scene['id']}:{variant}: finalized SVG differs from reviewed preview")

    base = unit_root(course, unit_id) if has_unit_layout(course) else course
    asset_dir = base / "assets" / "figures"
    wide_path = asset_dir / f"{scene['id']}.svg"
    narrow_path = asset_dir / narrow_name
    spec_path = asset_dir / f"{scene['id']}.scene.json"
    normalized_bytes = scene_spec.scene_bytes(scene)
    _same_or_write(spec_path, normalized_bytes)
    _same_or_write(wide_path, rendered["wide"][0])
    _same_or_write(narrow_path, rendered["narrow"][0])

    wide_rel = wide_path.relative_to(base).as_posix()
    narrow_rel = narrow_path.relative_to(base).as_posix()
    spec_rel = spec_path.relative_to(base).as_posix()
    key = derived_key(scene["id"])
    metadata = {
        "method": "deterministic-scene-svg",
        "generator": scene_render.GENERATOR_ID,
        "version": scene_render.GENERATOR_VERSION,
        "schema_version": 2,
        "scene": spec_rel,
        "scene_sha256": scene_spec.scene_sha256(scene),
        "variants": {
            "wide": {"asset": wide_rel, "asset_sha256": sha256_file(wide_path)},
            "narrow": {"asset": narrow_rel, "asset_sha256": sha256_file(narrow_path)},
        },
        "visual_review": {
            "attempt": review_row["attempt"],
            "wide_png_sha256": inspected["wide"]["sha256"],
            "narrow_png_sha256": inspected["narrow"]["sha256"],
        },
    }

    existing = _existing_scene_record(course, key, unit_id)
    if existing is not None:
        if existing.get("asset") != wide_rel or existing.get("asset_sha256") != sha256_file(wide_path) or existing.get("scene_generation") != metadata:
            raise SceneFigureError(f"existing scene registration differs; refusing overwrite: {key}")
        return {"ok": True, "created": False, "key": key, "record": existing}

    register_derived(
        course,
        scene["id"],
        unit_id,
        wide_rel,
        scene["description"],
        scene["based_on"],
        concepts=scene.get("concepts", []),
        learner_focus=scene.get("learner_focus", []),
        kind="illustration",
        role=scene["role"],
        visual_treatment=scene["visual_treatment"],
        source_figure_id=scene.get("source_figure_id"),
    )
    registry = load_registry(course)
    registry["figures"][key]["representation_role"] = scene["representation_role"]
    registry["figures"][key]["scene_generation"] = metadata
    save_registry(course, registry)
    record = load_registry(course)["figures"][key]
    return {"ok": True, "created": True, "key": key, "record": record}
