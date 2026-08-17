#!/usr/bin/env python3
"""Deterministic scale-aware notebook pencil primitives for scene V2."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable

THEME = {
    "graphite": "#42494f",
    "graphite_soft": "#697078",
    "graphite_faint": "#858b90",
    "ink": "#29323b",
    "primary": "#315573",
    "example": "#526358",
    "warning": "#75634a",
    "connection": "#615d68",
    "danger": "#805f5a",
}
TONE_COLOR = {
    "neutral": THEME["graphite"],
    "primary": THEME["primary"],
    "example": THEME["example"],
    "warning": THEME["warning"],
    "connection": THEME["connection"],
    "danger": THEME["danger"],
}


@dataclass(frozen=True)
class PencilProfile:
    logical_per_css_px: float
    main_width: float
    ghost_width: float
    jitter: float
    bend: float
    ghost_opacity: float
    label_font: float
    detail_font: float
    title_font: float
    annotation_font: float

    def display_metrics(self) -> dict[str, float]:
        scale = self.logical_per_css_px
        return {
            "main_width_px": self.main_width / scale,
            "ghost_width_px": self.ghost_width / scale,
            "jitter_px": self.jitter / scale,
            "bend_px": self.bend / scale,
            "label_font_px": self.label_font / scale,
            "detail_font_px": self.detail_font / scale,
        }


def profile(canvas_width: float, target_display_width: float) -> PencilProfile:
    if canvas_width <= 0 or target_display_width <= 0:
        raise ValueError("canvas/display width must be positive")
    logical = canvas_width / target_display_width
    return PencilProfile(
        logical_per_css_px=logical,
        main_width=1.75 * logical,
        ghost_width=0.72 * logical,
        jitter=1.05 * logical,
        bend=1.75 * logical,
        ghost_opacity=0.34,
        label_font=20.0 * logical,
        detail_font=15.5 * logical,
        title_font=24.0 * logical,
        annotation_font=17.0 * logical,
    )


def tone_color(tone: str) -> str:
    return TONE_COLOR.get(tone, THEME["graphite"])


def jitter(seed: str, *parts, scale: float = 1.0) -> float:
    payload = "|".join([seed, *(str(part) for part in parts)]).encode("utf-8")
    number = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 0xFFFFFFFFFFFFFFFF
    return (number * 2 - 1) * scale


def rough_polyline(
    points: Iterable[tuple[float, float]],
    seed: str,
    key: str,
    *,
    jitter_scale: float,
    bend_scale: float,
    closed: bool = False,
) -> str:
    pts = list(points)
    if len(pts) < 2:
        raise ValueError("rough polyline needs at least two points")
    varied = [
        (
            x + jitter(seed, key, i, "x", scale=jitter_scale),
            y + jitter(seed, key, i, "y", scale=jitter_scale),
        )
        for i, (x, y) in enumerate(pts)
    ]
    commands = [f"M {varied[0][0]:.2f} {varied[0][1]:.2f}"]
    targets = varied[1:] + ([varied[0]] if closed else [])
    start = varied[0]
    for i, target in enumerate(targets):
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        length = max(1.0, math.hypot(dx, dy))
        bend = jitter(seed, key, i, "bend", scale=bend_scale)
        along = jitter(seed, key, i, "along", scale=jitter_scale * 0.45)
        cx = (start[0] + target[0]) / 2 + (-dy / length) * bend + (dx / length) * along
        cy = (start[1] + target[1]) / 2 + (dx / length) * bend + (dy / length) * along
        commands.append(f"Q {cx:.2f} {cy:.2f} {target[0]:.2f} {target[1]:.2f}")
        start = target
    if closed:
        commands.append("Z")
    return " ".join(commands)


def rounded_rect_points(x: float, y: float, width: float, height: float, radius: float) -> list[tuple[float, float]]:
    radius = min(max(radius, 0.0), width / 2, height / 2)
    return [
        (x + radius, y),
        (x + width - radius, y),
        (x + width, y + radius),
        (x + width, y + height - radius),
        (x + width - radius, y + height),
        (x + radius, y + height),
        (x, y + height - radius),
        (x, y + radius),
    ]


def ellipse_points(cx: float, cy: float, rx: float, ry: float, count: int = 24) -> list[tuple[float, float]]:
    return [
        (cx + rx * math.cos(i * math.tau / count), cy + ry * math.sin(i * math.tau / count))
        for i in range(count)
    ]


def rough_commands(
    commands: list[dict], seed: str, key: str, *, jitter_scale: float, bend_scale: float
) -> str:
    out: list[str] = []
    current: tuple[float, float] | None = None
    start: tuple[float, float] | None = None
    for index, command in enumerate(commands):
        op = command["op"]
        if op == "close":
            out.append("Z")
            if start is not None:
                current = start
            continue

        def j(name: str) -> float:
            return jitter(seed, key, index, name, scale=jitter_scale)

        if op == "move":
            x = command["x"] + j("x")
            y = command["y"] + j("y")
            out.append(f"M {x:.2f} {y:.2f}")
            current = start = (x, y)
        elif op == "line":
            if current is None:
                raise ValueError("line before move")
            x = command["x"] + j("x")
            y = command["y"] + j("y")
            dx, dy = x - current[0], y - current[1]
            length = max(1.0, math.hypot(dx, dy))
            bend = jitter(seed, key, index, "bend", scale=bend_scale)
            cx = (current[0] + x) / 2 + (-dy / length) * bend
            cy = (current[1] + y) / 2 + (dx / length) * bend
            out.append(f"Q {cx:.2f} {cy:.2f} {x:.2f} {y:.2f}")
            current = (x, y)
        elif op == "quadratic":
            cx = command["cx"] + j("cx")
            cy = command["cy"] + j("cy")
            x = command["x"] + j("x")
            y = command["y"] + j("y")
            out.append(f"Q {cx:.2f} {cy:.2f} {x:.2f} {y:.2f}")
            current = (x, y)
        elif op == "cubic":
            cx1 = command["cx1"] + j("cx1")
            cy1 = command["cy1"] + j("cy1")
            cx2 = command["cx2"] + j("cx2")
            cy2 = command["cy2"] + j("cy2")
            x = command["x"] + j("x")
            y = command["y"] + j("y")
            out.append(f"C {cx1:.2f} {cy1:.2f} {cx2:.2f} {cy2:.2f} {x:.2f} {y:.2f}")
            current = (x, y)
    return " ".join(out)
