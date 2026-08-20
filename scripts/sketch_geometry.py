#!/usr/bin/env python3
"""Deterministic geometry and render policy for Hybrid V1 sketch diagrams.

The semantic sketch spec stays compact and coordinate-free. This module owns the
cheap guarantees that should never require a vision model: notebook-scale
legibility, renderer-owned spacing, safe connector ports, collision-free edge
labels, deterministic pencil roughness and the notebook typography used inside
standalone SVG images.
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import pipeline_run, sketch_figure, visual_plan_hybrid  # noqa: E402
from scripts.course_layout import has_unit_layout, unit_root  # noqa: E402
from scripts.unit_identity import resolve_unit  # noqa: E402

# Geometry is calibrated against the notebook's ~44rem wide content lane. A
# viewBox wider than this budget gets scaled down by <img max-width:100%>, which
# was the main reason labels became tiny even though the SVG font sizes looked
# healthy in isolation.
NOTEBOOK_RENDER_WIDTH = 704.0
MAX_VIEWBOX_WIDTH = 960.0
MAX_TALL_ASPECT_RATIO = 2.15

# Direction-aware gaps: horizontal flows need substantially less inter-rank
# whitespace than vertical diagrams. The old global 118px rank minimum made a
# 4-5 step flow much wider than the notebook and therefore shrank its text.
MIN_NODE_GAP = 44
MIN_RANK_GAP = 84
VERTICAL_RANK_GAP = 104
HORIZONTAL_RANK_GAP_MIN = 32
HORIZONTAL_RANK_GAP_MAX = 40
HORIZONTAL_NODE_GAP_MIN = 36
HORIZONTAL_NODE_GAP_MAX = 64
VERTICAL_NODE_GAP_MAX = 76

NODE_LABEL_FONT_SIZE = 22.0
NODE_DETAIL_FONT_SIZE = 17.0
EDGE_LABEL_FONT_SIZE = 15.0
NODE_LABEL_MIN_RENDERED = 15.0
NODE_DETAIL_MIN_RENDERED = 11.5
EDGE_LABEL_MIN_RENDERED = 10.5

EDGE_LABEL_CHAR_WIDTH = 7.4
EDGE_LABEL_HEIGHT = 23.0
EDGE_LABEL_MAX_WIDTH = 240.0
EDGE_LABEL_GAP = 12.0
EDGE_LABEL_NODE_GAP = 14.0
CANVAS_MARGIN = 14.0
CONNECTOR_TOLERANCE = 1.75
CONNECTOR_NODE_CLEARANCE = 3.0
LABEL_LANES = (0.0, -28.0, 28.0, -56.0, 56.0, -84.0, 84.0, -112.0, 112.0)

SIZE_CLASSES = (
    ("S", 700.0),
    ("M", 800.0),
    ("L", 880.0),
    ("XL", MAX_VIEWBOX_WIDTH),
)

NEUCHA_WOFF2 = "https://fonts.gstatic.com/s/neucha/v18/q5uGsou0JOdh94bfvQlt.woff2"
ARCHITECTS_TTF = "https://fonts.gstatic.com/s/architectsdaughter/v19/KtkxAKiDZI_td1Lkx62xHZHDtgO_Y-bvfY5q4szgE-Q.ttf"
TYPOGRAPHY_POLICY = "carpeta-notebook-v1"
PENCIL_POLICY = "deterministic-pencil-v2"


class GeometryError(ValueError):
    pass


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def intersects(self, other: "Rect", gap: float = 0.0) -> bool:
        return not (
            self.right + gap <= other.left
            or other.right + gap <= self.left
            or self.bottom + gap <= other.top
            or other.bottom + gap <= self.top
        )

    def contains_strict(self, x: float, y: float, inset: float = 0.0) -> bool:
        return (
            self.left + inset < x < self.right - inset
            and self.top + inset < y < self.bottom - inset
        )


def constrained_spec(spec_value: Any) -> dict[str, Any]:
    """Return a normalized copy with renderer-owned safe spacing bounds."""
    spec = sketch_figure.validate_spec(spec_value)
    effective = copy.deepcopy(spec)
    layout = effective["layout"]
    if layout["direction"] == "left-to-right":
        layout["rank_gap"] = min(
            HORIZONTAL_RANK_GAP_MAX,
            max(int(layout["rank_gap"]), HORIZONTAL_RANK_GAP_MIN),
        )
        layout["node_gap"] = min(
            HORIZONTAL_NODE_GAP_MAX,
            max(int(layout["node_gap"]), HORIZONTAL_NODE_GAP_MIN),
        )
    else:
        layout["rank_gap"] = max(int(layout["rank_gap"]), VERTICAL_RANK_GAP)
        layout["node_gap"] = min(
            VERTICAL_NODE_GAP_MAX,
            max(int(layout["node_gap"]), MIN_NODE_GAP),
        )
    return effective


def _rank_counts(spec: dict[str, Any]) -> tuple[int, int]:
    ranks = sketch_figure._rank_nodes(spec)
    counts: dict[int, int] = {}
    for node in spec["nodes"]:
        rank = ranks[node["id"]]
        counts[rank] = counts.get(rank, 0) + 1
    return len(counts), max(counts.values(), default=1)


def _policy_node_dimensions(
    node: dict[str, Any],
    *,
    direction: str,
    node_count: int,
    max_parallel: int,
) -> tuple[float, float, tuple[str, ...], tuple[str, ...]]:
    """Keep node text large by compacting geometry instead of shrinking fonts."""
    label = node["label"]
    detail = node["detail"]
    longest = max((len(word) for word in label.split()), default=8)

    if direction == "left-to-right":
        if node_count >= 6:
            # Six or more sequential columns cannot remain notebook-legible;
            # keep a readable node floor and let the width gate demand a reflow.
            min_width, max_width = 132.0, 150.0
        elif node_count == 5:
            # 5 * 136 + 4 * 40 + 120 margins = 960px, the notebook budget.
            min_width, max_width = 132.0, 136.0
        elif node_count == 4:
            min_width, max_width = 150.0, 180.0
        else:
            min_width, max_width = 174.0, 226.0
    elif max_parallel >= 3:
        min_width, max_width = 176.0, 244.0
    elif max_parallel == 2:
        min_width, max_width = 188.0, 274.0
    else:
        min_width, max_width = 202.0, 300.0

    width = max(
        min_width,
        108.0 + min(len(label), 42) * 2.45,
        42.0 + longest * 8.7,
    )
    width = min(max_width, width)
    if node["shape"] in {"circle", "decision"}:
        width = min(max_width + 20.0, max(width, min_width + 22.0))

    label_capacity = max(12, int((width - 34.0) / 10.6))
    detail_capacity = max(17, int((width - 34.0) / 7.9))
    label_lines = sketch_figure._wrap(label, label_capacity)
    detail_lines = sketch_figure._wrap(detail, detail_capacity)
    height = 42 + len(label_lines) * 28 + len(detail_lines) * 21
    if detail_lines:
        height += 8
    height = max(92.0, float(height))
    if node["shape"] == "decision":
        height = max(132.0, height + 12.0)
    if node["shape"] == "circle":
        width = height = max(width, height, 170.0)
    return width, height, label_lines, detail_lines


def _layout_with_policy(
    spec_value: Any,
    layout_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]],
) -> tuple[dict[str, Any], float, float, float]:
    effective = constrained_spec(spec_value)
    _rank_count, max_parallel = _rank_counts(effective)
    direction = effective["layout"]["direction"]
    node_count = len(effective["nodes"])
    original_dimensions = sketch_figure._node_dimensions

    def safe_dimensions(node: dict[str, Any]):
        return _policy_node_dimensions(
            node,
            direction=direction,
            node_count=node_count,
            max_parallel=max_parallel,
        )

    sketch_figure._node_dimensions = safe_dimensions  # type: ignore[assignment]
    try:
        return layout_fn(effective)
    finally:
        sketch_figure._node_dimensions = original_dimensions  # type: ignore[assignment]


def constrained_layout(
    spec_value: Any,
    original_layout: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]] | None = None,
):
    layout_fn = original_layout or sketch_figure._layout
    return _layout_with_policy(spec_value, layout_fn)


def _node_rect(box: Any) -> Rect:
    return Rect(float(box.x), float(box.y), float(box.x + box.width), float(box.y + box.height))


def _label_rect(label: str, x: float, geometry_y: float) -> Rect:
    baseline = geometry_y - 7.0
    width = max(42.0, len(label) * EDGE_LABEL_CHAR_WIDTH + 14.0)
    half = width / 2.0
    return Rect(x - half, baseline - 18.0, x + half, baseline + 5.0)


def _inside_canvas(rect: Rect, width: float, height: float) -> bool:
    return (
        rect.left >= CANVAS_MARGIN
        and rect.right <= width - CANVAS_MARGIN
        and rect.top >= CANVAS_MARGIN
        and rect.bottom <= height - CANVAS_MARGIN
    )


def _node_overlap_issues(boxes: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    items = list(boxes.items())
    for index, (left_id, left_box) in enumerate(items):
        left = _node_rect(left_box)
        for right_id, right_box in items[index + 1 :]:
            right = _node_rect(right_box)
            if left.intersects(right, 0.0):
                issues.append(f"node-overlap:{left_id}:{right_id}")
    return issues


def _point_on_rect_border(point: tuple[float, float], rect: Rect, tolerance: float = CONNECTOR_TOLERANCE) -> bool:
    x, y = point
    horizontal = (
        rect.left - tolerance <= x <= rect.right + tolerance
        and (abs(y - rect.top) <= tolerance or abs(y - rect.bottom) <= tolerance)
    )
    vertical = (
        rect.top - tolerance <= y <= rect.bottom + tolerance
        and (abs(x - rect.left) <= tolerance or abs(x - rect.right) <= tolerance)
    )
    return horizontal or vertical


def _segment_hits_rect_interior(
    start: tuple[float, float], end: tuple[float, float], rect: Rect
) -> bool:
    """Detect intrusion for the orthogonal connectors emitted by sketch_figure."""
    x1, y1 = start
    x2, y2 = end
    eps = CONNECTOR_TOLERANCE
    if abs(y1 - y2) <= eps:
        y = (y1 + y2) / 2.0
        if not (rect.top + eps < y < rect.bottom - eps):
            return False
        low, high = sorted((x1, x2))
        return high > rect.left + eps and low < rect.right - eps
    if abs(x1 - x2) <= eps:
        x = (x1 + x2) / 2.0
        if not (rect.left + eps < x < rect.right - eps):
            return False
        low, high = sorted((y1, y2))
        return high > rect.top + eps and low < rect.bottom - eps

    # Fallback for future non-orthogonal connectors: sample the segment densely
    # enough to catch an actual pass through a node. This remains deterministic
    # and cheap for the small graphs allowed by the contract.
    steps = max(8, int(math.ceil(math.hypot(x2 - x1, y2 - y1) / 8.0)))
    for index in range(1, steps):
        t = index / steps
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        if rect.contains_strict(x, y, CONNECTOR_NODE_CLEARANCE):
            return True
    return False


def _connector_issues(
    spec: dict[str, Any],
    boxes: dict[str, Any],
    edge_fn: Callable[[Any, Any, str, int], tuple[list[tuple[float, float]], float, float]],
) -> tuple[list[str], list[dict[str, Any]]]:
    issues: list[str] = []
    paths: list[dict[str, Any]] = []
    node_rects = {node_id: _node_rect(box) for node_id, box in boxes.items()}

    for index, edge in enumerate(spec["edges"]):
        points, _label_x, _label_y = edge_fn(
            boxes[edge["from"]], boxes[edge["to"]], spec["layout"]["direction"], index
        )
        if len(points) < 2:
            issues.append(f"connector-too-short:{index}:{edge['from']}->{edge['to']}")
            continue
        source_rect = node_rects[edge["from"]]
        target_rect = node_rects[edge["to"]]
        if not _point_on_rect_border(points[0], source_rect):
            issues.append(f"connector-source-not-on-border:{index}:{edge['from']}")
        if not _point_on_rect_border(points[-1], target_rect):
            issues.append(f"connector-target-not-on-border:{index}:{edge['to']}")

        if edge["from"] != edge["to"]:
            for node_id, rect in node_rects.items():
                if node_id in {edge["from"], edge["to"]}:
                    continue
                if any(
                    _segment_hits_rect_interior(points[segment], points[segment + 1], rect)
                    for segment in range(len(points) - 1)
                ):
                    issues.append(
                        f"connector-intrusion:{index}:{edge['from']}->{edge['to']}:{node_id}"
                    )

        paths.append({
            "edge_index": index,
            "from": edge["from"],
            "to": edge["to"],
            "points": [[round(x, 2), round(y, 2)] for x, y in points],
        })
    return issues, paths


def _size_class(width: float) -> str:
    for name, maximum in SIZE_CLASSES:
        if width <= maximum:
            return name
    return "OVERSIZE"


def _legibility_issues(width: float, height: float) -> tuple[list[str], dict[str, float | str]]:
    issues: list[str] = []
    scale = min(1.0, NOTEBOOK_RENDER_WIDTH / max(width, 1.0))
    rendered_label = NODE_LABEL_FONT_SIZE * scale
    rendered_detail = NODE_DETAIL_FONT_SIZE * scale
    rendered_edge = EDGE_LABEL_FONT_SIZE * scale
    if width > MAX_VIEWBOX_WIDTH:
        issues.append(f"canvas-too-wide:{int(round(width))}>{int(MAX_VIEWBOX_WIDTH)}")
    if rendered_label < NODE_LABEL_MIN_RENDERED:
        issues.append(f"font-too-small:node-label:{rendered_label:.1f}<{NODE_LABEL_MIN_RENDERED:.1f}")
    if rendered_detail < NODE_DETAIL_MIN_RENDERED:
        issues.append(f"font-too-small:node-detail:{rendered_detail:.1f}<{NODE_DETAIL_MIN_RENDERED:.1f}")
    if rendered_edge < EDGE_LABEL_MIN_RENDERED:
        issues.append(f"font-too-small:edge-label:{rendered_edge:.1f}<{EDGE_LABEL_MIN_RENDERED:.1f}")
    aspect = height / max(width, 1.0)
    if aspect > MAX_TALL_ASPECT_RATIO:
        issues.append(f"aspect-too-tall:{aspect:.2f}>{MAX_TALL_ASPECT_RATIO:.2f}")
    return issues, {
        "size_class": _size_class(width),
        "notebook_scale": round(scale, 4),
        "rendered_node_label_px": round(rendered_label, 2),
        "rendered_node_detail_px": round(rendered_detail, 2),
        "rendered_edge_label_px": round(rendered_edge, 2),
        "aspect_ratio": round(aspect, 3),
    }


def analyze_spec(
    spec_value: Any,
    *,
    layout_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]] | None = None,
    edge_fn: Callable[[Any, Any, str, int], tuple[list[tuple[float, float]], float, float]] | None = None,
) -> dict[str, Any]:
    """Return one deterministic, machine-checkable preflight report."""
    spec = sketch_figure.validate_spec(spec_value)
    effective = constrained_spec(spec)
    raw_layout = layout_fn or sketch_figure._layout
    raw_edge = edge_fn or sketch_figure._edge_geometry
    boxes, width, height, _title_height = _layout_with_policy(effective, raw_layout)

    issues = _node_overlap_issues(boxes)
    connector_issues, connector_paths = _connector_issues(effective, boxes, raw_edge)
    issues.extend(connector_issues)
    legibility_issues, legibility = _legibility_issues(width, height)
    issues.extend(legibility_issues)

    occupied_labels: list[tuple[int, Rect]] = []
    label_offsets: dict[int, float] = {}
    label_boxes: list[dict[str, Any]] = []
    node_rects = [(node_id, _node_rect(box)) for node_id, box in boxes.items()]

    for index, edge in enumerate(spec["edges"]):
        label = str(edge.get("label") or "")
        if not label:
            label_offsets[index] = 0.0
            continue
        estimated_width = max(42.0, len(label) * EDGE_LABEL_CHAR_WIDTH + 14.0)
        if estimated_width > EDGE_LABEL_MAX_WIDTH:
            issues.append(
                f"edge-label-too-wide:{index}:{int(math.ceil(estimated_width))}>{int(EDGE_LABEL_MAX_WIDTH)}"
            )
            continue

        _points, base_x, base_y = raw_edge(
            boxes[edge["from"]], boxes[edge["to"]], effective["layout"]["direction"], index
        )
        chosen: tuple[float, Rect] | None = None
        for offset in LABEL_LANES:
            candidate = _label_rect(label, base_x, base_y + offset)
            if not _inside_canvas(candidate, width, height):
                continue
            if any(candidate.intersects(rect, EDGE_LABEL_NODE_GAP) for _node_id, rect in node_rects):
                continue
            if any(candidate.intersects(rect, EDGE_LABEL_GAP) for _other_index, rect in occupied_labels):
                continue
            chosen = (offset, candidate)
            break
        if chosen is None:
            issues.append(f"edge-label-no-safe-lane:{index}:{edge['from']}->{edge['to']}")
            continue
        offset, rect = chosen
        label_offsets[index] = offset
        occupied_labels.append((index, rect))
        label_boxes.append({
            "edge_index": index,
            "from": edge["from"],
            "to": edge["to"],
            "label": label,
            "offset": offset,
            "box": [round(rect.left, 2), round(rect.top, 2), round(rect.right, 2), round(rect.bottom, 2)],
        })

    return {
        "ok": not issues,
        "issues": sorted(set(issues)),
        "constraints": {
            "min_node_gap": MIN_NODE_GAP,
            "min_rank_gap": MIN_RANK_GAP,
            "max_viewbox_width": int(MAX_VIEWBOX_WIDTH),
            "max_tall_aspect_ratio": MAX_TALL_ASPECT_RATIO,
            "edge_label_gap": EDGE_LABEL_GAP,
            "edge_label_node_gap": EDGE_LABEL_NODE_GAP,
            "edge_label_max_width": EDGE_LABEL_MAX_WIDTH,
            "connector_tolerance": CONNECTOR_TOLERANCE,
        },
        "effective_layout": dict(effective["layout"]),
        "width": int(round(width)),
        "height": int(round(height)),
        **legibility,
        "label_offsets": {str(key): value for key, value in sorted(label_offsets.items())},
        "label_boxes": label_boxes,
        "connector_paths": connector_paths,
    }


def _policy_rough_polyline(
    points: list[tuple[float, float]],
    seed: str,
    key: str,
    *,
    closed: bool = False,
    scale: float = 1.0,
) -> str:
    """Pencil path with exact connector ports and more visible shape roughness."""
    if not points:
        return ""
    is_connector = key.startswith("edge-") and not closed
    effective_scale = scale * (1.35 if closed else 1.0)
    varied: list[tuple[float, float]] = []
    last_index = len(points) - 1
    for index, (x, y) in enumerate(points):
        lock_port = is_connector and index in {0, last_index}
        if lock_port:
            varied.append((x, y))
        else:
            varied.append((
                x + sketch_figure._jitter(seed, key, index, "x", scale=0.72 * effective_scale),
                y + sketch_figure._jitter(seed, key, index, "y", scale=0.72 * effective_scale),
            ))

    commands = [f"M {varied[0][0]:.2f} {varied[0][1]:.2f}"]
    targets = varied[1:] + ([varied[0]] if closed else [])
    start = varied[0]
    for index, target in enumerate(targets):
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        length = max(1.0, math.hypot(dx, dy))
        bend = sketch_figure._jitter(seed, key, index, "bend", scale=1.55 * effective_scale)
        along = sketch_figure._jitter(seed, key, index, "along", scale=0.45 * effective_scale)
        control_x = (start[0] + target[0]) / 2 + (-dy / length) * bend + (dx / length) * along
        control_y = (start[1] + target[1]) / 2 + (dx / length) * bend + (dy / length) * along
        commands.append(f"Q {control_x:.2f} {control_y:.2f} {target[0]:.2f} {target[1]:.2f}")
        start = target
    if closed:
        commands.append("Z")
    return " ".join(commands)


def _apply_notebook_typography(svg_bytes: bytes, size_class: str) -> bytes:
    text = svg_bytes.decode("utf-8")
    font_faces = (
        f'@font-face{{font-family:"Neucha";font-style:normal;font-weight:400;font-display:swap;'
        f'src:local("Neucha"),url("{NEUCHA_WOFF2}") format("woff2")}}'
        f'@font-face{{font-family:"Architects Daughter";font-style:normal;font-weight:400;font-display:swap;'
        f'src:local("Architects Daughter"),url("{ARCHITECTS_TTF}") format("truetype")}}'
    )
    text = text.replace("<style>", "<style>" + font_faces, 1)
    replacements = {
        "sketch-label": f'font:400 {int(NODE_LABEL_FONT_SIZE)}px "Neucha","Segoe Print","Comic Sans MS",cursive',
        "sketch-detail": f'font:400 {int(NODE_DETAIL_FONT_SIZE)}px "Neucha","Segoe Print","Comic Sans MS",cursive',
        "sketch-title": 'font:400 29px "Architects Daughter","Segoe Print","Comic Sans MS",cursive',
        "sketch-kind": 'font:400 15px "Neucha","Segoe Print","Comic Sans MS",cursive',
        "sketch-edge-label": f'font:400 {int(EDGE_LABEL_FONT_SIZE)}px "Neucha","Segoe Print","Comic Sans MS",cursive',
        "sketch-group-label": 'font:400 15px "Neucha","Segoe Print","Comic Sans MS",cursive',
    }
    for class_name, font_decl in replacements.items():
        text = re.sub(
            rf'(\.{re.escape(class_name)}\{{)font:[^;]+;',
            rf'\1{font_decl};',
            text,
            count=1,
        )
    marker = 'data-pencil-style="graphite-overlay-v1">'
    enriched = (
        f'data-pencil-style="graphite-overlay-v1" data-layout-size="{html.escape(size_class, quote=True)}" '
        f'data-typography="{TYPOGRAPHY_POLICY}" data-pencil-policy="{PENCIL_POLICY}">'
    )
    text = text.replace(marker, enriched, 1)
    return text.encode("utf-8")


def install_for_spec(spec_value: Any):
    """Install the exact preflighted geometry + render policy for one diagram."""
    original_layout = sketch_figure._layout
    original_edge = sketch_figure._edge_geometry
    original_rough_polyline = sketch_figure._rough_polyline
    original_render_svg = sketch_figure.render_svg

    report = analyze_spec(spec_value, layout_fn=original_layout, edge_fn=original_edge)
    if not report["ok"]:
        raise GeometryError("; ".join(report["issues"]))
    offsets = {int(key): float(value) for key, value in report["label_offsets"].items()}

    def safe_layout(spec: dict[str, Any]):
        return _layout_with_policy(spec, original_layout)

    def safe_edge(start: Any, end: Any, direction: str, index: int):
        points, label_x, label_y = original_edge(start, end, direction, index)
        return points, label_x, label_y + offsets.get(index, 0.0)

    def safe_render(spec: Any):
        svg_bytes, render_report = original_render_svg(spec)
        svg_bytes = _apply_notebook_typography(svg_bytes, str(report["size_class"]))
        style_audit = sketch_figure.audit_svg_style(svg_bytes)
        if not style_audit["ok"]:
            raise sketch_figure.SketchSpecError(
                f"generated SVG failed style audit: {', '.join(style_audit['issues'])}"
            )
        updated = dict(render_report)
        updated.update({
            "svg_sha256": sketch_figure.digest_bytes(svg_bytes),
            "style_audit": style_audit,
            "size_class": report["size_class"],
            "typography_policy": TYPOGRAPHY_POLICY,
            "pencil_policy": PENCIL_POLICY,
        })
        return svg_bytes, updated

    sketch_figure._layout = safe_layout  # type: ignore[assignment]
    sketch_figure._edge_geometry = safe_edge  # type: ignore[assignment]
    sketch_figure._rough_polyline = _policy_rough_polyline  # type: ignore[assignment]
    sketch_figure.render_svg = safe_render  # type: ignore[assignment]

    def restore() -> None:
        sketch_figure._layout = original_layout  # type: ignore[assignment]
        sketch_figure._edge_geometry = original_edge  # type: ignore[assignment]
        sketch_figure._rough_polyline = original_rough_polyline  # type: ignore[assignment]
        sketch_figure.render_svg = original_render_svg  # type: ignore[assignment]

    return report, restore


def validate_run_plan(run_value: str) -> dict[str, Any]:
    run = pipeline_run.resolve_run(run_value)
    inp = json.loads((run / "01-input.json").read_text(encoding="utf-8"))
    course = (ROOT / str(inp["course"])).resolve()
    unit_id = str(inp.get("unit_id") or "").strip()
    if not course.is_dir() or not unit_id:
        raise GeometryError("run context is missing course/unit")
    resolved = resolve_unit(course, unit_id)
    if not resolved.get("unit_id"):
        raise GeometryError(f"could not resolve unit: {unit_id}")
    if has_unit_layout(course):
        unit_root(course, unit_id)
    plan_path = run / "02-plan.json"
    selected = visual_plan_hybrid.inspect_plan(course, unit_id, plan_path)
    figures: list[dict[str, Any]] = []
    issues: list[str] = []
    for row in selected:
        if row.get("visual_medium") != "diagram":
            continue
        report = analyze_spec(row["spec"])
        figures.append({"concept_id": row["concept_id"], "derived_figure_id": row["derived_figure_id"], **report})
        issues.extend(f"{row['derived_figure_id']}:{issue}" for issue in report["issues"])
    return {"ok": not issues, "issues": issues, "figures": figures}


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic geometry gate for Hybrid V1 diagrams")
    sub = ap.add_subparsers(dest="cmd", required=True)
    validate = sub.add_parser("validate-plan")
    validate.add_argument("--run", required=True)
    args = ap.parse_args()
    try:
        report = validate_run_plan(args.run)
    except (GeometryError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "issues": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
