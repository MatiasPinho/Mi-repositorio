#!/usr/bin/env python3
"""Deterministic notebook-sketch SVG generator for pedagogical figures.

The model/planner owns the academic structure expressed by a validated JSON
specification. This module owns layout, SVG geometry and safe registration. It
does not call an image model, use randomness, or infer academic relationships.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
if __package__:
    from .course_layout import has_unit_layout, unit_root  # noqa: E402
    from .figure_assets import derived_key, load_registry, register_derived, sha256  # noqa: E402
    from .unit_identity import resolve_unit  # noqa: E402
else:
    from course_layout import has_unit_layout, unit_root  # noqa: E402
    from figure_assets import derived_key, load_registry, register_derived, sha256  # noqa: E402
    from unit_identity import resolve_unit  # noqa: E402


SPEC_VERSION = 1
GENERATOR_ID = "university-study-sketch-svg"
GENERATOR_VERSION = 2
MAX_NODES = 36
MAX_EDGES = 72
MAX_NODES_PER_ROW = 3

FIGURE_KINDS = {"flow", "tree", "concept-map", "relations", "technical-schematic"}
TREATMENTS = {"reinterpret", "preserve+derived_sketch"}
SHAPES = {
    "box", "rounded", "terminal", "process", "decision", "data",
    "circle", "note", "component", "datastore",
}
TONES = {"neutral", "primary", "example", "warning", "connection", "danger"}
RELATIONS = {"flow", "relation", "dependency", "feedback"}
LINE_STYLES = {"solid", "dashed"}
DIRECTIONS = {"top-to-bottom", "left-to-right"}
BACKGROUNDS = {"transparent"}

TOP_LEVEL_KEYS = {
    "schema_version", "id", "title", "kind", "visual_treatment", "role",
    "description", "alt", "caption", "based_on", "concepts", "learner_focus",
    "source_figure_id", "layout", "nodes", "edges", "groups",
}
NODE_KEYS = {"id", "label", "detail", "shape", "tone", "rank", "order", "based_on"}
EDGE_KEYS = {"from", "to", "label", "relation", "style", "tone", "based_on"}
GROUP_KEYS = {"id", "label", "nodes", "tone", "based_on"}
LAYOUT_KEYS = {"direction", "background", "rank_gap", "node_gap"}

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


class SketchSpecError(ValueError):
    """A structured sketch spec is unsafe or incomplete."""


@dataclass(frozen=True)
class NodeBox:
    x: float
    y: float
    width: float
    height: float
    label_lines: tuple[str, ...]
    detail_lines: tuple[str, ...]

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


def canonical_json(value: Any, *, indent: int | None = None) -> str:
    separators = (",", ":") if indent is None else None
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        separators=separators,
    )


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _error(path: str, message: str) -> SketchSpecError:
    return SketchSpecError(f"{path}: {message}")


def _strict_object(value: Any, path: str, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(path, "must be an object")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error(path, f"unknown fields: {', '.join(unknown)}")
    return value


def _text(value: Any, path: str, *, maximum: int, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str):
        raise _error(path, "must be a string")
    if value != value.strip():
        raise _error(path, "must not have leading or trailing whitespace")
    if not value and not optional:
        raise _error(path, "must not be empty")
    if len(value) > maximum:
        raise _error(path, f"must be at most {maximum} characters")
    if any(ord(char) < 32 for char in value):
        raise _error(path, "must be a single printable line")
    return value


def _identifier(value: Any, path: str) -> str:
    text = _text(value, path, maximum=64)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", text):
        raise _error(path, "must use lowercase letters, digits, hyphens or underscores")
    return text


def _integer(value: Any, path: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(path, "must be an integer")
    if value < minimum or value > maximum:
        raise _error(path, f"must be between {minimum} and {maximum}")
    return value


def _enum(value: Any, path: str, allowed: set[str]) -> str:
    text = _text(value, path, maximum=64)
    if text not in allowed:
        raise _error(path, f"must be one of: {', '.join(sorted(allowed))}")
    return text


def _refs(value: Any, path: str, *, required: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise _error(path, "must be an array")
    if required and not value:
        raise _error(path, "must contain at least one canonical reference")
    result: list[str] = []
    for index, item in enumerate(value):
        ref = _text(item, f"{path}[{index}]", maximum=180)
        if not re.fullmatch(r"[a-z][a-z0-9_-]*:.+", ref):
            raise _error(f"{path}[{index}]", "must use a namespaced reference such as concept:id")
        if ref in result:
            raise _error(f"{path}[{index}]", "duplicate reference")
        result.append(ref)
    return result


def _string_list(value: Any, path: str, *, maximum_items: int, maximum_text: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _error(path, "must be an array")
    if len(value) > maximum_items:
        raise _error(path, f"must contain at most {maximum_items} items")
    result: list[str] = []
    for index, item in enumerate(value):
        text = _text(item, f"{path}[{index}]", maximum=maximum_text)
        if text in result:
            raise _error(f"{path}[{index}]", "duplicate value")
        result.append(text)
    return result


def _evidence_subset(refs: list[str], global_refs: list[str], path: str) -> None:
    missing = [ref for ref in refs if ref not in global_refs]
    if missing:
        raise _error(path, f"references not declared in top-level based_on: {', '.join(missing)}")


def validate_spec(raw: Any) -> dict[str, Any]:
    """Validate and normalize a versioned sketch spec without inferring content."""
    source = _strict_object(raw, "$", TOP_LEVEL_KEYS)
    version = _integer(source.get("schema_version"), "$.schema_version", minimum=1, maximum=1)
    figure_id = _identifier(source.get("id"), "$.id")
    title = _text(source.get("title"), "$.title", maximum=120)
    kind = _enum(source.get("kind"), "$.kind", FIGURE_KINDS)
    treatment = _enum(source.get("visual_treatment"), "$.visual_treatment", TREATMENTS)
    role = _enum(source.get("role", "supporting"), "$.role", {"essential", "supporting"})
    description = _text(source.get("description"), "$.description", maximum=320)
    alt = _text(source.get("alt"), "$.alt", maximum=320)
    caption = _text(source.get("caption"), "$.caption", maximum=320)
    based_on = _refs(source.get("based_on"), "$.based_on")
    concepts = _string_list(source.get("concepts"), "$.concepts", maximum_items=20, maximum_text=100)
    learner_focus = _string_list(
        source.get("learner_focus"), "$.learner_focus", maximum_items=8, maximum_text=180
    )

    source_figure_id = source.get("source_figure_id")
    if treatment == "preserve+derived_sketch":
        source_figure_id = _text(source_figure_id, "$.source_figure_id", maximum=100)
        expected_ref = f"figure:{source_figure_id}"
        if expected_ref not in based_on:
            raise _error("$.based_on", f"must include {expected_ref} for a preserved companion")
    elif source_figure_id is not None:
        raise _error("$.source_figure_id", "is only valid for preserve+derived_sketch")

    layout_raw = _strict_object(source.get("layout", {}), "$.layout", LAYOUT_KEYS)
    layout = {
        "direction": _enum(
            layout_raw.get("direction", "top-to-bottom"), "$.layout.direction", DIRECTIONS
        ),
        "background": _enum(
            layout_raw.get("background", "transparent"), "$.layout.background", BACKGROUNDS
        ),
        "rank_gap": _integer(layout_raw.get("rank_gap", 108), "$.layout.rank_gap", minimum=72, maximum=220),
        "node_gap": _integer(layout_raw.get("node_gap", 56), "$.layout.node_gap", minimum=28, maximum=140),
    }

    nodes_raw = source.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise _error("$.nodes", "must contain at least one node")
    if len(nodes_raw) > MAX_NODES:
        raise _error("$.nodes", f"must contain at most {MAX_NODES} nodes")
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    rank_presence: list[bool] = []
    for index, item in enumerate(nodes_raw):
        path = f"$.nodes[{index}]"
        row = _strict_object(item, path, NODE_KEYS)
        node_id = _identifier(row.get("id"), f"{path}.id")
        if node_id in node_ids:
            raise _error(f"{path}.id", "duplicate node id")
        node_ids.add(node_id)
        node_refs = _refs(row.get("based_on"), f"{path}.based_on")
        _evidence_subset(node_refs, based_on, f"{path}.based_on")
        normalized = {
            "id": node_id,
            "label": _text(row.get("label"), f"{path}.label", maximum=90),
            "detail": _text(row.get("detail"), f"{path}.detail", maximum=180, optional=True),
            "shape": _enum(row.get("shape", "rounded"), f"{path}.shape", SHAPES),
            "tone": _enum(row.get("tone", "neutral"), f"{path}.tone", TONES),
            "order": _integer(row.get("order", index), f"{path}.order", minimum=0, maximum=200),
            "based_on": node_refs,
        }
        has_rank = "rank" in row
        rank_presence.append(has_rank)
        if has_rank:
            normalized["rank"] = _integer(row["rank"], f"{path}.rank", minimum=0, maximum=30)
        nodes.append(normalized)
    if any(rank_presence) and not all(rank_presence):
        raise _error("$.nodes", "either every node declares rank or none do")

    edges_raw = source.get("edges", [])
    if not isinstance(edges_raw, list):
        raise _error("$.edges", "must be an array")
    if len(edges_raw) > MAX_EDGES:
        raise _error("$.edges", f"must contain at most {MAX_EDGES} edges")
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for index, item in enumerate(edges_raw):
        path = f"$.edges[{index}]"
        row = _strict_object(item, path, EDGE_KEYS)
        start = _identifier(row.get("from"), f"{path}.from")
        end = _identifier(row.get("to"), f"{path}.to")
        if start not in node_ids or end not in node_ids:
            raise _error(path, "from and to must reference declared nodes")
        relation = _enum(row.get("relation", "flow"), f"{path}.relation", RELATIONS)
        label = _text(row.get("label"), f"{path}.label", maximum=72, optional=True)
        if relation != "flow" and not label:
            raise _error(f"{path}.label", "is required for a non-flow relationship")
        key = (start, end, label)
        if key in seen_edges:
            raise _error(path, "duplicate edge")
        seen_edges.add(key)
        edge_refs = _refs(row.get("based_on"), f"{path}.based_on")
        _evidence_subset(edge_refs, based_on, f"{path}.based_on")
        edges.append({
            "from": start,
            "to": end,
            "label": label,
            "relation": relation,
            "style": _enum(row.get("style", "solid"), f"{path}.style", LINE_STYLES),
            "tone": _enum(row.get("tone", "primary"), f"{path}.tone", TONES),
            "based_on": edge_refs,
        })
    if len(nodes) > 1 and not edges:
        raise _error("$.edges", "multiple nodes require explicit relationships")

    groups_raw = source.get("groups", [])
    if not isinstance(groups_raw, list):
        raise _error("$.groups", "must be an array")
    if len(groups_raw) > 10:
        raise _error("$.groups", "must contain at most 10 groups")
    groups: list[dict[str, Any]] = []
    group_ids: set[str] = set()
    for index, item in enumerate(groups_raw):
        path = f"$.groups[{index}]"
        row = _strict_object(item, path, GROUP_KEYS)
        group_id = _identifier(row.get("id"), f"{path}.id")
        if group_id in group_ids or group_id in node_ids:
            raise _error(f"{path}.id", "duplicate group or node id")
        group_ids.add(group_id)
        members = _string_list(row.get("nodes"), f"{path}.nodes", maximum_items=MAX_NODES, maximum_text=64)
        if not members:
            raise _error(f"{path}.nodes", "must contain at least one node")
        unknown = [member for member in members if member not in node_ids]
        if unknown:
            raise _error(f"{path}.nodes", f"unknown nodes: {', '.join(unknown)}")
        group_refs = _refs(row.get("based_on"), f"{path}.based_on")
        _evidence_subset(group_refs, based_on, f"{path}.based_on")
        groups.append({
            "id": group_id,
            "label": _text(row.get("label"), f"{path}.label", maximum=80),
            "nodes": members,
            "tone": _enum(row.get("tone", "neutral"), f"{path}.tone", TONES),
            "based_on": group_refs,
        })

    if kind == "tree":
        incoming = {node_id: 0 for node_id in node_ids}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            incoming[edge["to"]] += 1
            outgoing[edge["from"]].append(edge["to"])
        roots = [node_id for node_id, count in incoming.items() if count == 0]
        if len(roots) != 1 or any(count > 1 for count in incoming.values()):
            raise _error("$.edges", "tree requires exactly one root and at most one parent per node")
        if len(edges) != len(nodes) - 1:
            raise _error("$.edges", "tree must connect every node exactly once")
        reachable: set[str] = set()
        pending = [roots[0]]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(outgoing[current])
        if reachable != node_ids:
            raise _error("$.edges", "tree must be acyclic and reachable from its single root")

    result = {
        "schema_version": version,
        "id": figure_id,
        "title": title,
        "kind": kind,
        "visual_treatment": treatment,
        "role": role,
        "description": description,
        "alt": alt,
        "caption": caption,
        "based_on": based_on,
        "concepts": concepts,
        "learner_focus": learner_focus,
        "layout": layout,
        "nodes": nodes,
        "edges": edges,
        "groups": groups,
    }
    if source_figure_id:
        result["source_figure_id"] = source_figure_id
    return result


def load_spec(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SketchSpecError(f"Could not read sketch spec {path}: {exc}") from exc
    return validate_spec(raw)


def _jitter(seed: str, *parts: Any, scale: float = 0.8) -> float:
    payload = "|".join([seed, *(str(part) for part in parts)]).encode("utf-8")
    number = int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") / 0xFFFFFFFF
    return (number * 2 - 1) * scale


def _wrap(text: str, capacity: int) -> tuple[str, ...]:
    if not text:
        return ()
    return tuple(textwrap.wrap(
        text,
        width=capacity,
        break_long_words=True,
        break_on_hyphens=False,
        replace_whitespace=False,
    ))


def _node_dimensions(node: dict[str, Any]) -> tuple[float, float, tuple[str, ...], tuple[str, ...]]:
    label = node["label"]
    detail = node["detail"]
    longest = max((len(word) for word in label.split()), default=8)
    width = min(340.0, max(205.0, 168.0 + min(len(label), 42) * 3.25, 54.0 + longest * 10.2))
    if node["shape"] in {"circle", "decision"}:
        width = max(width, 240.0)
    label_capacity = max(16, int((width - 42) / 12.3))
    detail_capacity = max(22, int((width - 42) / 9.1))
    label_lines = _wrap(label, label_capacity)
    detail_lines = _wrap(detail, detail_capacity)
    height = 48 + len(label_lines) * 30 + len(detail_lines) * 23
    if detail_lines:
        height += 10
    height = max(98.0, float(height))
    if node["shape"] == "decision":
        height = max(142.0, height + 16)
    if node["shape"] == "circle":
        width = height = max(width, height, 180.0)
    return width, height, label_lines, detail_lines


def _rank_nodes(spec: dict[str, Any]) -> dict[str, int]:
    nodes = spec["nodes"]
    if nodes and "rank" in nodes[0]:
        return {node["id"]: node["rank"] for node in nodes}
    ranks: dict[str, int] = {}
    incoming = {node["id"]: 0 for node in nodes}
    outgoing: dict[str, list[str]] = {node["id"]: [] for node in nodes}
    for edge in spec["edges"]:
        incoming[edge["to"]] += 1
        outgoing[edge["from"]].append(edge["to"])
    roots = [node["id"] for node in nodes if incoming[node["id"]] == 0]
    if not roots:
        roots = [nodes[0]["id"]]
    queue = list(roots)
    for root in roots:
        ranks[root] = 0
    while queue:
        current = queue.pop(0)
        for target in outgoing[current]:
            if target not in ranks:
                ranks[target] = ranks[current] + 1
                queue.append(target)
    next_rank = max(ranks.values(), default=-1) + 1
    for node in nodes:
        if node["id"] not in ranks:
            ranks[node["id"]] = next_rank
            next_rank += 1
    return ranks


def _layout(spec: dict[str, Any]) -> tuple[dict[str, NodeBox], float, float, float]:
    direction = spec["layout"]["direction"]
    rank_gap = spec["layout"]["rank_gap"]
    node_gap = spec["layout"]["node_gap"]
    ranks = _rank_nodes(spec)
    dimensions = {node["id"]: _node_dimensions(node) for node in spec["nodes"]}
    by_rank: dict[int, list[dict[str, Any]]] = {}
    declaration_order = {node["id"]: index for index, node in enumerate(spec["nodes"])}
    for node in spec["nodes"]:
        by_rank.setdefault(ranks[node["id"]], []).append(node)
    for rank_nodes in by_rank.values():
        rank_nodes.sort(key=lambda node: (node["order"], declaration_order[node["id"]]))

    title_lines = _wrap(spec["title"], 54)
    title_height = 58 + len(title_lines) * 36
    margin_x = 60.0
    margin_bottom = 70.0
    boxes: dict[str, NodeBox] = {}

    if direction == "top-to-bottom":
        rank_chunks = {
            rank: [rows[index:index + MAX_NODES_PER_ROW] for index in range(0, len(rows), MAX_NODES_PER_ROW)]
            for rank, rows in by_rank.items()
        }
        layer_widths = {
            rank: max(
                sum(dimensions[node["id"]][0] for node in chunk) + node_gap * max(0, len(chunk) - 1)
                for chunk in chunks
            )
            for rank, chunks in rank_chunks.items()
        }
        content_width = max(layer_widths.values(), default=640.0)
        canvas_width = max(680.0, content_width + margin_x * 2)
        y = float(title_height)
        for rank in sorted(by_rank):
            chunks = rank_chunks[rank]
            row_y = y
            for chunk_index, chunk in enumerate(chunks):
                chunk_width = sum(dimensions[node["id"]][0] for node in chunk) + node_gap * max(0, len(chunk) - 1)
                row_height = max(dimensions[node["id"]][1] for node in chunk)
                x = (canvas_width - chunk_width) / 2
                for node in chunk:
                    width, node_height, label_lines, detail_lines = dimensions[node["id"]]
                    boxes[node["id"]] = NodeBox(
                        x,
                        row_y + (row_height - node_height) / 2,
                        width,
                        node_height,
                        label_lines,
                        detail_lines,
                    )
                    x += width + node_gap
                row_y += row_height
                if chunk_index < len(chunks) - 1:
                    row_y += node_gap * 0.7
            y = row_y + rank_gap
        canvas_height = max(520.0, y - rank_gap + margin_bottom)
    else:
        layer_heights = {
            rank: sum(dimensions[node["id"]][1] for node in rows) + node_gap * max(0, len(rows) - 1)
            for rank, rows in by_rank.items()
        }
        content_height = max(layer_heights.values(), default=380.0)
        canvas_height = max(560.0, title_height + content_height + margin_bottom)
        x = margin_x
        for rank in sorted(by_rank):
            rows = by_rank[rank]
            layer_width = max(dimensions[node["id"]][0] for node in rows)
            y = title_height + (content_height - layer_heights[rank]) / 2
            for node in rows:
                width, height, label_lines, detail_lines = dimensions[node["id"]]
                boxes[node["id"]] = NodeBox(x + (layer_width - width) / 2, y, width, height, label_lines, detail_lines)
                y += height + node_gap
            x += layer_width + rank_gap
        canvas_width = max(680.0, x - rank_gap + margin_x)
    return boxes, canvas_width, canvas_height, float(title_height)


def _tone_color(tone: str) -> str:
    if tone == "primary":
        return THEME["primary"]
    if tone == "example":
        return THEME["example"]
    if tone == "warning":
        return THEME["warning"]
    if tone == "connection":
        return THEME["connection"]
    if tone == "danger":
        return THEME["danger"]
    return THEME["graphite"]


def _rough_polyline(
    points: list[tuple[float, float]],
    seed: str,
    key: str,
    *,
    closed: bool = False,
    scale: float = 1.0,
) -> str:
    """Draw a deterministic pencil line with a small bend in every segment."""
    varied = [
        (
            x + _jitter(seed, key, index, "x", scale=0.72 * scale),
            y + _jitter(seed, key, index, "y", scale=0.72 * scale),
        )
        for index, (x, y) in enumerate(points)
    ]
    commands = [f"M {varied[0][0]:.2f} {varied[0][1]:.2f}"]
    targets = varied[1:] + ([varied[0]] if closed else [])
    start = varied[0]
    for index, target in enumerate(targets):
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        bend = _jitter(seed, key, index, "bend", scale=1.55 * scale)
        along = _jitter(seed, key, index, "along", scale=0.45 * scale)
        control_x = (start[0] + target[0]) / 2 + (-dy / length) * bend + (dx / length) * along
        control_y = (start[1] + target[1]) / 2 + (dx / length) * bend + (dy / length) * along
        commands.append(f"Q {control_x:.2f} {control_y:.2f} {target[0]:.2f} {target[1]:.2f}")
        start = target
    if closed:
        commands.append("Z")
    return " ".join(commands)


def _rough_polygon(
    points: list[tuple[float, float]], seed: str, key: str, *, scale: float = 1.0
) -> str:
    return _rough_polyline(points, seed, key, closed=True, scale=scale)


def _rounded_path(box: NodeBox, radius: float, seed: str, key: str, *, scale: float = 1.0) -> str:
    x, y, width, height = box.x, box.y, box.width, box.height
    radius = min(radius, width / 2, height / 2)
    return _rough_polygon(
        [
            (x + radius, y),
            (x + width - radius, y),
            (x + width, y + radius),
            (x + width, y + height - radius),
            (x + width - radius, y + height),
            (x + radius, y + height),
            (x, y + height - radius),
            (x, y + radius),
        ],
        seed,
        key,
        scale=scale,
    )


def _node_path(
    node: dict[str, Any], box: NodeBox, seed: str, trace: str, *, scale: float = 1.0
) -> str:
    x, y, width, height = box.x, box.y, box.width, box.height
    shape = node["shape"]
    key = f'{node["id"]}:{trace}'
    if shape == "decision":
        return _rough_polygon(
            [(box.cx, y), (x + width, box.cy), (box.cx, y + height), (x, box.cy)],
            seed,
            key,
            scale=scale,
        )
    if shape == "data":
        skew = min(34.0, width * 0.12)
        return _rough_polygon(
            [(x + skew, y), (x + width, y), (x + width - skew, y + height), (x, y + height)],
            seed,
            key,
            scale=scale,
        )
    if shape == "note":
        fold = min(28.0, width * 0.12)
        return _rough_polygon(
            [(x, y), (x + width - fold, y), (x + width, y + fold), (x + width, y + height), (x, y + height)],
            seed,
            key,
            scale=scale,
        )
    if shape == "datastore":
        return _rounded_path(box, 24.0, seed, key, scale=scale)
    if shape == "circle":
        radius = min(width, height) / 2
        points = [
            (
                box.cx + radius * math.cos(index * math.tau / 16),
                box.cy + radius * math.sin(index * math.tau / 16),
            )
            for index in range(16)
        ]
        return _rough_polygon(points, seed, key, scale=scale)
    if shape in {"rounded", "terminal"}:
        return _rounded_path(
            box, height / 2 if shape == "terminal" else 12.0, seed, key, scale=scale
        )
    return _rough_polygon(
        [(x, y), (x + width, y), (x + width, y + height), (x, y + height)],
        seed,
        key,
        scale=scale,
    )


def _edge_geometry(
    start: NodeBox,
    end: NodeBox,
    direction: str,
    index: int,
) -> tuple[list[tuple[float, float]], float, float]:
    if start == end:
        channel = start.x + start.width + 46 + index * 8
        return [
            (start.x + start.width, start.cy),
            (channel, start.cy),
            (channel, start.y - 34),
            (start.cx, start.y - 34),
            (start.cx, start.y),
        ], channel, start.y - 34
    if direction == "top-to-bottom" and end.cy > start.cy + 4:
        sx, sy = start.cx, start.y + start.height
        ex, ey = end.cx, end.y
        mid = (sy + ey) / 2
        return [(sx, sy), (sx, mid), (ex, mid), (ex, ey)], (sx + ex) / 2, mid
    if direction == "left-to-right" and end.cx > start.cx + 4:
        sx, sy = start.x + start.width, start.cy
        ex, ey = end.x, end.cy
        mid = (sx + ex) / 2
        return [(sx, sy), (mid, sy), (mid, ey), (ex, ey)], mid, (sy + ey) / 2
    if abs(start.cy - end.cy) < max(start.height, end.height):
        if end.cx >= start.cx:
            sx, sy = start.x + start.width, start.cy
            ex, ey = end.x, end.cy
        else:
            sx, sy = start.x, start.cy
            ex, ey = end.x + end.width, end.cy
        mid = (sx + ex) / 2
        return [(sx, sy), (mid, sy), (mid, ey), (ex, ey)], mid, (sy + ey) / 2
    channel = max(start.x + start.width, end.x + end.width) + 42 + index * 9
    sx, sy = start.x + start.width, start.cy
    ex, ey = end.x + end.width, end.cy
    return [(sx, sy), (channel, sy), (channel, ey), (ex, ey)], channel, (sy + ey) / 2


def _svg_text_lines(
    lines: tuple[str, ...],
    x: float,
    y: float,
    *,
    css_class: str,
    line_height: float,
) -> str:
    if not lines:
        return ""
    tspans = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else line_height
        tspans.append(f'<tspan x="{x:.2f}" dy="{dy:.2f}">{html.escape(line)}</tspan>')
    return f'<text class="{css_class}" x="{x:.2f}" y="{y:.2f}" text-anchor="middle">{"".join(tspans)}</text>'


def audit_svg_style(svg_value: bytes | str) -> dict[str, Any]:
    """Mechanically reject opaque, framed or overly clean generated sketches."""
    svg_text = svg_value.decode("utf-8") if isinstance(svg_value, bytes) else svg_value
    issues: list[str] = []
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        return {"ok": False, "issues": [f"invalid-svg:{exc}"], "pencil_traces": 0}

    namespace = "{http://www.w3.org/2000/svg}"
    if root.get("data-transparent-canvas") != "1":
        issues.append("opaque-or-unattested-canvas")
    if root.get("data-pencil-style") != "graphite-overlay-v1":
        issues.append("pencil-style-marker-missing")
    if "background:" in svg_text.lower() or "background-color:" in svg_text.lower():
        issues.append("explicit-background-style")

    forbidden_tags = {"rect": "opaque-or-framed-rect", "pattern": "internal-paper-pattern", "filter": "ui-filter"}
    for element in root.iter():
        local_name = element.tag.removeprefix(namespace)
        if local_name in forbidden_tags:
            issues.append(forbidden_tags[local_name])
        if local_name == "path" and element.get("fill", "none") != "none":
            issues.append("solid-vector-fill")

    for child in root:
        if child.tag == f"{namespace}path" and child.get("data-role") != "annotation":
            issues.append("outer-frame-path")

    pencil_traces = 0
    for group in root.iter(f"{namespace}g"):
        group_id = group.get("id", "")
        if not (group_id.startswith("node-") or group_id.startswith("edge-")):
            continue
        traces = [
            child for child in group
            if child.tag == f"{namespace}path" and child.get("data-pencil-trace") in {"main", "ghost"}
        ]
        pencil_traces += len(traces)
        if len(traces) < 2:
            issues.append(f"single-clean-trace:{group_id}")
            continue
        if any("Q" not in trace.get("d", "") and "C" not in trace.get("d", "") for trace in traces):
            issues.append(f"perfectly-straight-trace:{group_id}")

    return {
        "ok": not issues,
        "issues": sorted(set(issues)),
        "pencil_traces": pencil_traces,
    }


def render_svg(spec_value: Any) -> tuple[bytes, dict[str, Any]]:
    """Render canonical SVG bytes; equal normalized specs always yield equal bytes."""
    spec = validate_spec(spec_value)
    spec_bytes = (canonical_json(spec, indent=2) + "\n").encode("utf-8")
    spec_sha = digest_bytes(spec_bytes)
    seed = digest_bytes(canonical_json(spec).encode("utf-8"))
    boxes, width, height, title_height = _layout(spec)
    title_lines = _wrap(spec["title"], 54)
    kind_labels = {
        "flow": "flujo",
        "tree": "árbol",
        "concept-map": "mapa conceptual",
        "relations": "relaciones",
        "technical-schematic": "esquema técnico",
    }

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="sketch-title sketch-desc" '
            f'data-study-sketch="1" data-generator="{GENERATOR_ID}" data-generator-version="{GENERATOR_VERSION}" '
            f'data-spec-sha256="{spec_sha}" data-transparent-canvas="1" '
            f'data-pencil-style="graphite-overlay-v1">'
        ),
        f'<title id="sketch-title">{html.escape(spec["alt"])}</title>',
        f'<desc id="sketch-desc">{html.escape(spec["caption"])}</desc>',
        (
            '<metadata id="study-sketch-metadata">'
            + html.escape(canonical_json({
                "generator": GENERATOR_ID,
                "generator_version": GENERATOR_VERSION,
                "spec_sha256": spec_sha,
                "spec": spec,
            }))
            + '</metadata>'
        ),
        '<defs>',
    ]
    for tone in sorted(TONES):
        stroke = _tone_color(tone)
        lines.append(
            f'<marker id="arrow-{tone}" markerWidth="12" markerHeight="12" refX="10" refY="6" '
            f'orient="auto" markerUnits="strokeWidth"><path d="M 1.2 1.4 Q 5.7 4.2 10 6 '
            f'Q 5.4 7.8 1.4 10.8" fill="none" stroke="{stroke}" stroke-width="1.45" '
            f'stroke-linecap="round" stroke-linejoin="round"/></marker>'
        )
    lines.extend([
        '<style>',
        f'.sketch-label{{font:600 22px "Segoe Print","Bradley Hand","Comic Sans MS",cursive;fill:{THEME["ink"]}}}',
        f'.sketch-detail{{font:400 17px "Segoe Print","Bradley Hand","Comic Sans MS",cursive;fill:{THEME["graphite_soft"]}}}',
        f'.sketch-title{{font:600 29px "Segoe Print","Bradley Hand","Comic Sans MS",cursive;fill:{THEME["ink"]}}}',
        f'.sketch-kind{{font:400 15px "Segoe Print","Bradley Hand","Comic Sans MS",cursive;fill:{THEME["graphite_soft"]}}}',
        f'.sketch-edge-label{{font:600 15px "Segoe Print","Bradley Hand","Comic Sans MS",cursive;fill:{THEME["graphite"]}}}',
        f'.sketch-group-label{{font:600 15px "Segoe Print","Bradley Hand","Comic Sans MS",cursive;fill:{THEME["graphite_soft"]}}}',
        '</style>',
        '</defs>',
    ])
    title_y = 52.0
    for index, title_line in enumerate(title_lines):
        lines.append(
            f'<text class="sketch-title" x="22" y="{title_y + index * 36:.2f}">{html.escape(title_line)}</text>'
        )
    lines.append(
        f'<text class="sketch-kind" x="{width - 22:.2f}" y="48" text-anchor="end">{kind_labels[spec["kind"]]}</text>'
    )
    underline_y = min(title_height - 24, title_y + len(title_lines) * 36 - 18)
    underline = _rough_polyline(
        [(22, underline_y), (min(width - 22, 450), underline_y)],
        seed,
        "title-underline:main",
        scale=1.25,
    )
    underline_ghost = _rough_polyline(
        [(22, underline_y), (min(width - 22, 450), underline_y)],
        seed,
        "title-underline:ghost",
        scale=1.85,
    )
    lines.append(
        f'<path data-role="annotation" data-pencil-trace="main" d="{underline}" fill="none" '
        f'stroke="{THEME["primary"]}" stroke-width="1.8" stroke-linecap="round" opacity=".88"/>'
    )
    lines.append(
        f'<path data-role="annotation" data-pencil-trace="ghost" d="{underline_ghost}" fill="none" '
        f'stroke="{THEME["primary"]}" stroke-width=".65" stroke-linecap="round" opacity=".34"/>'
    )

    lines.append('<g id="groups">')
    for group in spec["groups"]:
        members = [boxes[node_id] for node_id in group["nodes"]]
        left = min(box.x for box in members) - 25
        top = min(box.y for box in members) - 34
        right = max(box.x + box.width for box in members) + 25
        bottom = max(box.y + box.height for box in members) + 25
        group_box = NodeBox(left, top, right - left, bottom - top, (), ())
        stroke = _tone_color(group["tone"])
        path = _rounded_path(group_box, 14, seed, f'group:{group["id"]}:main', scale=1.0)
        ghost_path = _rounded_path(group_box, 14, seed, f'group:{group["id"]}:ghost', scale=1.65)
        evidence = html.escape(" ".join(group["based_on"]), quote=True)
        lines.append(
            f'<g id="group-{group["id"]}" data-based-on="{evidence}"><path data-pencil-trace="main" '
            f'd="{path}" fill="none" stroke="{stroke}" stroke-width="1.35" stroke-dasharray="7 7" opacity=".72"/>'
            f'<path data-pencil-trace="ghost" d="{ghost_path}" fill="none" stroke="{stroke}" '
            f'stroke-width=".55" stroke-dasharray="7 7" opacity=".28"/>'
            f'<text class="sketch-group-label" x="{left + 16:.2f}" y="{top + 23:.2f}">{html.escape(group["label"])}</text></g>'
        )
    lines.append('</g>')

    node_by_id = {node["id"]: node for node in spec["nodes"]}
    lines.append('<g id="edges" fill="none">')
    for index, edge in enumerate(spec["edges"]):
        edge_points, label_x, label_y = _edge_geometry(
            boxes[edge["from"]], boxes[edge["to"]], spec["layout"]["direction"], index
        )
        stroke = _tone_color(edge["tone"])
        dash = ' stroke-dasharray="9 7"' if edge["style"] == "dashed" else ""
        evidence = html.escape(" ".join(edge["based_on"]), quote=True)
        edge_id = f'edge-{index + 1}-{edge["from"]}-{edge["to"]}'
        edge_name = edge["label"] or edge["relation"]
        edge_title = html.escape(
            f'{node_by_id[edge["from"]]["label"]} → {node_by_id[edge["to"]]["label"]}: {edge_name}'
        )
        path = _rough_polyline(edge_points, seed, f"{edge_id}:main", scale=1.15)
        ghost_path = _rough_polyline(edge_points, seed, f"{edge_id}:ghost", scale=1.8)
        lines.append(
            f'<g id="{edge_id}" data-from="{edge["from"]}" data-to="{edge["to"]}" '
            f'data-relation="{edge["relation"]}" data-based-on="{evidence}"><title>{edge_title}</title>'
            f'<path data-pencil-trace="main" d="{path}" fill="none" stroke="{stroke}" stroke-width="1.85" '
            f'stroke-linejoin="round" stroke-linecap="round" marker-end="url(#arrow-{edge["tone"]})"{dash}/>'
            f'<path data-pencil-trace="ghost" d="{ghost_path}" fill="none" stroke="{stroke}" '
            f'stroke-width=".7" stroke-linejoin="round" stroke-linecap="round" opacity=".34"{dash}/>'
        )
        if edge["label"]:
            lines.append(
                f'<text class="sketch-edge-label" x="{label_x:.2f}" y="{label_y - 7:.2f}" '
                f'text-anchor="middle">{html.escape(edge["label"])}</text>'
            )
        lines.append('</g>')
    lines.append('</g>')

    lines.append('<g id="nodes">')
    for node_id in [node["id"] for node in spec["nodes"]]:
        node = node_by_id[node_id]
        box = boxes[node_id]
        stroke = _tone_color(node["tone"])
        path = _node_path(node, box, seed, "main", scale=1.0)
        ghost_path = _node_path(node, box, seed, "ghost", scale=1.65)
        evidence = html.escape(" ".join(node["based_on"]), quote=True)
        node_title = node["label"] + (f'. {node["detail"]}' if node["detail"] else '')
        lines.append(
            f'<g id="node-{node_id}" data-shape="{node["shape"]}" data-based-on="{evidence}">'
            f'<title>{html.escape(node_title)}</title>'
            f'<path data-pencil-trace="main" d="{path}" fill="none" stroke="{stroke}" stroke-width="1.85" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path data-pencil-trace="ghost" d="{ghost_path}" fill="none" stroke="{stroke}" '
            f'stroke-width=".72" stroke-linecap="round" stroke-linejoin="round" opacity=".38"/>'
        )
        total_text_height = len(box.label_lines) * 30 + len(box.detail_lines) * 23
        if box.detail_lines:
            total_text_height += 10
        label_y = box.cy - total_text_height / 2 + 20
        lines.append(_svg_text_lines(box.label_lines, box.cx, label_y, css_class="sketch-label", line_height=30))
        if box.detail_lines:
            detail_y = label_y + (len(box.label_lines) - 1) * 30 + 36
            lines.append(_svg_text_lines(box.detail_lines, box.cx, detail_y, css_class="sketch-detail", line_height=23))
        lines.append('</g>')
    lines.extend(['</g>', '</svg>'])
    svg_bytes = ("\n".join(line for line in lines if line != "") + "\n").encode("utf-8")
    style_audit = audit_svg_style(svg_bytes)
    if not style_audit["ok"]:
        raise SketchSpecError(f"generated SVG failed style audit: {', '.join(style_audit['issues'])}")
    return svg_bytes, {
        "ok": True,
        "generator": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "spec_sha256": spec_sha,
        "svg_sha256": digest_bytes(svg_bytes),
        "kind": spec["kind"],
        "nodes": len(spec["nodes"]),
        "edges": len(spec["edges"]),
        "width": int(round(width)),
        "height": int(round(height)),
        "style_audit": style_audit,
    }


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _unit_asset_base(course: Path, unit_value: str) -> tuple[dict[str, str], Path]:
    unit = resolve_unit(course, unit_value)
    if not unit.get("unit_id"):
        raise SketchSpecError(f"Could not resolve stable unit id from: {unit_value}")
    base = unit_root(course, unit["unit_id"]) if has_unit_layout(course) else course
    return unit, base


def _existing_idempotent_result(
    course: Path,
    unit_id: str,
    spec: dict[str, Any],
    asset_rel: str,
    spec_rel: str,
    asset_path: Path,
    spec_path: Path,
    spec_sha: str,
    svg_sha: str,
) -> dict[str, Any] | None:
    key = derived_key(spec["id"])
    registry = load_registry(course)
    record = registry.get("figures", {}).get(key)
    if not isinstance(record, dict):
        return None
    generation = record.get("generation")
    exact = (
        isinstance(generation, dict)
        and generation.get("method") == "deterministic-svg"
        and generation.get("generator") == GENERATOR_ID
        and generation.get("version") == GENERATOR_VERSION
        and generation.get("spec") == spec_rel
        and generation.get("spec_sha256") == spec_sha
        and record.get("unit_id") == unit_id
        and record.get("asset") == asset_rel
        and record.get("visual_treatment") == spec["visual_treatment"]
        and record.get("source_figure_id") == spec.get("source_figure_id")
        and record.get("asset_sha256") == svg_sha
        and asset_path.is_file()
        and spec_path.is_file()
        and sha256(asset_path) == svg_sha
        and sha256(spec_path) == spec_sha
    )
    if not exact:
        raise SketchSpecError(f"Figure id already exists with different content; refusing overwrite: {key}")
    return {
        "ok": True,
        "created": False,
        "key": key,
        "record": record,
        "spec_sha256": spec_sha,
        "svg_sha256": svg_sha,
    }


def generate_and_register(course: Path, unit_value: str, spec_value: Any) -> dict[str, Any]:
    """Generate SVG + canonical spec and register them as one retry-safe operation."""
    spec = validate_spec(spec_value)
    unit, base = _unit_asset_base(course, unit_value)
    asset_rel = f"assets/figures/{spec['id']}.svg"
    spec_rel = f"assets/figures/{spec['id']}.sketch.json"
    asset_path = (base / asset_rel).resolve()
    spec_path = (base / spec_rel).resolve()
    asset_root = (base / "assets" / "figures").resolve()
    if not asset_path.is_relative_to(asset_root) or not spec_path.is_relative_to(asset_root):
        raise SketchSpecError("Generated files must stay under assets/figures/")

    spec_bytes = (canonical_json(spec, indent=2) + "\n").encode("utf-8")
    spec_sha = digest_bytes(spec_bytes)
    svg_bytes, render_report = render_svg(spec)
    svg_sha = digest_bytes(svg_bytes)
    existing = _existing_idempotent_result(
        course, unit["unit_id"], spec, asset_rel, spec_rel, asset_path, spec_path, spec_sha, svg_sha
    )
    if existing is not None:
        return existing
    if asset_path.exists() or spec_path.exists():
        occupied = asset_path if asset_path.exists() else spec_path
        raise SketchSpecError(f"Generated figure path already exists; refusing overwrite: {occupied}")

    created: list[Path] = []
    try:
        _write_atomic(spec_path, spec_bytes)
        created.append(spec_path)
        _write_atomic(asset_path, svg_bytes)
        created.append(asset_path)
        generation = {
            "method": "deterministic-svg",
            "generator": GENERATOR_ID,
            "version": GENERATOR_VERSION,
            "spec": spec_rel,
            "spec_sha256": spec_sha,
            "diagram_kind": spec["kind"],
        }
        result = register_derived(
            course,
            spec["id"],
            unit["unit_id"],
            asset_rel,
            spec["description"],
            spec["based_on"],
            concepts=spec["concepts"],
            learner_focus=spec["learner_focus"],
            kind="diagram",
            role=spec["role"],
            visual_treatment=spec["visual_treatment"],
            source_figure_id=spec.get("source_figure_id"),
            generation=generation,
        )
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return {
        **result,
        "created": True,
        "spec": spec_rel,
        **render_report,
    }


def _safe_output(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def cmd_validate(args: argparse.Namespace) -> None:
    spec = load_spec(Path(args.spec).resolve())
    spec_bytes = (canonical_json(spec, indent=2) + "\n").encode("utf-8")
    print(canonical_json({
        "ok": True,
        "id": spec["id"],
        "kind": spec["kind"],
        "nodes": len(spec["nodes"]),
        "edges": len(spec["edges"]),
        "spec_sha256": digest_bytes(spec_bytes),
    }, indent=2))


def cmd_render(args: argparse.Namespace) -> None:
    spec = load_spec(Path(args.spec).resolve())
    svg, report = render_svg(spec)
    output = _safe_output(args.output)
    if output.exists():
        if output.is_file() and output.read_bytes() == svg:
            print(canonical_json({**report, "output": str(output), "created": False}, indent=2))
            return
        raise SystemExit(f"Output already exists with different content; refusing overwrite: {output}")
    _write_atomic(output, svg)
    print(canonical_json({**report, "output": str(output), "created": True}, indent=2))


def cmd_audit(args: argparse.Namespace) -> None:
    path = Path(args.svg).resolve()
    try:
        report = audit_svg_style(path.read_bytes())
    except OSError as exc:
        raise SketchSpecError(f"Could not read SVG {path}: {exc}") from exc
    print(canonical_json({**report, "svg": str(path)}, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


def cmd_generate(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    spec = load_spec(Path(args.spec).resolve())
    try:
        result = generate_and_register(course, args.unit, spec)
    except (SketchSpecError, ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
    print(canonical_json(result, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic notebook-sketch SVG figures")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("validate", help="Validate and fingerprint a structured sketch spec")
    command.add_argument("--spec", required=True)
    command.set_defaults(func=cmd_validate)
    command = sub.add_parser("render", help="Render a sketch spec to SVG without registering it")
    command.add_argument("--spec", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=cmd_render)
    command = sub.add_parser(
        "audit", help="Reject opaque, framed or excessively clean generated SVGs"
    )
    command.add_argument("--svg", required=True)
    command.set_defaults(func=cmd_audit)
    command = sub.add_parser("generate", help="Generate and atomically register a derived SVG")
    command.add_argument("--course", required=True)
    command.add_argument("--unit", required=True)
    command.add_argument("--spec", required=True)
    command.set_defaults(func=cmd_generate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except SketchSpecError as exc:
        print(canonical_json({"ok": False, "error": str(exc)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
