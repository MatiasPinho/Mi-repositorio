#!/usr/bin/env python3
"""Notebook-specific polish for schema-1 deterministic sketch diagrams.

This module intentionally owns only presentation invariants that were easy to
lose while switching between visual-system generations: text must fit inside
nodes, every geometric node must retain a visibly hand-drawn pencil outline,
standalone SVG images must carry the notebook fonts themselves, and the small
figure-kind label must share a stable title baseline.

The semantic graph, node ranks, relationships and connector routing remain
owned by ``sketch_figure`` / the active hybrid runtime.  No model calls are
introduced here.
"""
from __future__ import annotations

import hashlib
import html
import math
import re
import xml.etree.ElementTree as ET
from typing import Any

from scripts import sketch_figure as sketch

POLICY_VERSION = "carpeta-sketch-polish-v1"
TEXT_FIT_POLICY = "fit-first-v2"
SHAPE_POLICY = "pencil-shape-variants-v1"
TITLE_META_POLICY = "baseline-safe-v1"
TYPOGRAPHY_POLICY = "carpeta-svg-fonts-v1"

NEUCHA_WOFF2 = "https://fonts.gstatic.com/s/neucha/v18/q5uGsou0JOdh94bfvQlt.woff2"
ARCHITECTS_TTF = "https://fonts.gstatic.com/s/architectsdaughter/v19/KtkxAKiDZI_td1Lkx62xHZHDtgO_Y-bvfY5q4szgE-Q.ttf"

# The active runtime scales logical SVG units into a ~704px notebook lane.  Its
# preferred candidates stay at >= .88 display scale, so reserving ~18% extra
# text width prevents a scale-aware font from outgrowing the box that was laid
# out before the final SVG scale was known.
TEXT_SCALE_BUDGET = 1.18
LABEL_CHAR_WIDTH = 10.4 * TEXT_SCALE_BUDGET
DETAIL_CHAR_WIDTH = 7.9 * TEXT_SCALE_BUDGET
NODE_PADDING_X = 24.0
NODE_PADDING_Y = 24.0

INNER_WIDTH_FACTOR = {
    "decision": 0.68,
    "data": 0.78,
    "note": 0.84,
    "circle": 0.72,
    "terminal": 0.84,
    "rounded": 0.88,
    "datastore": 0.86,
    "component": 0.86,
    "box": 0.90,
    "process": 0.90,
}

MIN_WIDTH = {
    "decision": 250.0,
    "circle": 225.0,
    "data": 218.0,
    "component": 218.0,
}
MAX_WIDTH = {
    "decision": 380.0,
    "circle": 340.0,
}


class SketchPolishError(ValueError):
    pass


def _variant_index(seed: str, node_id: str) -> int:
    payload = f"{seed}|{node_id}|shape-variant".encode("utf-8")
    return hashlib.sha256(payload).digest()[0] % 3


def variant_name(seed: str, node_id: str) -> str:
    return ("a", "b", "c")[_variant_index(seed, node_id)]


def _longest_token(text: str) -> int:
    return max((len(token) for token in text.split()), default=1)


def _desired_lines(text: str, *, detail: bool = False) -> int:
    if not text:
        return 0
    if detail:
        if len(text) <= 42:
            return 2
        if len(text) <= 88:
            return 3
        return 4
    if len(text) <= 19:
        return 1
    if len(text) <= 46:
        return 2
    return 3


