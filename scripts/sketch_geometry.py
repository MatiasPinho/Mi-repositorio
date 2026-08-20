#!/usr/bin/env python3
"""Deterministic geometry gate for Hybrid V1 notebook diagrams.

This module is the cheap, local visual contract used before and during summary
visual materialization.  It deliberately keeps semantic specs coordinate-free
while making the renderer own the things a model should never have to guess:

- final notebook legibility;
- fit-first node sizing;
- compact orientation for simple flows;
- safe connector ports and routing clearance;
- collision-free edge-label lanes;
- bounded aspect ratio / canvas width;
- notebook pencil shapes and typography.

No model or vision call is required.
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

from scripts import pipeline_run, sketch_figure, sketch_notebook_polish, visual_plan_hybrid  # noqa: E402
from scripts.course_layout import has_unit_layout, unit_root  # noqa: E402
from scripts.scene_pencil import rough_polyline as pencil_rough_polyline  # noqa: E402
from scripts.unit_identity import resolve_unit  # noqa: E402

NOTEBOOK_RENDER_WIDTH = 704.0
MAX_VIEWBOX_WIDTH = 960.0
MAX_TALL_ASPECT_RATIO = 2.15

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

# Prefer moving labels along the free inter-rank corridor before moving them
# sideways. Crossed comparison edges sometimes need a small second dimension,
# so x lanes are explicit rather than allowing arbitrary positions.
LABEL_Y_LANES = (0.0, -28.0, 28.0, -56.0, 56.0, -84.0, 84.0, -112.0, 112.0)
LABEL_X_LANES = (0.0, -48.0, 48.0, -96.0, 96.0, -144.0, 144.0)
LABEL_LANES = LABEL_Y_LANES  # compatibility for older callers/tests

SIZE_CLASSES = (
    ("S", 700.0),
    ("M", 800.0),
    ("L", 880.0),
    ("XL", MAX_VIEWBOX_WIDTH),
)

TYPOGRAPHY_POLICY = "carpeta-notebook-v1"
PENCIL_POLICY = "deterministic-pencil-v3"
GEOMETRY_POLICY = "fit-first-geometry-v2"
AUTO_FLOW_POLICY = "linear-flow-auto-horizontal-v1"


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


def _is_linear_flow(spec: dict[str, Any]) -> bool:
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    if spec.get("kind") != "flow" or not (2 <= len(nodes) <= 4):
        return False
    if len(edges) != len(nodes) - 1:
        return False
    ids = {node["id"] for node in nodes}
    indegree = {node_id: 0 for node_id in ids}
    outdegree = {node_id: 0 for node_id in ids}
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        if source not in ids or target not in ids or source == target:
            return False
        outdegree[source] += 1
        indegree[target] += 1
    return (
        sum(value == 0 for value in indegree.values()) == 1
        and sum(value == 0 for value in outdegree.values()) == 1
        and all(value <= 1 for value in indegree.values())
        and all(value <= 1 for value in outdegree.values())
    )


def _projected_horizontal_width(spec: dict[str, Any]) -> float:
    widths = [sketch_notebook_polish.node_dimensions(node)[0] for node in spec["nodes"]]
    gap_count = max(0, len(widths) - 1)
    return sum(widths) + gap_count * HORIZONTAL_RANK_GAP_MAX + 120.0


def _should_auto_horizontal(spec: dict[str, Any]) -> bool:
    if spec["layout"]["direction"] != "top-to-bottom":
        return False
    if not _is_linear_flow(spec):
        return False
    return _projected_horizontal_width(spec) <= MAX_VIEWBOX_WIDTH


def constrained_spec(spec_value: Any) -> dict[str, Any]:
    """Normalize once, then apply renderer-owned spacing/orientation policy.

    Horizontal rank gaps intentionally go below the public schema's generic
    minimum.  The effective spec therefore must never be fed back through
    ``validate_spec``.  It is an internal layout document, not a user spec.
    """
    spec = sketch_figure.validate_spec(spec_value)
    effective = copy.deepcopy(spec)
    layout = effective["layout"]

    if _should_auto_horizontal(effective):
        layout["direction"] = "left-to-right"
        effective["_geometry_auto_direction"] = AUTO_FLOW_POLICY

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


def _fit_first_dimensions(node: dict[str, Any]):
    # One source of truth for the final node content box.  Long labels/details
    # make the box grow or wrap; font-size is never the escape hatch.
    return sketch_notebook_polish.node_dimensions(node)


def _layout_effective(
    effective: dict[str, Any],
    layout_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]],
) -> tuple[dict[str, Any], float, float, float]:
    original_dimensions = sketch_figure._node_dimensions
    sketch_figure._node_dimensions = _fit_first_dimensions  # type: ignore[assignment]
    try:
        return layout_fn(effective)
    finally:
        sketch_figure._node_dimensions = original_dimensions  # type: ignore[assignment]


def _layout_with_policy(
    spec_value: Any,
    layout_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]],
) -> tuple[dict[str, Any], float, float, float]:
    return _layout_effective(constrained_spec(spec_value), layout_fn)


def constrained_layout(
    spec_value: Any,
    original_layout: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]] | None = None,
):
    return _layout_with_policy(spec_value, original_layout or sketch_figure._layout)


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
            if left.intersects(_node_rect(right_box)):
                issues.append(f"node-overlap:{left_id}:{right_id}")
    return issues


def _point_on_rect_border(
    point: tuple[float, float], rect: Rect, tolerance: float = CONNECTOR_TOLERANCE
) -> bool:
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

    steps = max(8, int(math.ceil(math.hypot(x2 - x1, y2 - y1) / 8.0)))
    for index in range(1, steps):
        t = index / steps
        if rect.contains_strict(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, CONNECTOR_NODE_CLEARANCE):
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


def _find_label_lane(
    label: str,
    base_x: float,
    base_y: float,
    *,
    width: float,
    height: float,
    node_rects: list[tuple[str, Rect]],
    occupied: list[tuple[int, Rect]],
) -> tuple[float, float, Rect] | None:
    for y_offset in LABEL_Y_LANES:
        for x_offset in LABEL_X_LANES:
            candidate = _label_rect(label, base_x + x_offset, base_y + y_offset)
            if not _inside_canvas(candidate, width, height):
                continue
            if any(candidate.intersects(rect, EDGE_LABEL_NODE_GAP) for _node_id, rect in node_rects):
                continue
            if any(candidate.intersects(rect, EDGE_LABEL_GAP) for _index, rect in occupied):
                continue
            return x_offset, y_offset, candidate
    return None


def _analyze_effective(
    spec: dict[str, Any],
    effective: dict[str, Any],
    *,
    layout_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]],
    edge_fn: Callable[[Any, Any, str, int], tuple[list[tuple[float, float]], float, float]],
) -> dict[str, Any]:
    boxes, width, height, _title_height = _layout_effective(effective, layout_fn)
    issues = _node_overlap_issues(boxes)
    connector_issues, connector_paths = _connector_issues(effective, boxes, edge_fn)
    issues.extend(connector_issues)
    legibility_issues, legibility = _legibility_issues(width, height)
    issues.extend(legibility_issues)

    occupied_labels: list[tuple[int, Rect]] = []
    label_offsets: dict[int, float] = {}
    label_x_offsets: dict[int, float] = {}
    label_boxes: list[dict[str, Any]] = []
    node_rects = [(node_id, _node_rect(box)) for node_id, box in boxes.items()]

    for index, edge in enumerate(spec["edges"]):
        label = str(edge.get("label") or "")
        if not label:
            label_offsets[index] = 0.0
            label_x_offsets[index] = 0.0
            continue
        estimated_width = max(42.0, len(label) * EDGE_LABEL_CHAR_WIDTH + 14.0)
        if estimated_width > EDGE_LABEL_MAX_WIDTH:
            issues.append(
                f"edge-label-too-wide:{index}:{int(math.ceil(estimated_width))}>{int(EDGE_LABEL_MAX_WIDTH)}"
            )
            continue

        _points, base_x, base_y = edge_fn(
            boxes[edge["from"]], boxes[edge["to"]], effective["layout"]["direction"], index
        )
        chosen = _find_label_lane(
            label,
            base_x,
            base_y,
            width=width,
            height=height,
            node_rects=node_rects,
            occupied=occupied_labels,
        )
        if chosen is None:
            issues.append(f"edge-label-no-safe-lane:{index}:{edge['from']}->{edge['to']}")
            continue
        x_offset, y_offset, rect = chosen
        label_offsets[index] = y_offset
        label_x_offsets[index] = x_offset
        occupied_labels.append((index, rect))
        label_boxes.append({
            "edge_index": index,
            "from": edge["from"],
            "to": edge["to"],
            "label": label,
            "offset": y_offset,
            "x_offset": x_offset,
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
            "text_fit_policy": sketch_notebook_polish.TEXT_FIT_POLICY,
            "geometry_policy": GEOMETRY_POLICY,
        },
        "effective_layout": dict(effective["layout"]),
        "auto_direction": effective.get("_geometry_auto_direction"),
        "width": int(round(width)),
        "height": int(round(height)),
        **legibility,
        "label_offsets": {str(key): value for key, value in sorted(label_offsets.items())},
        "label_x_offsets": {str(key): value for key, value in sorted(label_x_offsets.items())},
        "label_boxes": label_boxes,
        "connector_paths": connector_paths,
    }


def analyze_spec(
    spec_value: Any,
    *,
    layout_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]] | None = None,
    edge_fn: Callable[[Any, Any, str, int], tuple[list[tuple[float, float]], float, float]] | None = None,
) -> dict[str, Any]:
    spec = sketch_figure.validate_spec(spec_value)
    effective = constrained_spec(spec)
    return _analyze_effective(
        spec,
        effective,
        layout_fn=layout_fn or sketch_figure._layout,
        edge_fn=edge_fn or sketch_figure._edge_geometry,
    )


def _policy_rough_polyline(
    points: list[tuple[float, float]],
    seed: str,
    key: str,
    *,
    closed: bool = False,
    scale: float = 1.0,
) -> str:
    if not points:
        return ""
    return pencil_rough_polyline(
        points,
        seed,
        key,
        jitter_scale=1.65 * scale,
        bend_scale=2.85 * scale,
        closed=closed,
    )


def _apply_geometry_metadata(svg_bytes: bytes, size_class: str) -> bytes:
    text = svg_bytes.decode("utf-8")
    marker = 'data-pencil-style="graphite-overlay-v1"'
    additions = (
        marker
        + f' data-layout-size="{html.escape(size_class, quote=True)}"'
        + f' data-typography="{TYPOGRAPHY_POLICY}"'
        + f' data-pencil-policy="{PENCIL_POLICY}"'
        + f' data-geometry-policy="{GEOMETRY_POLICY}"'
    )
    text = text.replace(marker, additions, 1)
    return text.encode("utf-8")


def install_for_spec(spec_value: Any):
    """Install the exact preflighted geometry and notebook render for one figure."""
    sketch_notebook_polish.install()

    original_layout = sketch_figure._layout
    original_edge = sketch_figure._edge_geometry
    original_rough_polyline = sketch_figure._rough_polyline
    original_render_svg = sketch_figure.render_svg

    spec = sketch_figure.validate_spec(spec_value)
    effective = constrained_spec(spec)
    report = _analyze_effective(
        spec,
        effective,
        layout_fn=original_layout,
        edge_fn=original_edge,
    )
    if not report["ok"]:
        raise GeometryError("; ".join(report["issues"]))

    y_offsets = {int(key): float(value) for key, value in report["label_offsets"].items()}
    x_offsets = {int(key): float(value) for key, value in report["label_x_offsets"].items()}

    def safe_layout(spec_to_render: dict[str, Any]):
        render_effective = constrained_spec(spec_to_render)
        return _layout_effective(render_effective, original_layout)

    def safe_edge(start: Any, end: Any, direction: str, index: int):
        points, label_x, label_y = original_edge(start, end, direction, index)
        return (
            points,
            label_x + x_offsets.get(index, 0.0),
            label_y + y_offsets.get(index, 0.0),
        )

    def safe_render(spec_to_render: Any):
        svg_bytes, render_report = original_render_svg(spec_to_render)
        svg_bytes = _apply_geometry_metadata(svg_bytes, str(report["size_class"]))
        style_audit = sketch_figure.audit_svg_style(svg_bytes)
        if not style_audit["ok"]:
            raise sketch_figure.SketchSpecError(
                "generated SVG failed style audit: " + ", ".join(style_audit["issues"])
            )
        updated = dict(render_report)
        updated.update({
            "svg_sha256": sketch_figure.digest_bytes(svg_bytes),
            "style_audit": style_audit,
            "size_class": report["size_class"],
            "typography_policy": TYPOGRAPHY_POLICY,
            "pencil_policy": PENCIL_POLICY,
            "geometry_policy": GEOMETRY_POLICY,
            "node_text_policy": sketch_notebook_polish.TEXT_FIT_POLICY,
            "shape_policy": sketch_notebook_polish.SHAPE_POLICY,
            "title_meta_policy": sketch_notebook_polish.TITLE_META_POLICY,
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
        figures.append({
            "concept_id": row["concept_id"],
            "derived_figure_id": row["derived_figure_id"],
            **report,
        })
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
