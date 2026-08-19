#!/usr/bin/env python3
"""Runtime wrapper for the active hybrid visual plan.

Keeps the compact schema-1 / Cloudflare architecture while applying the
scale-aware notebook pencil profile, V2-inspired final-display layout guards
and tighter illustration cropping. This adds no model/agent calls.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import illustration_figure as illustration  # noqa: E402
from scripts import sketch_figure as sketch  # noqa: E402
from scripts import visual_plan_hybrid as hybrid  # noqa: E402
from scripts.course_layout import has_unit_layout, unit_root  # noqa: E402
from scripts.figure_assets import (  # noqa: E402
    derived_key,
    load_registry,
    registry_issues,
    save_registry,
    sha256,
)
from scripts.scene_pencil import profile as pencil_profile, rough_polyline as v2_rough_polyline  # noqa: E402
from scripts.unit_identity import resolve_unit  # noqa: E402

DIAGRAM_GENERATOR_VERSION = 4
ILLUSTRATION_GENERATOR_VERSION = 2
TARGET_DIAGRAM_WIDTH_PX = 704.0
ILLUSTRATION_CROP_VERSION = 2

# Recovered from GPT56/V2's deterministic geometry preflight. The hybrid path
# keeps schema-1 specs compact, but layout is now chosen against final-display
# constraints instead of logical-canvas dimensions alone.
V2_MIN_DISPLAY_GAP_PX = 7.0
V2_MAX_DENSITY = 0.74
V2_MAX_WIDE_ASPECT = 3.4
MIN_LAYOUT_SCALE = 0.88
PREFERRED_NODE_GAP = 72
PREFERRED_RANK_GAP = 124
LAYOUT_PROFILE = "v2-display-guard"

_ORIGINAL_LAYOUT = sketch._layout
_ORIGINAL_NODE_DIMENSIONS = sketch._node_dimensions
_ORIGINAL_ROUGH_POLYLINE = sketch._rough_polyline
_ORIGINAL_RENDER_SVG = sketch.render_svg
_ORIGINAL_PREPARE_OVERLAY = illustration._prepare_overlay
_ORIGINAL_GENERATE_ILLUSTRATION = illustration.generate_and_register
_ACTIVE_PROFILE = pencil_profile(704.0, 704.0)
_ACTIVE_LAYOUT_REPORT: dict[str, Any] = {
    "profile": LAYOUT_PROFILE,
    "requested_direction": "top-to-bottom",
    "resolved_direction": "top-to-bottom",
    "max_nodes_per_row": 1,
    "display_scale": 1.0,
    "min_display_gap_px": None,
    "density": 0.0,
    "aspect_ratio": 1.0,
}


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def _node_dimensions_polished(node: dict[str, Any]):
    """Give labels/details breathing room without changing semantic structure."""
    width, height, label_lines, detail_lines = _ORIGINAL_NODE_DIMENSIONS(node)
    extra_width = 30.0
    if detail_lines or len(node.get("label", "")) > 28:
        extra_width += 24.0
    width = min(410.0, max(232.0, width + extra_width))
    height = max(116.0, height + 24.0 + (12.0 if detail_lines else 0.0))
    return width, height, label_lines, detail_lines


def _box_distance(left: sketch.NodeBox, right: sketch.NodeBox) -> float:
    dx = max(left.x - (right.x + right.width), right.x - (left.x + left.width), 0.0)
    dy = max(left.y - (right.y + right.height), right.y - (left.y + left.height), 0.0)
    return math.hypot(dx, dy)


def _layout_metrics(
    boxes: dict[str, sketch.NodeBox],
    width: float,
    height: float,
) -> dict[str, float | None]:
    display_scale = min(1.0, TARGET_DIAGRAM_WIDTH_PX / max(width, 1.0))
    values = list(boxes.values())
    gaps = [
        _box_distance(left, right) * display_scale
        for index, left in enumerate(values)
        for right in values[index + 1 :]
    ]
    occupied = sum(box.width * box.height for box in values)
    return {
        "display_scale": display_scale,
        "min_display_gap_px": min(gaps) if gaps else None,
        "density": occupied / max(width * height, 1.0),
        "aspect_ratio": width / max(height, 1.0),
        "display_height_px": height * display_scale,
    }


def _layout_candidate(
    spec: dict[str, Any],
    *,
    direction: str,
    max_nodes_per_row: int,
) -> dict[str, Any]:
    work = copy.deepcopy(spec)
    layout = work.setdefault("layout", {})
    layout["direction"] = direction
    layout["node_gap"] = max(int(layout.get("node_gap", 56)), PREFERRED_NODE_GAP)
    layout["rank_gap"] = max(int(layout.get("rank_gap", 108)), PREFERRED_RANK_GAP)

    previous = sketch.MAX_NODES_PER_ROW
    sketch.MAX_NODES_PER_ROW = max_nodes_per_row
    try:
        boxes, width, height, title_height = _ORIGINAL_LAYOUT(work)
    finally:
        sketch.MAX_NODES_PER_ROW = previous

    return {
        "boxes": boxes,
        "width": width,
        "height": height,
        "title_height": title_height,
        "direction": direction,
        "max_nodes_per_row": max_nodes_per_row,
        "metrics": _layout_metrics(boxes, width, height),
    }


def _layout_score(candidate: dict[str, Any], requested_direction: str) -> tuple[float, ...]:
    metrics = candidate["metrics"]
    scale = float(metrics["display_scale"] or 0.0)
    min_gap = metrics["min_display_gap_px"]
    density = float(metrics["density"] or 0.0)
    aspect = float(metrics["aspect_ratio"] or 0.0)

    hard_failures = 0.0
    if scale < MIN_LAYOUT_SCALE:
        hard_failures += 1.0
    if min_gap is not None and float(min_gap) < V2_MIN_DISPLAY_GAP_PX:
        hard_failures += 1.0
    if density > V2_MAX_DENSITY:
        hard_failures += 1.0
    if aspect > V2_MAX_WIDE_ASPECT:
        hard_failures += 1.0

    # Prefer the requested orientation when it already satisfies final-display
    # constraints. Otherwise a readable top-to-bottom reflow beats shrinking a
    # horizontal diagram until its text/padding collapse.
    direction_penalty = 0.0 if candidate["direction"] == requested_direction else 1.0
    return (
        hard_failures,
        max(0.0, MIN_LAYOUT_SCALE - scale),
        max(0.0, V2_MIN_DISPLAY_GAP_PX - float(min_gap or V2_MIN_DISPLAY_GAP_PX)),
        max(0.0, density - V2_MAX_DENSITY),
        max(0.0, aspect - V2_MAX_WIDE_ASPECT),
        direction_penalty,
        float(metrics["display_height_px"] or 0.0),
    )


def _layout_polished(spec: dict[str, Any]):
    """Recover GPT56/V2 final-display composition guarantees without scene graphs."""
    global _ACTIVE_PROFILE, _ACTIVE_LAYOUT_REPORT
    requested = str(spec.get("layout", {}).get("direction") or "top-to-bottom")

    candidates: list[dict[str, Any]] = []
    if requested == "left-to-right":
        candidates.append(_layout_candidate(spec, direction="left-to-right", max_nodes_per_row=2))
        candidates.append(_layout_candidate(spec, direction="top-to-bottom", max_nodes_per_row=2))
        candidates.append(_layout_candidate(spec, direction="top-to-bottom", max_nodes_per_row=1))
    else:
        candidates.append(_layout_candidate(spec, direction="top-to-bottom", max_nodes_per_row=2))
        candidates.append(_layout_candidate(spec, direction="top-to-bottom", max_nodes_per_row=1))

    chosen = min(candidates, key=lambda row: _layout_score(row, requested))
    metrics = chosen["metrics"]
    display_width = min(TARGET_DIAGRAM_WIDTH_PX, float(chosen["width"]))
    _ACTIVE_PROFILE = pencil_profile(float(chosen["width"]), display_width)
    _ACTIVE_LAYOUT_REPORT = {
        "profile": LAYOUT_PROFILE,
        "requested_direction": requested,
        "resolved_direction": chosen["direction"],
        "max_nodes_per_row": chosen["max_nodes_per_row"],
        "display_scale": round(float(metrics["display_scale"] or 0.0), 4),
        "min_display_gap_px": (
            round(float(metrics["min_display_gap_px"]), 2)
            if metrics["min_display_gap_px"] is not None
            else None
        ),
        "density": round(float(metrics["density"] or 0.0), 4),
        "aspect_ratio": round(float(metrics["aspect_ratio"] or 0.0), 4),
        "canvas": [round(float(chosen["width"]), 2), round(float(chosen["height"]), 2)],
    }
    return chosen["boxes"], chosen["width"], chosen["height"], chosen["title_height"]


def _rough_polyline_polished(
    points: list[tuple[float, float]],
    seed: str,
    key: str,
    *,
    closed: bool = False,
    scale: float = 1.0,
) -> str:
    """Reuse GPT56/V2's scale-aware pencil geometry in the cheap schema-1 renderer."""
    return v2_rough_polyline(
        points,
        seed,
        key,
        jitter_scale=_ACTIVE_PROFILE.jitter * scale,
        bend_scale=_ACTIVE_PROFILE.bend * scale,
        closed=closed,
    )


