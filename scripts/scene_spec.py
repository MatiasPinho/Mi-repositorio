#!/usr/bin/env python3
"""Strict schema-2 scene graph contract for AI-composed study illustrations.

The planner owns semantic content and composition. The renderer owns every
style decision. This module is deliberately dependency free so the same
normalization is used by CLI, MCP, tests and the deterministic renderer.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

SCHEMA_VERSION = 2
MAX_ELEMENTS = 80
MAX_REFERENCES = 96
MAX_TEXT = 320
VARIANTS = ("wide", "narrow")
TREATMENTS = {"reinterpret", "preserve+derived_sketch"}
ROLES = {"essential", "supporting"}
REPRESENTATION_ROLES = {"literal", "structural", "pedagogical_analogy"}
ELEMENT_TYPES = {
    "text", "shape", "line", "path", "connector", "arrow", "group",
    "region", "brace", "axis", "divider", "annotation",
}
SHAPES = {
    "rectangle", "rounded", "circle", "ellipse", "polygon", "decision",
    "data", "note", "component", "datastore",
}
TONES = {"neutral", "primary", "example", "warning", "connection", "danger"}
LINE_STYLES = {"solid", "dashed"}
RELATIONS = {"flow", "relation", "dependency", "feedback", "association"}
TEXT_ROLES = {"label", "detail", "title", "caption", "annotation"}
PATH_OPS = {"move", "line", "quadratic", "cubic", "close"}

_TOP = {
    "schema_version", "id", "title", "visual_treatment", "role",
    "representation_role", "description", "alt", "caption", "based_on",
    "concepts", "learner_focus", "source_figure_id", "elements", "layouts",
}
_ELEMENT_COMMON = {
    "id", "type", "tone", "semantic", "based_on", "representation_role",
}
_ELEMENT_ALLOWED = {
    "text": _ELEMENT_COMMON | {"text", "text_role"},
    "annotation": _ELEMENT_COMMON | {"text", "text_role"},
    "shape": _ELEMENT_COMMON | {"shape", "label", "detail"},
    "line": _ELEMENT_COMMON | {"style"},
    "path": _ELEMENT_COMMON | {"style"},
    "arrow": _ELEMENT_COMMON | {"style"},
    "connector": _ELEMENT_COMMON | {"from", "to", "label", "relation", "style", "arrowheads"},
    "group": _ELEMENT_COMMON | {"members", "label", "style"},
    "region": _ELEMENT_COMMON | {"members", "label", "shape", "style"},
    "brace": _ELEMENT_COMMON | {"label", "style"},
    "axis": _ELEMENT_COMMON | {"label", "style"},
    "divider": _ELEMENT_COMMON | {"style"},
}
_LAYOUT_KEYS = {"canvas", "placements", "allowed_overlaps"}
_CANVAS_KEYS = {"width", "height"}
_PLACEMENT_KEYS = {
    "x", "y", "width", "height", "points", "commands", "text_anchor",
    "label_x", "label_y", "rotation",
}
_DANGEROUS_TEXT = re.compile(
    r"(?:<\s*/?\s*(?:svg|script|style|foreignobject|iframe|img|object|embed|path|rect|circle|ellipse|polygon|polyline|g)\b|"
    r"javascript\s*:|data\s*:\s*(?:text/html|image/svg)|\bon(?:load|error|click|mouseover)\s*=|"
    r"\b(?:style|class|href|src)\s*=|url\s*\()",
    re.IGNORECASE,
)
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_REF = re.compile(r"^[a-z][a-z0-9_-]*:.+$")


class SceneSpecError(ValueError):
    """The scene graph is unsafe, ambiguous or academically unauditable."""


def canonical_json(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        separators=(",", ":") if indent is None else None,
    )


def scene_bytes(scene: dict[str, Any]) -> bytes:
    return (canonical_json(scene, indent=2) + "\n").encode("utf-8")


def scene_sha256(scene: dict[str, Any]) -> str:
    return hashlib.sha256(scene_bytes(scene)).hexdigest()


def _err(path: str, message: str) -> SceneSpecError:
    return SceneSpecError(f"{path}: {message}")


def _obj(value: Any, path: str, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _err(path, "must be an object")
    extra = sorted(set(value) - allowed)
    if extra:
        raise _err(path, f"unknown fields: {', '.join(extra)}")
    return value


def _text(value: Any, path: str, *, max_len: int = MAX_TEXT, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str):
        raise _err(path, "must be a string")
    if value != value.strip():
        raise _err(path, "must not have leading/trailing whitespace")
    if not value and not optional:
        raise _err(path, "must not be empty")
    if len(value) > max_len:
        raise _err(path, f"must be at most {max_len} characters")
    if any(ord(ch) < 32 and ch not in "\t" for ch in value):
        raise _err(path, "contains control characters")
    if _DANGEROUS_TEXT.search(value):
        raise _err(path, "contains markup/style/script/URL syntax; scene text must be plain")
    return value


def _id(value: Any, path: str) -> str:
    text = _text(value, path, max_len=64)
    if not _ID.fullmatch(text):
        raise _err(path, "must use lowercase letters, digits, hyphen or underscore")
    return text


def _enum(value: Any, path: str, allowed: set[str]) -> str:
    text = _text(value, path, max_len=64)
    if text not in allowed:
        raise _err(path, f"must be one of: {', '.join(sorted(allowed))}")
    return text


def _number(value: Any, path: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _err(path, "must be a finite number")
    out = float(value)
    if not math.isfinite(out):
        raise _err(path, "must be finite")
    if minimum is not None and out < minimum:
        raise _err(path, f"must be >= {minimum}")
    if maximum is not None and out > maximum:
        raise _err(path, f"must be <= {maximum}")
    return out


def _refs(value: Any, path: str, *, required: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise _err(path, "must be an array")
    if required and not value:
        raise _err(path, "must contain at least one canonical reference")
    if len(value) > MAX_REFERENCES:
        raise _err(path, f"must contain at most {MAX_REFERENCES} references")
    out: list[str] = []
    for i, raw in enumerate(value):
        ref = _text(raw, f"{path}[{i}]", max_len=180)
        if not _REF.fullmatch(ref):
            raise _err(f"{path}[{i}]", "must be namespaced, e.g. concept:cache")
        if ref in out:
            raise _err(f"{path}[{i}]", "duplicate reference")
        out.append(ref)
    return out


def _string_list(value: Any, path: str, *, max_items: int, max_len: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _err(path, "must be an array")
    if len(value) > max_items:
        raise _err(path, f"must contain at most {max_items} values")
    out: list[str] = []
    for i, raw in enumerate(value):
        text = _text(raw, f"{path}[{i}]", max_len=max_len)
        if text in out:
            raise _err(f"{path}[{i}]", "duplicate value")
        out.append(text)
    return out


def _subset(refs: list[str], global_refs: list[str], path: str) -> None:
    missing = [ref for ref in refs if ref not in global_refs]
    if missing:
        raise _err(path, f"references not present in top-level based_on: {', '.join(missing)}")


def _members(value: Any, path: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _err(path, "must be an array")
    out: list[str] = []
    for i, raw in enumerate(value):
        item = _id(raw, f"{path}[{i}]")
        if item in out:
            raise _err(f"{path}[{i}]", "duplicate member")
        out.append(item)
    return out


def _normalize_element(raw: Any, index: int, global_refs: list[str], top_role: str) -> dict[str, Any]:
    path = f"$.elements[{index}]"
    if not isinstance(raw, dict):
        raise _err(path, "must be an object")
    kind = _enum(raw.get("type"), f"{path}.type", ELEMENT_TYPES)
    row = _obj(raw, path, _ELEMENT_ALLOWED[kind])
    element_id = _id(row.get("id"), f"{path}.id")
    semantic = row.get("semantic", True)
    if not isinstance(semantic, bool):
        raise _err(f"{path}.semantic", "must be boolean")
    tone = _enum(row.get("tone", "neutral"), f"{path}.tone", TONES)
    representation_role = _enum(
        row.get("representation_role", top_role),
        f"{path}.representation_role",
        REPRESENTATION_ROLES,
    )
    refs = _refs(row.get("based_on", []), f"{path}.based_on", required=semantic)
    _subset(refs, global_refs, f"{path}.based_on")

    result: dict[str, Any] = {
        "id": element_id,
        "type": kind,
        "tone": tone,
        "semantic": semantic,
        "representation_role": representation_role,
        "based_on": refs,
    }

    def plain(name: str, *, max_len: int = 180, optional: bool = True) -> str:
        return _text(row.get(name), f"{path}.{name}", max_len=max_len, optional=optional)

    if kind in {"text", "annotation"}:
        if not semantic:
            raise _err(path, "text-bearing elements cannot be decorative/non-semantic")
        result["text"] = plain("text", max_len=220, optional=False)
        result["text_role"] = _enum(
            row.get("text_role", "annotation" if kind == "annotation" else "label"),
            f"{path}.text_role",
            TEXT_ROLES,
        )
    elif kind == "shape":
        result["shape"] = _enum(row.get("shape"), f"{path}.shape", SHAPES)
        result["label"] = plain("label", max_len=120)
        result["detail"] = plain("detail", max_len=220)
        if not semantic and (result["label"] or result["detail"]):
            raise _err(path, "decorative shapes cannot carry academic text")
    elif kind == "connector":
        if not semantic:
            raise _err(path, "connectors express relationships and must be semantic")
        result["from"] = _id(row.get("from"), f"{path}.from")
        result["to"] = _id(row.get("to"), f"{path}.to")
        result["label"] = plain("label", max_len=90)
        result["relation"] = _enum(row.get("relation", "relation"), f"{path}.relation", RELATIONS)
        result["style"] = _enum(row.get("style", "solid"), f"{path}.style", LINE_STYLES)
        result["arrowheads"] = _enum(row.get("arrowheads", "end"), f"{path}.arrowheads", {"none", "start", "end", "both"})
    elif kind in {"line", "path", "arrow", "brace", "axis", "divider"}:
        result["style"] = _enum(row.get("style", "solid"), f"{path}.style", LINE_STYLES)
        label = plain("label", max_len=90) if kind in {"brace", "axis"} else ""
        if label:
            if not semantic:
                raise _err(path, "decorative geometry cannot carry academic labels")
            result["label"] = label
    elif kind in {"group", "region"}:
        result["members"] = _members(row.get("members"), f"{path}.members")
        result["label"] = plain("label", max_len=100)
        result["style"] = _enum(row.get("style", "dashed" if kind == "group" else "solid"), f"{path}.style", LINE_STYLES)
        if kind == "region":
            result["shape"] = _enum(row.get("shape", "rounded"), f"{path}.shape", {"rectangle", "rounded", "ellipse", "polygon"})
        if not semantic and result["label"]:
            raise _err(path, "decorative groups/regions cannot carry academic labels")

    return result


def _normalize_command(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _err(path, "must be an object")
    allowed = {"op", "x", "y", "cx", "cy", "cx1", "cy1", "cx2", "cy2"}
    row = _obj(raw, path, allowed)
    op = _enum(row.get("op"), f"{path}.op", PATH_OPS)
    required = {
        "move": ("x", "y"),
        "line": ("x", "y"),
        "quadratic": ("cx", "cy", "x", "y"),
        "cubic": ("cx1", "cy1", "cx2", "cy2", "x", "y"),
        "close": (),
    }[op]
    permitted = {"op", *required}
    extra = sorted(set(row) - permitted)
    if extra:
        raise _err(path, f"fields not valid for {op}: {', '.join(extra)}")
    result: dict[str, Any] = {"op": op}
    for key in required:
        result[key] = _number(row.get(key), f"{path}.{key}", minimum=-10000, maximum=10000)
    return result


def _normalize_placement(raw: Any, path: str, kind: str, shape: str = "") -> dict[str, Any]:
    row = _obj(raw, path, _PLACEMENT_KEYS)
    result: dict[str, Any] = {}
    box_kinds = {"shape", "text", "annotation", "group", "region"}
    if kind in box_kinds and not (kind in {"shape", "region"} and shape == "polygon"):
        for key in ("x", "y", "width", "height"):
            minimum = 1 if key in {"width", "height"} else -10000
            result[key] = _number(row.get(key), f"{path}.{key}", minimum=minimum, maximum=10000)
    if kind in {"shape", "region"} and shape == "polygon":
        points = row.get("points")
        if not isinstance(points, list) or len(points) < 3:
            raise _err(f"{path}.points", "polygon requires at least three [x,y] points")
        normalized_points = []
        for i, point in enumerate(points):
            if not isinstance(point, list) or len(point) != 2:
                raise _err(f"{path}.points[{i}]", "must be [x,y]")
            normalized_points.append([
                _number(point[0], f"{path}.points[{i}][0]", minimum=-10000, maximum=10000),
                _number(point[1], f"{path}.points[{i}][1]", minimum=-10000, maximum=10000),
            ])
        result["points"] = normalized_points
    if kind in {"line", "path", "connector", "arrow", "brace", "axis", "divider"}:
        commands = row.get("commands")
        if not isinstance(commands, list) or len(commands) < 2:
            raise _err(f"{path}.commands", "requires at least move + drawing command")
        normalized = [_normalize_command(cmd, f"{path}.commands[{i}]") for i, cmd in enumerate(commands)]
        if normalized[0]["op"] != "move":
            raise _err(f"{path}.commands[0]", "first command must be move")
        if all(cmd["op"] in {"move", "close"} for cmd in normalized):
            raise _err(f"{path}.commands", "must contain a drawing command")
        result["commands"] = normalized
    if "rotation" in row:
        result["rotation"] = _number(row["rotation"], f"{path}.rotation", minimum=-180, maximum=180)
    if "text_anchor" in row:
        result["text_anchor"] = _enum(row["text_anchor"], f"{path}.text_anchor", {"start", "middle", "end"})
    for key in ("label_x", "label_y"):
        if key in row:
            result[key] = _number(row[key], f"{path}.{key}", minimum=-10000, maximum=10000)
    return result


def _normalize_layout(raw: Any, variant: str, elements: list[dict[str, Any]]) -> dict[str, Any]:
    path = f"$.layouts.{variant}"
    row = _obj(raw, path, _LAYOUT_KEYS)
    canvas_raw = _obj(row.get("canvas"), f"{path}.canvas", _CANVAS_KEYS)
    canvas = {
        "width": _number(canvas_raw.get("width"), f"{path}.canvas.width", minimum=240, maximum=2400),
        "height": _number(canvas_raw.get("height"), f"{path}.canvas.height", minimum=180, maximum=2400),
    }
    placements_raw = row.get("placements")
    if not isinstance(placements_raw, dict):
        raise _err(f"{path}.placements", "must be an object keyed by element id")
    ids = {element["id"] for element in elements}
    if set(placements_raw) != ids:
        missing = sorted(ids - set(placements_raw))
        extra = sorted(set(placements_raw) - ids)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("unknown=" + ",".join(extra))
        raise _err(f"{path}.placements", "must place every semantic element exactly once (" + "; ".join(details) + ")")
    by_id = {element["id"]: element for element in elements}
    placements = {
        element_id: _normalize_placement(
            placements_raw[element_id],
            f"{path}.placements.{element_id}",
            by_id[element_id]["type"],
            by_id[element_id].get("shape", ""),
        )
        for element_id in sorted(ids)
    }
    overlaps_raw = row.get("allowed_overlaps", [])
    if not isinstance(overlaps_raw, list):
        raise _err(f"{path}.allowed_overlaps", "must be an array of [id,id] pairs")
    overlaps: list[list[str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for i, pair in enumerate(overlaps_raw):
        if not isinstance(pair, list) or len(pair) != 2:
            raise _err(f"{path}.allowed_overlaps[{i}]", "must be [id,id]")
        left = _id(pair[0], f"{path}.allowed_overlaps[{i}][0]")
        right = _id(pair[1], f"{path}.allowed_overlaps[{i}][1]")
        if left == right or left not in ids or right not in ids:
            raise _err(f"{path}.allowed_overlaps[{i}]", "must name two distinct known elements")
        key = tuple(sorted((left, right)))
        if key in seen_pairs:
            raise _err(f"{path}.allowed_overlaps[{i}]", "duplicate overlap pair")
        seen_pairs.add(key)
        overlaps.append(list(key))
    return {"canvas": canvas, "placements": placements, "allowed_overlaps": sorted(overlaps)}


def validate_scene(raw: Any) -> dict[str, Any]:
    """Validate and return a deterministic normalized schema-2 scene."""
    source = _obj(raw, "$", _TOP)
    version = source.get("schema_version")
    if version != SCHEMA_VERSION:
        raise _err("$.schema_version", f"must equal {SCHEMA_VERSION}")
    scene_id = _id(source.get("id"), "$.id")
    title = _text(source.get("title"), "$.title", max_len=120)
    treatment = _enum(source.get("visual_treatment"), "$.visual_treatment", TREATMENTS)
    role = _enum(source.get("role", "supporting"), "$.role", ROLES)
    representation_role = _enum(
        source.get("representation_role", "structural"),
        "$.representation_role",
        REPRESENTATION_ROLES,
    )
    description = _text(source.get("description"), "$.description", max_len=320)
    alt = _text(source.get("alt"), "$.alt", max_len=320)
    caption = _text(source.get("caption"), "$.caption", max_len=320)
    based_on = _refs(source.get("based_on"), "$.based_on")
    concepts = _string_list(source.get("concepts"), "$.concepts", max_items=24, max_len=100)
    learner_focus = _string_list(source.get("learner_focus"), "$.learner_focus", max_items=10, max_len=180)

    source_figure_id = source.get("source_figure_id")
    if treatment == "preserve+derived_sketch":
        source_figure_id = _text(source_figure_id, "$.source_figure_id", max_len=100)
        if f"figure:{source_figure_id}" not in based_on:
            raise _err("$.based_on", f"must include figure:{source_figure_id}")
    elif source_figure_id is not None:
        raise _err("$.source_figure_id", "only valid with preserve+derived_sketch")

    elements_raw = source.get("elements")
    if not isinstance(elements_raw, list) or not elements_raw:
        raise _err("$.elements", "must contain at least one element")
    if len(elements_raw) > MAX_ELEMENTS:
        raise _err("$.elements", f"must contain at most {MAX_ELEMENTS} elements")
    elements = [_normalize_element(raw_element, i, based_on, representation_role) for i, raw_element in enumerate(elements_raw)]
    ids = [element["id"] for element in elements]
    if len(set(ids)) != len(ids):
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        raise _err("$.elements", "duplicate ids: " + ", ".join(duplicates))
    known = set(ids)
    for i, element in enumerate(elements):
        path = f"$.elements[{i}]"
        if element["type"] == "connector":
            if element["from"] not in known or element["to"] not in known:
                raise _err(path, "connector from/to must reference known elements")
            if element["from"] == element["to"]:
                raise _err(path, "self connector is not supported in V2; use a path/arrow if needed")
        if element["type"] in {"group", "region"}:
            unknown = sorted(set(element.get("members", [])) - known)
            if unknown:
                raise _err(path, "unknown members: " + ", ".join(unknown))
            if element["id"] in element.get("members", []):
                raise _err(path, "cannot contain itself")

    layouts_raw = source.get("layouts")
    if not isinstance(layouts_raw, dict) or set(layouts_raw) != set(VARIANTS):
        raise _err("$.layouts", "must contain exactly wide and narrow")
    layouts = {variant: _normalize_layout(layouts_raw[variant], variant, elements) for variant in VARIANTS}

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": scene_id,
        "title": title,
        "visual_treatment": treatment,
        "role": role,
        "representation_role": representation_role,
        "description": description,
        "alt": alt,
        "caption": caption,
        "based_on": based_on,
        "concepts": concepts,
        "learner_focus": learner_focus,
        "elements": elements,
        "layouts": layouts,
    }
    if source_figure_id:
        result["source_figure_id"] = source_figure_id
    return result


def load_scene(path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SceneSpecError(f"Could not read scene spec {path}: {exc}") from exc
    return validate_scene(raw)