def node_dimensions(node: dict[str, Any]):
    """Return shape-aware dimensions that fit text before shrinking anything.

    The base renderer used a rectangular text budget for every geometry.  That
    is unsafe for diamonds/parallelograms and becomes visible once final SVG
    fonts are preserved at notebook scale.  Here the content box is narrower
    for shapes whose sides intrude into the nominal bounding box.
    """
    label = str(node.get("label") or "")
    detail = str(node.get("detail") or "")
    shape = str(node.get("shape") or "rounded")
    inner_factor = INNER_WIDTH_FACTOR.get(shape, 0.88)

    label_target = max(1, _desired_lines(label))
    detail_target = max(1, _desired_lines(detail, detail=True)) if detail else 0
    label_need = max(
        _longest_token(label) * LABEL_CHAR_WIDTH,
        math.ceil(len(label) / label_target) * LABEL_CHAR_WIDTH * 0.90,
    )
    detail_need = 0.0
    if detail:
        detail_need = max(
            _longest_token(detail) * DETAIL_CHAR_WIDTH,
            math.ceil(len(detail) / detail_target) * DETAIL_CHAR_WIDTH * 0.88,
        )

    required_inner = max(label_need, detail_need, 120.0)
    minimum = MIN_WIDTH.get(shape, 205.0)
    maximum = MAX_WIDTH.get(shape, 350.0)
    width = max(minimum, (required_inner + NODE_PADDING_X * 2.0) / inner_factor)
    width = min(maximum, width)

    label_capacity = max(
        10,
        int((width * inner_factor - NODE_PADDING_X * 2.0) / LABEL_CHAR_WIDTH),
    )
    detail_capacity = max(
        14,
        int((width * inner_factor - NODE_PADDING_X * 2.0) / DETAIL_CHAR_WIDTH),
    )
    label_lines = sketch._wrap(label, label_capacity)
    detail_lines = sketch._wrap(detail, detail_capacity)

    label_height = len(label_lines) * 32.0
    detail_height = len(detail_lines) * 24.0
    inter_text_gap = 12.0 if detail_lines else 0.0
    height = NODE_PADDING_Y * 2.0 + label_height + detail_height + inter_text_gap
    height = max(104.0, height)

    if shape == "decision":
        # Text sits around the diamond centre where the available width is
        # largest, but extra vertical breathing room keeps upper/lower lines
        # away from the sloping edges.
        height = max(152.0, height + 20.0)
    elif shape == "terminal":
        height = max(112.0, height)
    elif shape == "circle":
        diameter = max(width, height, 220.0)
        width = height = diameter

    return width, height, label_lines, detail_lines


def _outline_points(node: dict[str, Any], box: Any, seed: str) -> list[tuple[float, float]] | None:
    """Return logical shape points with deterministic human variation.

    The logical bounding box is unchanged for routing.  Mid-edge connector
    locations remain on the nominal border while corners/shoulders vary enough
    that the visible outline no longer reads as a perfect UI rectangle.
    """
    x, y = float(box.x), float(box.y)
    width, height = float(box.width), float(box.height)
    cx, cy = float(box.cx), float(box.cy)
    shape = str(node.get("shape") or "rounded")
    variant = _variant_index(seed, str(node.get("id") or "node"))

    # Small structural asymmetry in logical units.  The scale-aware pencil
    # renderer adds its own second-order wobble on top of these points.
    drift = (2.2, 3.2, 4.0)[variant]

    def j(part: str, amount: float = drift) -> float:
        return sketch._jitter(seed, node.get("id", "node"), "outline", variant, part, scale=amount)

    if shape in {"box", "process"}:
        return [
            (x + j("tlx"), y + j("tly")),
            (cx, y),
            (x + width + j("trx"), y + j("try")),
            (x + width, cy),
            (x + width + j("brx"), y + height + j("bry")),
            (cx, y + height),
            (x + j("blx"), y + height + j("bly")),
            (x, cy),
        ]
    if shape == "component":
        cut = (12.0, 17.0, 22.0)[variant]
        return [
            (x + cut, y + j("ct1", drift * .45)),
            (cx, y),
            (x + width - cut, y + j("ct2", drift * .45)),
            (x + width + j("cr1", drift * .35), y + cut),
            (x + width, cy),
            (x + width + j("cr2", drift * .35), y + height - cut),
            (x + width - cut, y + height + j("cb1", drift * .45)),
            (cx, y + height),
            (x + cut, y + height + j("cb2", drift * .45)),
            (x + j("cl1", drift * .35), y + height - cut),
            (x, cy),
            (x + j("cl2", drift * .35), y + cut),
        ]
    if shape == "decision":
        shoulder = (0.0, 4.0, -4.0)[variant]
        return [
            (cx + shoulder, y),
            (x + width, cy + j("dr", drift * .35)),
            (cx - shoulder, y + height),
            (x, cy + j("dl", drift * .35)),
        ]
    if shape == "data":
        skew = min((28.0, 34.0, 40.0)[variant], width * 0.15)
        return [
            (x + skew + j("dtl", drift * .35), y),
            (cx, y),
            (x + width + j("dtr", drift * .35), y),
            (x + width - skew, y + height),
            (cx, y + height),
            (x + j("dbl", drift * .35), y + height),
        ]
    if shape == "note":
        fold = min((24.0, 30.0, 36.0)[variant], width * 0.16)
        return [
            (x + j("ntl", drift * .35), y),
            (cx, y),
            (x + width - fold, y),
            (x + width, y + fold),
            (x + width, cy),
            (x + width + j("nbr", drift * .3), y + height),
            (cx, y + height),
            (x + j("nbl", drift * .3), y + height),
            (x, cy),
        ]
    return None