def _add_non_scaling_stroke(match: re.Match[str]) -> str:
    """Add vector-effect without corrupting normal or self-closing path tags."""
    tag = match.group(0)
    closing = "/>" if tag.endswith("/>") else ">"
    body = tag[: -len(closing)].rstrip()
    return f'{body} vector-effect="non-scaling-stroke"{closing}'


def _postprocess_svg(svg: bytes) -> bytes:
    """Keep text/strokes legible after a wide SVG is scaled into the notebook."""
    logical = _ACTIVE_PROFILE.logical_per_css_px
    text = svg.decode("utf-8")

    replacements = {
        r'(\.sketch-label\{font:)600 22px': rf'\g<1>600 {22.0 * logical:.2f}px',
        r'(\.sketch-detail\{font:)400 17px': rf'\g<1>400 {17.0 * logical:.2f}px',
        r'(\.sketch-title\{font:)600 29px': rf'\g<1>600 {27.0 * logical:.2f}px',
        r'(\.sketch-kind\{font:)400 15px': rf'\g<1>400 {16.0 * logical:.2f}px',
        r'(\.sketch-edge-label\{font:)600 15px': rf'\g<1>600 {16.0 * logical:.2f}px',
        r'(\.sketch-group-label\{font:)600 15px': rf'\g<1>600 {16.0 * logical:.2f}px',
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)

    # SVG <img> scaling used to make the two pencil traces look ruler-clean.
    # Non-scaling strokes preserve graphite weight while scale-aware geometry
    # above preserves visible wobble. Match the complete opening tag and let the
    # replacement preserve '/>' explicitly; otherwise the slash becomes part of
    # the attribute body and creates invalid XML.
    text = re.sub(
        r'<path\b(?![^>]*\bvector-effect=)(?=[^>]*\bstroke="[^"]+")[^>]*?/?>',
        _add_non_scaling_stroke,
        text,
    )
    layout_attrs = (
        f'data-layout-profile="{LAYOUT_PROFILE}" '
        f'data-layout-direction="{_ACTIVE_LAYOUT_REPORT.get("resolved_direction", "")}" '
        f'data-layout-scale="{_ACTIVE_LAYOUT_REPORT.get("display_scale", 1.0)}"'
    )
    text = text.replace(
        'data-pencil-style="graphite-overlay-v1"',
        f'data-pencil-style="graphite-overlay-v1" data-pencil-profile="scale-aware-v2" {layout_attrs}',
        1,
    )
    polished = text.encode("utf-8")
    try:
        ET.fromstring(polished)
    except ET.ParseError as exc:
        raise sketch.SketchSpecError(f"polished SVG is invalid XML: {exc}") from exc
    audit = sketch.audit_svg_style(polished)
    if not audit["ok"]:
        raise sketch.SketchSpecError(
            f"polished SVG failed style audit: {', '.join(audit['issues'])}"
        )
    return polished


