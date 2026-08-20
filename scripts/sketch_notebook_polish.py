#!/usr/bin/env python3
"""Notebook-specific polish for schema-1 deterministic sketch diagrams.

Presentation invariants that belong to Carpeta rather than to semantic plans:
text fits before fonts shrink, geometric nodes use deterministic pencil
variants, standalone SVGs carry notebook fonts, and the small figure-kind label
never collides with the handwritten title.
"""
from __future__ import annotations

import hashlib
import math
import re
import xml.etree.ElementTree as ET
from typing import Any

from scripts import sketch_figure as sketch

POLICY_VERSION = "carpeta-sketch-polish-v2"
TEXT_FIT_POLICY = "fit-first-v2"
SHAPE_POLICY = "pencil-shape-variants-v1"
TITLE_META_POLICY = "collision-safe-v2"
TYPOGRAPHY_POLICY = "carpeta-svg-fonts-v1"

NEUCHA_WOFF2 = "https://fonts.gstatic.com/s/neucha/v18/q5uGsou0JOdh94bfvQlt.woff2"
ARCHITECTS_TTF = "https://fonts.gstatic.com/s/architectsdaughter/v19/KtkxAKiDZI_td1Lkx62xHZHDtgO_Y-bvfY5q4szgE-Q.ttf"

TEXT_SCALE_BUDGET = 1.18
LABEL_CHAR_WIDTH = 10.4 * TEXT_SCALE_BUDGET
DETAIL_CHAR_WIDTH = 7.9 * TEXT_SCALE_BUDGET
NODE_PADDING_X = 24.0
NODE_PADDING_Y = 24.0

# Conservative width model for the 29px Architects Daughter title and 15px
# Neucha kind label.  The point is not typographic measurement precision: the
# safety gap deliberately errs on the side of moving the meta word away.
TITLE_CHAR_WIDTH = 15.2
KIND_CHAR_WIDTH = 8.2
TITLE_LEFT = 22.0
TITLE_KIND_RIGHT = 22.0
TITLE_KIND_GAP = 28.0
TITLE_INLINE_Y = 52.0
TITLE_META_LANE_Y = 22.0

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

