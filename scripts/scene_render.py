#!/usr/bin/env python3
"""Deterministic renderer for Visual System V2 scene graphs."""
from __future__ import annotations

import hashlib
import html
import json
import math
from dataclasses import dataclass
from typing import Any

try:
    from . import scene_pencil, scene_spec
except ImportError:
    import scene_pencil  # type: ignore
    import scene_spec  # type: ignore

GENERATOR_ID = "carpeta-scene-svg"
GENERATOR_VERSION = 1
PENCIL_STYLE = "graphite-overlay-v2"
TARGET_DISPLAY_WIDTH = {"wide": 720.0, "narrow": 340.0}
FONT_STACK = '"Segoe Print","Bradley Hand","Comic Sans MS",cursive'


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _wrap(text: str, width_chars: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def font_size(profile: scene_pencil.PencilProfile, role: str) -> float:
    return {
        "title": profile.title_font,
        "label": profile.label_font,
        "detail": profile.detail_font,
        "caption": profile.detail_font,
        "annotation": profile.annotation_font,
    }.get(role, profile.label_font)


def text_layout(text: str, width: float, role: str, profile: scene_pencil.PencilProfile) -> tuple[list[str], float, float]:
    size = font_size(profile, role)
    avg = size * 0.56
    capacity = max(4, int(max(width, avg * 4) / max(avg, 1)))
    lines = _wrap(text, capacity)
    line_height = size * 1.28
    return lines, size, line_height


def _placement_box(element: dict[str, Any], placement: dict[str, Any]) -> Box:
    kind = element["type"]
    shape = element.get("shape", "")
    if kind in {"shape", "region"} and shape == "polygon":
        xs = [point[0] for point in placement["points"]]
        ys = [point[1] for point in placement["points"]]
        return Box(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    if kind in {"shape", "text", "annotation", "group", "region"}:
        return Box(placement["x"], placement["y"], placement["width"], placement["height"])
    points = command_points(placement["commands"])
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return Box(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def element_bounds(scene: dict[str, Any], variant: str) -> dict[str, Box]:
    normalized = scene_spec.validate_scene(scene)
    placements = normalized["layouts"][variant]["placements"]
    return {
        element["id"]: _placement_box(element, placements[element["id"]])
        for element in normalized["elements"]
    }


def command_points(commands: list[dict[str, Any]], curve_samples: int = 12) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    current: tuple[float, float] | None = None
    start: tuple[float, float] | None = None
    for cmd in commands:
        op = cmd["op"]
        if op == "move":
            current = (cmd["x"], cmd["y"])
            start = current
            points.append(current)
        elif op == "line" and current is not None:
            end = (cmd["x"], cmd["y"])
            points.append(end)
            current = end
        elif op == "quadratic" and current is not None:
            p0 = current
            p1 = (cmd["cx"], cmd["cy"])
            p2 = (cmd["x"], cmd["y"])
            for i in range(1, curve_samples + 1):
                t = i / curve_samples
                u = 1 - t
                points.append((u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0], u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]))
            current = p2
        elif op == "cubic" and current is not None:
            p0 = current
            p1 = (cmd["cx1"], cmd["cy1"])
            p2 = (cmd["cx2"], cmd["cy2"])
            p3 = (cmd["x"], cmd["y"])
            for i in range(1, curve_samples + 1):
                t = i / curve_samples
                u = 1 - t
                points.append((
                    u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                    u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1],
                ))
            current = p3
        elif op == "close" and current is not None and start is not None:
            points.append(start)
            current = start
    return points


def _trace_pair(path_main: str, path_ghost: str, stroke: str, profile: scene_pencil.PencilProfile, *, dashed: bool = False, marker_start: str = "", marker_end: str = "") -> list[str]:
    dash = f' stroke-dasharray="{8*profile.logical_per_css_px:.2f} {6*profile.logical_per_css_px:.2f}"' if dashed else ""
    start = f' marker-start="url(#{marker_start})"' if marker_start else ""
    end = f' marker-end="url(#{marker_end})"' if marker_end else ""
    return [
        f'<path data-pencil-trace="main" d="{path_main}" fill="none" stroke="{stroke}" stroke-width="{profile.main_width:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash}{start}{end}/>',
        f'<path data-pencil-trace="ghost" d="{path_ghost}" fill="none" stroke="{stroke}" stroke-width="{profile.ghost_width:.2f}" stroke-linecap="round" stroke-linejoin="round" opacity="{profile.ghost_opacity:.2f}"{dash}/>',
    ]