def _render_svg_polished(spec_value: Any):
    svg, report = _ORIGINAL_RENDER_SVG(spec_value)
    polished = _postprocess_svg(svg)
    report = dict(report)
    report["svg_sha256"] = hashlib.sha256(polished).hexdigest()
    report["pencil_profile"] = "scale-aware-v2"
    report["layout"] = dict(_ACTIVE_LAYOUT_REPORT)
    report["style_audit"] = sketch.audit_svg_style(polished)
    return polished, report


def _unit_base(course: Path, unit_value: str) -> tuple[str, Path]:
    unit = resolve_unit(course, unit_value)
    unit_id = str(unit.get("unit_id") or "")
    if not unit_id:
        raise sketch.SketchSpecError(f"Could not resolve stable unit id from: {unit_value}")
    return unit_id, unit_root(course, unit_id) if has_unit_layout(course) else course


def _stored_spec(base: Path, record: dict[str, Any]) -> dict[str, Any] | None:
    generation = record.get("generation")
    if not isinstance(generation, dict):
        return None
    rel = str(generation.get("spec") or "").strip()
    if not rel:
        return None
    path = (base / rel).resolve()
    if not path.is_file():
        return None
    try:
        return sketch.validate_spec(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError, sketch.SketchSpecError):
        return None


