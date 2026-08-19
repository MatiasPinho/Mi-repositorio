#!/usr/bin/env python3
"""Runtime wrapper for the active hybrid visual plan.

Keeps the compact schema-1 / Cloudflare architecture while applying the
scale-aware notebook pencil profile, roomier diagram layout and tighter
illustration cropping. This adds no model/agent calls.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
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

DIAGRAM_GENERATOR_VERSION = 3
ILLUSTRATION_GENERATOR_VERSION = 2
TARGET_DIAGRAM_WIDTH_PX = 704.0
ILLUSTRATION_CROP_VERSION = 2

_ORIGINAL_LAYOUT = sketch._layout
_ORIGINAL_NODE_DIMENSIONS = sketch._node_dimensions
_ORIGINAL_ROUGH_POLYLINE = sketch._rough_polyline
_ORIGINAL_RENDER_SVG = sketch.render_svg
_ORIGINAL_PREPARE_OVERLAY = illustration._prepare_overlay
_ORIGINAL_GENERATE_ILLUSTRATION = illustration.generate_and_register
_ACTIVE_PROFILE = pencil_profile(704.0, 704.0)


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
    height = max(116.0, height + 24.0 + (8.0 if detail_lines else 0.0))
    return width, height, label_lines, detail_lines


def _layout_polished(spec: dict[str, Any]):
    """Use larger gaps and fewer columns only when a graph is visually dense."""
    global _ACTIVE_PROFILE
    work = copy.deepcopy(spec)
    layout = work.setdefault("layout", {})
    layout["node_gap"] = max(int(layout.get("node_gap", 56)), 64)
    layout["rank_gap"] = max(int(layout.get("rank_gap", 108)), 118)

    nodes = work.get("nodes", [])
    dense = len(nodes) >= 5 or any(
        len(str(node.get("label", ""))) > 30 or bool(str(node.get("detail", "")).strip())
        for node in nodes
        if isinstance(node, dict)
    )
    previous = sketch.MAX_NODES_PER_ROW
    sketch.MAX_NODES_PER_ROW = 2 if dense else 3
    try:
        boxes, width, height, title_height = _ORIGINAL_LAYOUT(work)
    finally:
        sketch.MAX_NODES_PER_ROW = previous

    display_width = min(TARGET_DIAGRAM_WIDTH_PX, width)
    _ACTIVE_PROFILE = pencil_profile(width, display_width)
    return boxes, width, height, title_height


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
    text = text.replace(
        'data-pencil-style="graphite-overlay-v1"',
        'data-pencil-style="graphite-overlay-v1" data-pencil-profile="scale-aware-v2"',
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
    """Generate schema-1 diagrams with the V2 pencil profile and upgrade safe reuse in place."""
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
