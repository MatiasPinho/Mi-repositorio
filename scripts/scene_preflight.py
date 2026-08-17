#!/usr/bin/env python3
"""Objective geometry gate for Visual System V2 scenes."""
from __future__ import annotations

import math
from typing import Any

try:
    from . import scene_pencil, scene_render, scene_spec
except ImportError:
    import scene_pencil  # type: ignore
    import scene_render  # type: ignore
    import scene_spec  # type: ignore

MIN_DISPLAY_GAP = 7.0
MAX_DENSITY = 0.74


def _display(value: float, profile: scene_pencil.PencilProfile) -> float:
    return value / profile.logical_per_css_px


def _inside(box: scene_render.Box, canvas: dict[str, float], tol: float = .5) -> bool:
    return box.x >= -tol and box.y >= -tol and box.right <= canvas["width"] + tol and box.bottom <= canvas["height"] + tol


def _intersection(a: scene_render.Box, b: scene_render.Box) -> scene_render.Box | None:
    x0, y0 = max(a.x, b.x), max(a.y, b.y)
    x1, y1 = min(a.right, b.right), min(a.bottom, b.bottom)
    if x1 <= x0 or y1 <= y0:
        return None
    return scene_render.Box(x0, y0, x1 - x0, y1 - y0)


def _distance(a: scene_render.Box, b: scene_render.Box) -> float:
    dx = max(a.x - b.right, b.x - a.right, 0)
    dy = max(a.y - b.bottom, b.y - a.bottom, 0)
    return math.hypot(dx, dy)