def generate_polished_diagram(course: Path, unit_value: str, spec_value: Any) -> dict[str, Any]:
    """Generate schema-1 diagrams with V2 pencil/display guards and safe reuse upgrades."""
    spec = sketch.validate_spec(spec_value)
    unit_id, base = _unit_base(course, unit_value)
    key = derived_key(spec["id"])
    asset_rel = f"assets/figures/{spec['id']}.svg"
    spec_rel = f"assets/figures/{spec['id']}.sketch.json"
    asset_path = (base / asset_rel).resolve()
    spec_path = (base / spec_rel).resolve()
    data = load_registry(course)
    record = data.get("figures", {}).get(key)

    if isinstance(record, dict):
        generation = record.get("generation")
        safe_existing = (
            record.get("origin") == "derived"
            and record.get("unit_id") == unit_id
            and record.get("visual_treatment") == spec["visual_treatment"]
            and record.get("source_figure_id") == spec.get("source_figure_id")
            and record.get("asset") == asset_rel
            and isinstance(generation, dict)
            and generation.get("method") == "deterministic-svg"
            and _stored_spec(base, record) == spec
        )
        if not safe_existing:
            raise sketch.SketchSpecError(
                f"Figure id already exists with different semantic content; refusing visual upgrade: {key}"
            )

        spec_bytes = (sketch.canonical_json(spec, indent=2) + "\n").encode("utf-8")
        spec_sha = hashlib.sha256(spec_bytes).hexdigest()
        svg_bytes, render_report = _render_svg_polished(spec)
        svg_sha = hashlib.sha256(svg_bytes).hexdigest()
        already_current = (
            generation.get("generator") == sketch.GENERATOR_ID
            and generation.get("version") == DIAGRAM_GENERATOR_VERSION
            and generation.get("spec_sha256") == spec_sha
            and record.get("asset_sha256") == svg_sha
            and asset_path.is_file()
            and spec_path.is_file()
            and sha256(asset_path) == svg_sha
            and sha256(spec_path) == spec_sha
        )
        if already_current:
            return {
                "ok": True,
                "created": False,
                "upgraded": False,
                "key": key,
                "record": record,
                "spec_sha256": spec_sha,
                "svg_sha256": svg_sha,
            }

        old_asset = asset_path.read_bytes() if asset_path.is_file() else None
        old_spec = spec_path.read_bytes() if spec_path.is_file() else None
        old_record = copy.deepcopy(record)
        try:
            _atomic_write(spec_path, spec_bytes)
            _atomic_write(asset_path, svg_bytes)
            record["asset_sha256"] = svg_sha
            record["generation"] = {
                "method": "deterministic-svg",
                "generator": sketch.GENERATOR_ID,
                "version": DIAGRAM_GENERATOR_VERSION,
                "spec": spec_rel,
                "spec_sha256": spec_sha,
                "diagram_kind": spec["kind"],
                "pencil_profile": "scale-aware-v2",
                "layout_profile": LAYOUT_PROFILE,
            }
            issues = registry_issues(course, data)
            if issues:
                raise sketch.SketchSpecError(json.dumps({"issues": issues}, ensure_ascii=False))
            save_registry(course, data)
        except Exception:
            data["figures"][key] = old_record
            if old_asset is not None:
                _atomic_write(asset_path, old_asset)
            if old_spec is not None:
                _atomic_write(spec_path, old_spec)
            raise
        return {
            "ok": True,
            "created": False,
            "upgraded": True,
            "key": key,
            "record": record,
            "spec_sha256": spec_sha,
            "svg_sha256": svg_sha,
            **render_report,
        }

    return sketch.generate_and_register(course, unit_value, spec)