def _rough_pair_points(points: list[tuple[float, float]], seed: str, key: str, profile: scene_pencil.PencilProfile, *, closed: bool = False) -> tuple[str, str]:
    main = scene_pencil.rough_polyline(points, seed, key + ":main", jitter_scale=profile.jitter, bend_scale=profile.bend, closed=closed)
    ghost = scene_pencil.rough_polyline(points, seed, key + ":ghost", jitter_scale=profile.jitter * 1.55, bend_scale=profile.bend * 1.35, closed=closed)
    return main, ghost


def _rough_pair_commands(commands: list[dict[str, Any]], seed: str, key: str, profile: scene_pencil.PencilProfile) -> tuple[str, str]:
    main = scene_pencil.rough_commands(commands, seed, key + ":main", jitter_scale=profile.jitter, bend_scale=profile.bend)
    ghost = scene_pencil.rough_commands(commands, seed, key + ":ghost", jitter_scale=profile.jitter * 1.55, bend_scale=profile.bend * 1.35)
    return main, ghost


def _shape_points(element: dict[str, Any], placement: dict[str, Any]) -> list[tuple[float, float]]:
    shape = element["shape"]
    if shape == "polygon":
        return [(float(x), float(y)) for x, y in placement["points"]]
    box = Box(placement["x"], placement["y"], placement["width"], placement["height"])
    if shape in {"circle", "ellipse"}:
        return scene_pencil.ellipse_points(box.cx, box.cy, box.width / 2, box.height / 2)
    if shape == "decision":
        return [(box.cx, box.y), (box.right, box.cy), (box.cx, box.bottom), (box.x, box.cy)]
    if shape == "data":
        skew = min(box.width * .12, 34)
        return [(box.x + skew, box.y), (box.right, box.y), (box.right - skew, box.bottom), (box.x, box.bottom)]
    if shape == "note":
        fold = min(box.width * .12, 28)
        return [(box.x, box.y), (box.right - fold, box.y), (box.right, box.y + fold), (box.right, box.bottom), (box.x, box.bottom)]
    radius = min(box.height / 2, 26) if shape == "datastore" else (min(box.height / 2, 24) if shape == "rounded" else 2)
    return scene_pencil.rounded_rect_points(box.x, box.y, box.width, box.height, radius)


def _text_svg(text: str, box: Box, role: str, profile: scene_pencil.PencilProfile, *, anchor: str = "middle", css_class: str = "scene-label") -> list[str]:
    lines, size, line_height = text_layout(text, box.width, role, profile)
    if not lines:
        return []
    x = box.cx if anchor == "middle" else (box.x if anchor == "start" else box.right)
    total = line_height * (len(lines) - 1)
    y = box.cy - total / 2 + size * 0.35
    spans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_height
        spans.append(f'<tspan x="{x:.2f}" dy="{dy:.2f}">{html.escape(line)}</tspan>')
    return [f'<text class="{css_class}" x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}">{"".join(spans)}</text>']


def _shape_text(element: dict[str, Any], placement: dict[str, Any], profile: scene_pencil.PencilProfile) -> list[str]:
    if element.get("shape") == "polygon":
        bounds = _placement_box(element, placement)
    else:
        bounds = Box(placement["x"], placement["y"], placement["width"], placement["height"])
    label = element.get("label", "")
    detail = element.get("detail", "")
    if not label and not detail:
        return []
    if label and detail:
        label_box = Box(bounds.x + bounds.width*.08, bounds.y + bounds.height*.14, bounds.width*.84, bounds.height*.38)
        detail_box = Box(bounds.x + bounds.width*.08, bounds.y + bounds.height*.52, bounds.width*.84, bounds.height*.34)
        return _text_svg(label, label_box, "label", profile, css_class="scene-label") + _text_svg(detail, detail_box, "detail", profile, css_class="scene-detail")
    return _text_svg(label or detail, Box(bounds.x + bounds.width*.08, bounds.y + bounds.height*.10, bounds.width*.84, bounds.height*.80), "label" if label else "detail", profile, css_class="scene-label" if label else "scene-detail")


