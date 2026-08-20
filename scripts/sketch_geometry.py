#!/usr/bin/env python3
"""Deterministic geometry constraints for Hybrid V1 sketch diagrams.

The semantic sketch spec stays compact and coordinate-free. This module applies
renderer-owned minimum spacing and plans collision-free edge-label lanes before
an SVG is accepted. It never changes academic content.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
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

MIN_NODE_GAP = 56
MIN_RANK_GAP = 118
EDGE_LABEL_FONT_SIZE = 15.0
EDGE_LABEL_CHAR_WIDTH = 7.4
EDGE_LABEL_HEIGHT = 23.0
EDGE_LABEL_MAX_WIDTH = 240.0
EDGE_LABEL_GAP = 12.0
EDGE_LABEL_NODE_GAP = 14.0
CANVAS_MARGIN = 14.0
LABEL_LANES = (0.0, -28.0, 28.0, -56.0, 56.0, -84.0, 84.0, -112.0, 112.0)


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


def constrained_spec(spec_value: Any) -> dict[str, Any]:
    """Return a normalized copy with renderer-owned safe spacing minimums."""
    spec = sketch_figure.validate_spec(spec_value)
    effective = copy.deepcopy(spec)
    layout = effective["layout"]
    layout["node_gap"] = max(int(layout["node_gap"]), MIN_NODE_GAP)
    layout["rank_gap"] = max(int(layout["rank_gap"]), MIN_RANK_GAP)
    return effective


def constrained_layout(
    spec_value: Any,
    original_layout: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]] | None = None,
):
    layout_fn = original_layout or sketch_figure._layout
    return layout_fn(constrained_spec(spec_value))


def _node_rect(box: Any) -> Rect:
    return Rect(float(box.x), float(box.y), float(box.x + box.width), float(box.y + box.height))


def _label_rect(label: str, x: float, geometry_y: float) -> Rect:
    # render_svg writes the baseline at geometry_y - 7. A conservative box around
    # that baseline catches collisions despite font fallback differences.
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


def analyze_spec(
    spec_value: Any,
    *,
    layout_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], float, float, float]] | None = None,
    edge_fn: Callable[[Any, Any, str, int], tuple[list[tuple[float, float]], float, float]] | None = None,
) -> dict[str, Any]:
    """Plan deterministic label lanes and return a machine-checkable geometry report."""
    spec = sketch_figure.validate_spec(spec_value)
    effective = constrained_spec(spec)
    raw_layout = layout_fn or sketch_figure._layout
    raw_edge = edge_fn or sketch_figure._edge_geometry
    boxes, width, height, _title_height = raw_layout(effective)

    issues = _node_overlap_issues(boxes)
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
            boxes[edge["from"]], boxes[edge["to"]], spec["layout"]["direction"], index
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
        label_boxes.append(
            {
                "edge_index": index,
                "from": edge["from"],
                "to": edge["to"],
                "label": label,
                "offset": offset,
                "box": [round(rect.left, 2), round(rect.top, 2), round(rect.right, 2), round(rect.bottom, 2)],
            }
        )

    return {
        "ok": not issues,
        "issues": sorted(set(issues)),
        "constraints": {
            "min_node_gap": MIN_NODE_GAP,
            "min_rank_gap": MIN_RANK_GAP,
            "edge_label_gap": EDGE_LABEL_GAP,
            "edge_label_node_gap": EDGE_LABEL_NODE_GAP,
            "edge_label_max_width": EDGE_LABEL_MAX_WIDTH,
        },
        "effective_layout": dict(effective["layout"]),
        "width": int(round(width)),
        "height": int(round(height)),
        "label_offsets": {str(key): value for key, value in sorted(label_offsets.items())},
        "label_boxes": label_boxes,
    }


def install_for_spec(spec_value: Any):
    """Temporarily install the exact geometry analyzed for one render.

    Returns ``(report, restore)``. The caller must invoke ``restore`` in finally.
    """
    original_layout = sketch_figure._layout
    original_edge = sketch_figure._edge_geometry
    report = analyze_spec(spec_value, layout_fn=original_layout, edge_fn=original_edge)
    if not report["ok"]:
        raise GeometryError("; ".join(report["issues"]))
    offsets = {int(key): float(value) for key, value in report["label_offsets"].items()}

    def safe_layout(spec: dict[str, Any]):
        return original_layout(constrained_spec(spec))

    def safe_edge(start: Any, end: Any, direction: str, index: int):
        points, label_x, label_y = original_edge(start, end, direction, index)
        return points, label_x, label_y + offsets.get(index, 0.0)

    sketch_figure._layout = safe_layout  # type: ignore[assignment]
    sketch_figure._edge_geometry = safe_edge  # type: ignore[assignment]

    def restore() -> None:
        sketch_figure._layout = original_layout  # type: ignore[assignment]
        sketch_figure._edge_geometry = original_edge  # type: ignore[assignment]

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
        unit_root(course, unit_id)  # validate canonical unit boundary
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