def node_path(node: dict[str, Any], box: Any, seed: str, trace: str, *, scale: float = 1.0) -> str:
    """Render all schema-1 node shapes through the notebook pencil language."""
    points = _outline_points(node, box, seed)
    shape = str(node.get("shape") or "rounded")
    key = f'{node.get("id", "node")}:{trace}'
    variant = _variant_index(seed, str(node.get("id") or "node"))

    if points is not None:
        return sketch._rough_polygon(points, seed, key, scale=scale)
    if shape == "datastore":
        radius = (18.0, 24.0, 30.0)[variant]
        return sketch._rounded_path(box, radius, seed, key, scale=scale)
    if shape == "rounded":
        radius = (10.0, 15.0, 20.0)[variant]
        return sketch._rounded_path(box, radius, seed, key, scale=scale)
    if shape == "terminal":
        return sketch._rounded_path(box, float(box.height) / 2.0, seed, key, scale=scale)
    if shape == "circle":
        count = (22, 26, 30)[variant]
        radius_x = float(box.width) / 2.0
        radius_y = float(box.height) / 2.0
        points = [
            (
                float(box.cx) + radius_x * math.cos(index * math.tau / count),
                float(box.cy) + radius_y * math.sin(index * math.tau / count),
            )
            for index in range(count)
        ]
        return sketch._rough_polygon(points, seed, key, scale=scale)
    return sketch._rough_polygon(
        [
            (float(box.x), float(box.y)),
            (float(box.x + box.width), float(box.y)),
            (float(box.x + box.width), float(box.y + box.height)),
            (float(box.x), float(box.y + box.height)),
        ],
        seed,
        key,
        scale=scale,
    )


def _font_css() -> str:
    return (
        f'@font-face{{font-family:"Neucha";font-style:normal;font-weight:400;font-display:swap;'
        f'src:local("Neucha"),url("{NEUCHA_WOFF2}") format("woff2")}}'
        f'@font-face{{font-family:"Architects Daughter";font-style:normal;font-weight:400;font-display:swap;'
        f'src:local("Architects Daughter"),url("{ARCHITECTS_TTF}") format("truetype")}}'
    )


def _replace_font_family(text: str, class_name: str, family: str) -> str:
    pattern = rf'(\.{re.escape(class_name)}\{{font:[^;]+?px )[^;]+(;fill:)'
    return re.sub(pattern, rf'\1{family}\2', text, count=1)


def postprocess_svg(svg: bytes, spec_value: Any) -> bytes:
    spec = sketch.validate_spec(spec_value)
    seed = sketch.digest_bytes(sketch.canonical_json(spec).encode("utf-8"))
    text = svg.decode("utf-8")

    if 'font-family:"Neucha"' not in text:
        text = text.replace("<style>", "<style>" + _font_css(), 1)

    text = _replace_font_family(
        text,
        "sketch-label",
        '"Neucha","Segoe Print","Comic Sans MS",cursive',
    )
    text = _replace_font_family(
        text,
        "sketch-detail",
        '"Neucha","Segoe Print","Comic Sans MS",cursive',
    )
    text = _replace_font_family(
        text,
        "sketch-title",
        '"Architects Daughter","Segoe Print","Comic Sans MS",cursive',
    )
    for class_name in ("sketch-kind", "sketch-edge-label", "sketch-group-label"):
        text = _replace_font_family(
            text,
            class_name,
            '"Neucha","Segoe Print","Comic Sans MS",cursive',
        )

    # The base renderer placed the meta word four logical pixels above the
    # title baseline.  On a handwriting face that looks visibly detached.
    text = re.sub(
        r'<text class="sketch-kind" x="([^"]+)" y="48" text-anchor="end">',
        r'<text class="sketch-kind" x="\1" y="52.00" text-anchor="end" dominant-baseline="alphabetic" data-role="figure-kind">',
        text,
        count=1,
    )

    root_marker = 'data-pencil-style="graphite-overlay-v1"'
    if f'data-sketch-polish="{POLICY_VERSION}"' not in text:
        text = text.replace(
            root_marker,
            (
                root_marker
                + f' data-sketch-polish="{POLICY_VERSION}"'
                + f' data-node-text-policy="{TEXT_FIT_POLICY}"'
                + f' data-shape-policy="{SHAPE_POLICY}"'
                + f' data-title-meta-policy="{TITLE_META_POLICY}"'
                + f' data-svg-typography="{TYPOGRAPHY_POLICY}"'
            ),
            1,
        )

    for node in spec["nodes"]:
        node_id = str(node["id"])
        variant = variant_name(seed, node_id)
        pattern = rf'(<g id="node-{re.escape(node_id)}"\s+)'
        replacement = rf'\1data-pencil-variant="{variant}" '
        text = re.sub(pattern, replacement, text, count=1)

    payload = text.encode("utf-8")
    try:
        ET.fromstring(payload)
    except ET.ParseError as exc:
        raise SketchPolishError(f"notebook-polished SVG is invalid XML: {exc}") from exc
    return payload