def _tighten_overlay_svg(svg: bytes) -> tuple[bytes, dict[str, Any]]:
    """Trim transparent tails/noise from an already prepared illustration without another provider call."""
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise illustration.IllustrationError("Pillow is required; install requirements-visual.txt") from exc

    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise illustration.IllustrationUnavailable(f"Generated illustration SVG is invalid: {exc}") from exc
    namespace = "{http://www.w3.org/2000/svg}"
    image_node = root.find(f"{namespace}image")
    if image_node is None:
        raise illustration.IllustrationUnavailable("Generated illustration overlay has no image")
    href = image_node.get("href", "")
    prefix = "data:image/png;base64,"
    if not href.startswith(prefix):
        raise illustration.IllustrationUnavailable("Generated illustration overlay has no embedded PNG")
    try:
        png = base64.b64decode(href[len(prefix):], validate=True)
        raster = Image.open(io.BytesIO(png)).convert("RGBA")
    except Exception as exc:
        raise illustration.IllustrationUnavailable("Generated illustration PNG is invalid") from exc

    alpha = raster.getchannel("A")
    significant = alpha.point(lambda p: 255 if p >= 20 else 0)
    bbox = significant.getbbox() or alpha.getbbox()
    if bbox is None:
        raise illustration.IllustrationUnavailable("Generated illustration is blank after transparency")
    left, top, right, bottom = bbox
    pad = max(8, int(max(right - left, bottom - top) * 0.025))
    box = (
        max(0, left - pad),
        max(0, top - pad),
        min(raster.width, right + pad),
        min(raster.height, bottom + pad),
    )
    cropped = raster.crop(box)
    out = io.BytesIO()
    cropped.save(out, "PNG", optimize=True)
    new_png = out.getvalue()
    width, height = cropped.size

    root.set("width", str(width))
    root.set("height", str(height))
    root.set("viewBox", f"0 0 {width} {height}")
    root.set("data-crop-version", str(ILLUSTRATION_CROP_VERSION))
    image_node.set("width", str(width))
    image_node.set("height", str(height))
    image_node.set("href", prefix + base64.b64encode(new_png).decode("ascii"))
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    payload = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n"
    return payload, {
        "tight_crop_box": list(box),
        "output_size": [width, height],
        "embedded_png_sha256": hashlib.sha256(new_png).hexdigest(),
        "crop_version": ILLUSTRATION_CROP_VERSION,
        "transparent_overlay": True,
    }