def _element_svg(element: dict[str, Any], placement: dict[str, Any], seed: str, profile: scene_pencil.PencilProfile) -> list[str]:
    kind = element["type"]
    eid = element["id"]
    stroke = scene_pencil.tone_color(element["tone"])
    dashed = element.get("style") == "dashed"
    lines = [f'<g id="el-{html.escape(eid)}" data-scene-element="{html.escape(eid)}" data-element-type="{kind}">']
    if kind == "shape":
        main, ghost = _rough_pair_points(_shape_points(element, placement), seed, eid, profile, closed=True)
        lines.extend(_trace_pair(main, ghost, stroke, profile, dashed=dashed))
        lines.extend(_shape_text(element, placement, profile))
    elif kind in {"group", "region"}:
        shape_element = {"shape": element.get("shape", "rounded")}
        main, ghost = _rough_pair_points(_shape_points(shape_element, placement), seed, eid, profile, closed=True)
        lines.extend(_trace_pair(main, ghost, stroke, profile, dashed=element.get("style") == "dashed"))
        if element.get("label"):
            box = _placement_box({"type": kind, "shape": element.get("shape", "")}, placement)
            label_box = Box(box.x + 8*profile.logical_per_css_px, box.y + 5*profile.logical_per_css_px, max(20, box.width - 16*profile.logical_per_css_px), 28*profile.logical_per_css_px)
            lines.extend(_text_svg(element["label"], label_box, "detail", profile, anchor="start", css_class="scene-detail"))
    elif kind in {"line", "path", "arrow", "connector", "brace", "axis", "divider"}:
        main, ghost = _rough_pair_commands(placement["commands"], seed, eid, profile)
        marker_start = marker_end = ""
        if kind in {"arrow", "connector"}:
            heads = element.get("arrowheads", "end")
            if heads in {"start", "both"}:
                marker_start = f"arrow-{element['tone']}"
            if heads in {"end", "both"}:
                marker_end = f"arrow-{element['tone']}"
        lines.extend(_trace_pair(main, ghost, stroke, profile, dashed=dashed, marker_start=marker_start, marker_end=marker_end))
        label = element.get("label", "")
        if label:
            box = _placement_box(element, placement)
            lx = placement.get("label_x", box.cx)
            ly = placement.get("label_y", box.cy)
            label_box = Box(lx - 60*profile.logical_per_css_px, ly - 16*profile.logical_per_css_px, 120*profile.logical_per_css_px, 32*profile.logical_per_css_px)
            lines.extend(_text_svg(label, label_box, "detail", profile, css_class="scene-edge-label"))
    elif kind in {"text", "annotation"}:
        box = Box(placement["x"], placement["y"], placement["width"], placement["height"])
        role = element.get("text_role", "annotation" if kind == "annotation" else "label")
        anchor = placement.get("text_anchor", "start" if kind == "annotation" else "middle")
        css = "scene-annotation" if kind == "annotation" else ("scene-title" if role == "title" else "scene-label")
        lines.extend(_text_svg(element["text"], box, role, profile, anchor=anchor, css_class=css))
    lines.append("</g>")
    return lines