def _segment_intersects_box(p1: tuple[float, float], p2: tuple[float, float], box: scene_render.Box, pad: float = 0) -> bool:
    left, right = box.x - pad, box.right + pad
    top, bottom = box.y - pad, box.bottom + pad
    if max(p1[0], p2[0]) < left or min(p1[0], p2[0]) > right or max(p1[1], p2[1]) < top or min(p1[1], p2[1]) > bottom:
        return False
    for x, y in (p1, p2):
        if left <= x <= right and top <= y <= bottom:
            return True

    def ccw(a, b, c):
        return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])

    def hit(a, b, c, d):
        return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)

    corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
    return any(hit(p1, p2, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _allowed(layout: dict[str, Any]) -> set[tuple[str, str]]:
    return {tuple(sorted(pair)) for pair in layout.get("allowed_overlaps", [])}


def _member_pair(scene: dict[str, Any], left: str, right: str) -> bool:
    by_id = {e["id"]: e for e in scene["elements"]}
    for parent, child in ((left, right), (right, left)):
        item = by_id[parent]
        if item["type"] in {"group", "region"} and child in item.get("members", []):
            return True
    return False


def _text_overflow(element: dict[str, Any], placement: dict[str, Any], profile: scene_pencil.PencilProfile) -> bool:
    kind = element["type"]
    if kind in {"text", "annotation"}:
        text = element["text"]
        role = element.get("text_role", "annotation" if kind == "annotation" else "label")
        width, height = placement["width"], placement["height"]
        lines, size, line_height = scene_render.text_layout(text, width, role, profile)
        needed = line_height * len(lines)
        return needed > height * .95 or any(len(line) > max(5, int(width / max(size*.48, 1))) * 1.25 for line in lines)
    if kind == "shape" and (element.get("label") or element.get("detail")):
        if element.get("shape") == "polygon":
            box = scene_render._placement_box(element, placement)
        else:
            box = scene_render.Box(placement["x"], placement["y"], placement["width"], placement["height"])
        label, detail = element.get("label", ""), element.get("detail", "")
        if label:
            lines, _, lh = scene_render.text_layout(label, box.width*.82, "label", profile)
            if lh * len(lines) > box.height * (.40 if detail else .78):
                return True
        if detail:
            lines, _, lh = scene_render.text_layout(detail, box.width*.82, "detail", profile)
            if lh * len(lines) > box.height * (.36 if label else .78):
                return True
    return False


def preflight_variant(scene_value: Any, variant: str) -> dict[str, Any]:
    scene = scene_spec.validate_scene(scene_value)
    layout = scene["layouts"][variant]
    canvas = layout["canvas"]
    profile = scene_pencil.profile(canvas["width"], scene_render.TARGET_DISPLAY_WIDTH[variant])
    bounds = scene_render.element_bounds(scene, variant)
    by_id = {e["id"]: e for e in scene["elements"]}
    issues: list[dict[str, Any]] = []

    def add(code: str, severity: str, elements: list[str], message: str) -> None:
        issues.append({"code": code, "severity": severity, "elements": elements, "message": message})

    ratio = canvas["width"] / canvas["height"]
    if variant == "wide" and ratio > 3.4:
        add("extreme-aspect-ratio", "warning", [], f"wide canvas ratio {ratio:.2f} is likely to collapse when embedded")
    if variant == "narrow" and ratio > 1.45:
        add("narrow-too-wide", "warning", [], f"narrow canvas ratio {ratio:.2f} wastes mobile width")

    for eid, box in bounds.items():
        if not _inside(box, canvas):
            add("out-of-bounds", "error", [eid], "element geometry exceeds canvas")
        element = by_id[eid]
        placement = layout["placements"][eid]
        if element["type"] == "shape" and element.get("semantic", True) and not (element.get("label") or element.get("detail")):
            add(
                "empty-semantic-shape",
                "error",
                [eid],
                "semantic shape renders as an unexplained empty box/form; add visible content or mark it decorative",
            )
        if _text_overflow(element, placement, profile):
            add("text-overflow", "error", [eid], "text does not fit its declared geometry")

    allowed = _allowed(layout)
    solid_types = {"shape", "text", "annotation", "group", "region"}
    solid_ids = [eid for eid in bounds if by_id[eid]["type"] in solid_types]
    for i, left in enumerate(solid_ids):
        for right in solid_ids[i + 1:]:
            pair = tuple(sorted((left, right)))
            if pair in allowed or _member_pair(scene, left, right):
                continue
            overlap = _intersection(bounds[left], bounds[right])
            if overlap and overlap.width * overlap.height > profile.logical_per_css_px ** 2 * 4:
                add("accidental-overlap", "error", [left, right], "elements overlap without an allowed_overlaps declaration")
            elif not overlap:
                gap = _display(_distance(bounds[left], bounds[right]), profile)
                if gap < MIN_DISPLAY_GAP:
                    add("insufficient-spacing", "warning", [left, right], f"visual gap is only {gap:.1f}px")

    protected = [eid for eid in bounds if by_id[eid]["type"] in {"shape", "text", "annotation"}]
    for eid, element in by_id.items():
        if element["type"] not in {"connector", "arrow", "line", "path", "axis", "brace", "divider"}:
            continue
        points = scene_render.command_points(layout["placements"][eid]["commands"])
        if len(points) < 2:
            continue
        exempt = {eid}
        if element["type"] == "connector":
            exempt |= {element["from"], element["to"]}
        for other in protected:
            if other in exempt or tuple(sorted((eid, other))) in allowed:
                continue
            if any(_segment_intersects_box(a, b, bounds[other], pad=profile.logical_per_css_px * 1.5) for a, b in zip(points, points[1:])):
                code = "connector-through-element" if element["type"] == "connector" else "path-through-element"
                add(code, "error", [eid, other], "route crosses unrelated text/shape")

        if element.get("label"):
            route_box = bounds[eid]
            p = layout["placements"][eid]
            lx, ly = p.get("label_x", route_box.cx), p.get("label_y", route_box.cy)
            label_box = scene_render.Box(lx - 55*profile.logical_per_css_px, ly - 14*profile.logical_per_css_px, 110*profile.logical_per_css_px, 28*profile.logical_per_css_px)
            # A connector's own label is not exempt from its route. This exact
            # defect escaped the first real V2 run and required an expensive
            # vision retry, so catch it deterministically before rendering.
            if any(_segment_intersects_box(a, b, label_box) for a, b in zip(points, points[1:])):
                add("connector-through-own-label", "error", [eid], "connector route crosses its own label")
            for other in protected:
                if other in exempt or tuple(sorted((eid, other))) in allowed:
                    continue
                if _intersection(label_box, bounds[other]):
                    add("connector-label-collision", "error", [eid, other], "connector label collides with another element")

    occupied = sum(box.width * box.height for eid, box in bounds.items() if by_id[eid]["type"] in solid_types)
    density = occupied / max(canvas["width"] * canvas["height"], 1)
    if density > MAX_DENSITY or len(scene["elements"]) > 34:
        add("excessive-density", "warning", [], f"scene density {density:.2f} with {len(scene['elements'])} elements may need splitting")

    metrics = profile.display_metrics()
    if metrics["main_width_px"] < 1.7 or metrics["jitter_px"] < 1.25 or metrics["ghost_width_px"] < .7:
        add("pencil-underpowered", "error", [], "pencil profile falls below perceptual hand-drawn minimum at target display size")
    if metrics["label_font_px"] < 17 or metrics["detail_font_px"] < 13.5:
        add("text-too-small", "error", [], "renderer font profile is below final-display readability minimum")

    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "variant": variant,
        "canvas": canvas,
        "density": round(density, 4),
        "display_metrics": metrics,
        "issues": issues,
    }


def preflight_scene(scene_value: Any) -> dict[str, Any]:
    scene = scene_spec.validate_scene(scene_value)
    variants = {variant: preflight_variant(scene, variant) for variant in scene_spec.VARIANTS}
    return {
        "version": 1,
        "ok": all(row["ok"] for row in variants.values()),
        "scene_id": scene["id"],
        "scene_sha256": scene_spec.scene_sha256(scene),
        "variants": variants,
        "issues": [
            {"variant": variant, **issue}
            for variant, report in variants.items()
            for issue in report["issues"]
        ],
    }