KIND_LABELS = {
    "flow": "flujo",
    "tree": "árbol",
    "concept-map": "mapa conceptual",
    "relations": "relaciones",
    "technical-schematic": "esquema técnico",
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
    """Return shape-aware dimensions that fit text before shrinking anything."""
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
        height = max(152.0, height + 20.0)
    elif shape == "terminal":
        height = max(112.0, height)
    elif shape == "circle":
        diameter = max(width, height, 220.0)
        width = height = diameter

    return width, height, label_lines, detail_lines


def text_fit_issues(node: dict[str, Any], box: Any) -> list[str]:
    """Validate the same conservative content box used by node_dimensions."""
    shape = str(node.get("shape") or "rounded")
    inner_factor = INNER_WIDTH_FACTOR.get(shape, 0.88)
    safe_width = float(box.width) * inner_factor - NODE_PADDING_X * 2.0
    issues: list[str] = []
    for line in box.label_lines:
        estimated = len(line) * LABEL_CHAR_WIDTH
        if estimated > safe_width + LABEL_CHAR_WIDTH:
            issues.append(
                f"node-label-overflow:{node['id']}:{int(math.ceil(estimated))}>{int(math.floor(safe_width))}"
            )
    for line in box.detail_lines:
        estimated = len(line) * DETAIL_CHAR_WIDTH
        if estimated > safe_width + DETAIL_CHAR_WIDTH:
            issues.append(
                f"node-detail-overflow:{node['id']}:{int(math.ceil(estimated))}>{int(math.floor(safe_width))}"
            )
    return issues


def _outline_points(node: dict[str, Any], box: Any, seed: str) -> list[tuple[float, float]] | None:
    """Logical shape points with deterministic human variation.

    Routing still uses the unmodified bbox. Mid-edge ports therefore remain
    exact while the visible corners and shoulders vary by stable A/B/C style.
    """
    x, y = float(box.x), float(box.y)
    width, height = float(box.width), float(box.height)
    cx, cy = float(box.cx), float(box.cy)
    shape = str(node.get("shape") or "rounded")
    variant = _variant_index(seed, str(node.get("id") or "node"))
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
    """Render every schema-1 geometry through the notebook pencil language."""
    points = _outline_points(node, box, seed)
    shape = str(node.get("shape") or "rounded")
    key = f'{node.get("id", "node")}:{trace}'
    variant = _variant_index(seed, str(node.get("id") or "node"))

    if points is not None:
        return sketch._rough_polygon(points, seed, key, scale=scale)
    if shape == "datastore":
        return sketch._rounded_path(box, (18.0, 24.0, 30.0)[variant], seed, key, scale=scale)
    if shape == "rounded":
        return sketch._rounded_path(box, (10.0, 15.0, 20.0)[variant], seed, key, scale=scale)
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


def title_meta_placement(spec: dict[str, Any], canvas_width: float) -> tuple[str, float]:
    """Keep the kind tag inline only when the title leaves a safe gap."""
    title_lines = sketch._wrap(str(spec.get("title") or ""), 54)
    first_line = title_lines[0] if title_lines else ""
    kind = KIND_LABELS.get(str(spec.get("kind") or ""), "")
    title_right = TITLE_LEFT + len(first_line) * TITLE_CHAR_WIDTH
    kind_left = canvas_width - TITLE_KIND_RIGHT - len(kind) * KIND_CHAR_WIDTH
    if len(title_lines) == 1 and title_right + TITLE_KIND_GAP <= kind_left:
        return "inline", TITLE_INLINE_Y
    return "top-right", TITLE_META_LANE_Y


def _canvas_width(svg_text: str) -> float:
    match = re.search(r'<svg\b[^>]*\bwidth="([0-9.]+)"', svg_text, flags=re.IGNORECASE)
    if not match:
        raise SketchPolishError("SVG width missing before title-meta placement")
    return float(match.group(1))


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

    placement, kind_y = title_meta_placement(spec, _canvas_width(text))
    kind_pattern = r'<text class="sketch-kind" x="([^"]+)" y="48" text-anchor="end">'
    kind_replacement = (
        rf'<text class="sketch-kind" x="\1" y="{kind_y:.2f}" text-anchor="end" '
        rf'dominant-baseline="alphabetic" data-role="figure-kind" data-placement="{placement}">'
    )
    text, substitutions = re.subn(kind_pattern, kind_replacement, text, count=1)
    if substitutions != 1:
        raise SketchPolishError("figure kind label could not be positioned")

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
        text = re.sub(
            rf'(<g id="node-{re.escape(node_id)}"\s+)',
            rf'\1data-pencil-variant="{variant}" ',
            text,
            count=1,
        )

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

    kind_nodes = [node for node in root.iter(f"{namespace}text") if node.get("class") == "sketch-kind"]
    if len(kind_nodes) != 1 or kind_nodes[0].get("data-role") != "figure-kind":
        issues.append("figure-kind-placement-contract-missing")
    else:
        placement = kind_nodes[0].get("data-placement")
        y = kind_nodes[0].get("y")
        if placement == "inline" and y not in {"52", "52.0", "52.00"}:
            issues.append("figure-kind-inline-baseline-misaligned")
        elif placement == "top-right" and y not in {"22", "22.0", "22.00"}:
            issues.append("figure-kind-meta-lane-misaligned")
        elif placement not in {"inline", "top-right"}:
            issues.append("figure-kind-placement-invalid")

    for group in root.iter(f"{namespace}g"):
        group_id = group.get("id", "")
        if group_id.startswith("node-") and group.get("data-pencil-variant") not in {"a", "b", "c"}:
            issues.append(f"node-pencil-variant-missing:{group_id}")

    if 'font-family:"Neucha"' not in text or 'font-family:"Architects Daughter"' not in text:
        issues.append("standalone-svg-fonts-missing")

    return {**report, "ok": not issues, "issues": sorted(set(issues))}


def install() -> None:
    """Patch schema-1 renderer before runtime/geometry wrappers capture it."""
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
    "text_fit_issues",
    "node_path",
    "postprocess_svg",
    "audit_svg",
    "title_meta_placement",
    "variant_name",
    "install",
]