def render_variant(scene_value: Any, variant: str, *, narrow_asset: str = "") -> tuple[bytes, dict[str, Any]]:
    scene = scene_spec.validate_scene(scene_value)
    if variant not in scene_spec.VARIANTS:
        raise scene_spec.SceneSpecError(f"variant must be one of {scene_spec.VARIANTS}")
    layout = scene["layouts"][variant]
    width = layout["canvas"]["width"]
    height = layout["canvas"]["height"]
    profile = scene_pencil.profile(width, TARGET_DISPLAY_WIDTH[variant])
    normalized_bytes = scene_spec.scene_bytes(scene)
    scene_sha = digest_bytes(normalized_bytes)
    seed = hashlib.sha256((scene_spec.canonical_json(scene) + "|" + variant).encode("utf-8")).hexdigest()

    attrs = [
        'xmlns="http://www.w3.org/2000/svg"',
        f'width="{width:.0f}"', f'height="{height:.0f}"',
        f'viewBox="0 0 {width:.0f} {height:.0f}"',
        'role="img"', 'aria-labelledby="scene-title scene-desc"',
        'data-study-sketch="1"', 'data-transparent-canvas="1"',
        'data-study-scene="1"', 'data-scene-version="2"',
        f'data-generator="{GENERATOR_ID}"', f'data-generator-version="{GENERATOR_VERSION}"',
        f'data-scene-id="{html.escape(scene["id"], quote=True)}"',
        f'data-scene-sha256="{scene_sha}"', f'data-scene-variant="{variant}"',
        f'data-pencil-style="{PENCIL_STYLE}"',
    ]
    if variant == "wide" and narrow_asset:
        attrs.append(f'data-narrow-variant="{html.escape(narrow_asset, quote=True)}"')
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg ' + ' '.join(attrs) + '>',
        f'<title id="scene-title">{html.escape(scene["alt"])}</title>',
        f'<desc id="scene-desc">{html.escape(scene["caption"])}</desc>',
        '<metadata id="scene-metadata">' + html.escape(json.dumps({
            "generator": GENERATOR_ID,
            "generator_version": GENERATOR_VERSION,
            "scene_sha256": scene_sha,
            "variant": variant,
            "representation_role": scene["representation_role"],
        }, ensure_ascii=False, sort_keys=True)) + '</metadata>',
        '<defs>',
    ]
    for tone in sorted(scene_spec.TONES):
        color = scene_pencil.tone_color(tone)
        sw = max(profile.main_width * .82, .5)
        lines.append(
            f'<marker id="arrow-{tone}" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto-start-reverse" markerUnits="strokeWidth">'
            f'<path d="M 1.2 1.4 Q 5.7 4.2 10 6 Q 5.4 7.8 1.4 10.8" fill="none" stroke="{color}" stroke-width="{sw:.2f}" stroke-linecap="round" stroke-linejoin="round"/>'
            '</marker>'
        )
    lines.extend([
        '<style>',
        f'.scene-label{{font:600 {profile.label_font:.2f}px {FONT_STACK};fill:{scene_pencil.THEME["ink"]}}}',
        f'.scene-detail{{font:400 {profile.detail_font:.2f}px {FONT_STACK};fill:{scene_pencil.THEME["graphite_soft"]}}}',
        f'.scene-title{{font:600 {profile.title_font:.2f}px {FONT_STACK};fill:{scene_pencil.THEME["ink"]}}}',
        f'.scene-annotation{{font:500 {profile.annotation_font:.2f}px {FONT_STACK};fill:{scene_pencil.THEME["graphite"]}}}',
        f'.scene-edge-label{{font:600 {profile.detail_font:.2f}px {FONT_STACK};fill:{scene_pencil.THEME["graphite"]}}}',
        '</style>', '</defs>',
    ])

    by_id = {element["id"]: element for element in scene["elements"]}
    z = {"region": 0, "group": 1, "axis": 2, "divider": 2, "line": 3, "path": 3, "brace": 3, "connector": 4, "arrow": 4, "shape": 5, "text": 6, "annotation": 7}
    for eid in sorted(by_id, key=lambda item: (z.get(by_id[item]["type"], 5), scene["elements"].index(by_id[item]))):
        lines.extend(_element_svg(by_id[eid], layout["placements"][eid], seed, profile))
    lines.append('</svg>')
    data = ("\n".join(lines) + "\n").encode("utf-8")
    report = {
        "ok": True,
        "schema_version": 2,
        "id": scene["id"],
        "variant": variant,
        "scene_sha256": scene_sha,
        "svg_sha256": digest_bytes(data),
        "width": width,
        "height": height,
        "target_display_width": TARGET_DISPLAY_WIDTH[variant],
        "pencil_metrics": profile.display_metrics(),
        "generator": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
    }
    return data, report