def _prepare_overlay_polished(raw: bytes, alt: str):
    overlay, metadata = _ORIGINAL_PREPARE_OVERLAY(raw, alt)
    tightened, tight_meta = _tighten_overlay_svg(overlay)
    return tightened, {**metadata, **tight_meta}


def _stored_illustration_spec(base: Path, record: dict[str, Any]) -> dict[str, Any] | None:
    meta = record.get("illustration_generation")
    if not isinstance(meta, dict):
        return None
    rel = str(meta.get("spec") or "").strip()
    path = (base / rel).resolve() if rel else None
    if path is None or not path.is_file():
        return None
    try:
        return illustration.validate_spec(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError, illustration.IllustrationError):
        return None


def generate_polished_illustration(
    course: Path,
    unit_value: str,
    spec_value: Any,
    *,
    concept_id: str,
) -> dict[str, Any]:
    """Tighten existing overlays locally; only new semantic specs call Cloudflare."""
    spec = illustration.validate_spec(spec_value)
    unit = resolve_unit(course, unit_value)
    unit_id = str(unit.get("unit_id") or "")
    if not unit_id:
        raise illustration.IllustrationError(f"Could not resolve unit: {unit_value}")
    base = unit_root(course, unit_id) if has_unit_layout(course) else course
    key = derived_key(spec["id"])
    data = load_registry(course)
    record = data.get("figures", {}).get(key)

    if isinstance(record, dict):
        meta = record.get("illustration_generation")
        asset_rel = f"assets/figures/{spec['id']}.illustration.svg"
        asset_path = (base / asset_rel).resolve()
        safe_existing = (
            record.get("origin") == "derived"
            and record.get("kind") == "illustration"
            and record.get("unit_id") == unit_id
            and record.get("asset") == asset_rel
            and isinstance(meta, dict)
            and meta.get("method") == "generated-illustration"
            and _stored_illustration_spec(base, record) == spec
            and asset_path.is_file()
        )
        if not safe_existing:
            raise illustration.IllustrationError(
                f"Figure id already exists with different semantic content: {key}"
            )
        if (
            meta.get("version") == ILLUSTRATION_GENERATOR_VERSION
            and meta.get("crop_version") == ILLUSTRATION_CROP_VERSION
            and record.get("asset_sha256") == sha256(asset_path)
        ):
            return {"ok": True, "created": False, "upgraded": False, "key": key, "record": record}

        old_asset = asset_path.read_bytes()
        old_record = copy.deepcopy(record)
        try:
            tightened, tight_meta = _tighten_overlay_svg(old_asset)
            _atomic_write(asset_path, tightened)
            record["asset_sha256"] = sha256(asset_path)
            meta.update(tight_meta)
            meta["version"] = ILLUSTRATION_GENERATOR_VERSION
            issues = registry_issues(course, data)
            if issues:
                raise illustration.IllustrationError(json.dumps({"issues": issues}, ensure_ascii=False))
            save_registry(course, data)
        except Exception:
            data["figures"][key] = old_record
            _atomic_write(asset_path, old_asset)
            raise
        return {"ok": True, "created": False, "upgraded": True, "key": key, "record": record}

    return _ORIGINAL_GENERATE_ILLUSTRATION(
        course,
        unit_value,
        spec,
        concept_id=concept_id,
    )


def install_runtime_polish() -> None:
    """Install deterministic runtime hooks before the existing hybrid main executes."""
    sketch.GENERATOR_VERSION = DIAGRAM_GENERATOR_VERSION
    sketch._node_dimensions = _node_dimensions_polished
    sketch._layout = _layout_polished
    sketch._rough_polyline = _rough_polyline_polished
    sketch.render_svg = _render_svg_polished

    illustration.VERSION = ILLUSTRATION_GENERATOR_VERSION
    illustration._prepare_overlay = _prepare_overlay_polished

    hybrid.generate_and_register = generate_polished_diagram
    hybrid.generate_illustration = generate_polished_illustration


if __name__ == "__main__":
    install_runtime_polish()
    hybrid.main()