def audit_svg(svg_value: bytes | str, original_audit) -> dict[str, Any]:
    report = dict(original_audit(svg_value))
    if not report.get("ok"):
        return report
    text = svg_value.decode("utf-8") if isinstance(svg_value, bytes) else svg_value
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return {**report, "ok": False, "issues": [*report.get("issues", []), f"invalid-svg:{exc}"]}

    # Raw schema-1 render output is audited once before post-processing.  Only
    # enforce the extra contract after the polish marker has been attached.
    if root.get("data-sketch-polish") != POLICY_VERSION:
        return report

    namespace = "{http://www.w3.org/2000/svg}"
    issues = list(report.get("issues", []))
    if root.get("data-node-text-policy") != TEXT_FIT_POLICY:
        issues.append("node-text-policy-missing")
    if root.get("data-shape-policy") != SHAPE_POLICY:
        issues.append("shape-policy-missing")
    if root.get("data-title-meta-policy") != TITLE_META_POLICY:
        issues.append("title-meta-policy-missing")
    if root.get("data-svg-typography") != TYPOGRAPHY_POLICY:
        issues.append("svg-typography-policy-missing")

    kind_nodes = [
        node for node in root.iter(f"{namespace}text")
        if node.get("class") == "sketch-kind"
    ]
    if len(kind_nodes) != 1 or kind_nodes[0].get("data-role") != "figure-kind":
        issues.append("figure-kind-baseline-contract-missing")
    elif kind_nodes[0].get("y") not in {"52", "52.0", "52.00"}:
        issues.append("figure-kind-baseline-misaligned")

    for group in root.iter(f"{namespace}g"):
        group_id = group.get("id", "")
        if group_id.startswith("node-") and group.get("data-pencil-variant") not in {"a", "b", "c"}:
            issues.append(f"node-pencil-variant-missing:{group_id}")

    if 'font-family:"Neucha"' not in text or 'font-family:"Architects Daughter"' not in text:
        issues.append("standalone-svg-fonts-missing")

    return {**report, "ok": not issues, "issues": sorted(set(issues))}


def install() -> None:
    """Patch schema-1 renderer before the active hybrid runtime captures it."""
    if getattr(sketch, "_CARPETA_NOTEBOOK_POLISH", None) == POLICY_VERSION:
        return

    original_render = sketch.render_svg
    original_audit = sketch.audit_svg_style

    def polished_render(spec_value: Any):
        svg, report = original_render(spec_value)
        polished = postprocess_svg(svg, spec_value)
        audit = audit_svg(polished, original_audit)
        if not audit["ok"]:
            raise sketch.SketchSpecError(
                "notebook SVG failed polish audit: " + ", ".join(audit["issues"])
            )
        updated = dict(report)
        updated.update({
            "svg_sha256": sketch.digest_bytes(polished),
            "style_audit": audit,
            "notebook_polish": POLICY_VERSION,
            "node_text_policy": TEXT_FIT_POLICY,
            "shape_policy": SHAPE_POLICY,
            "title_meta_policy": TITLE_META_POLICY,
            "svg_typography": TYPOGRAPHY_POLICY,
        })
        return polished, updated

    def polished_audit(svg_value: bytes | str):
        return audit_svg(svg_value, original_audit)

    sketch._node_dimensions = node_dimensions  # type: ignore[assignment]
    sketch._node_path = node_path  # type: ignore[assignment]
    sketch.render_svg = polished_render  # type: ignore[assignment]
    sketch.audit_svg_style = polished_audit  # type: ignore[assignment]
    sketch._CARPETA_NOTEBOOK_POLISH = POLICY_VERSION


__all__ = [
    "POLICY_VERSION",
    "TEXT_FIT_POLICY",
    "SHAPE_POLICY",
    "TITLE_META_POLICY",
    "TYPOGRAPHY_POLICY",
    "node_dimensions",
    "node_path",
    "postprocess_svg",
    "audit_svg",
    "variant_name",
    "install",
]
