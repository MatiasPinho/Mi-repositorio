#!/usr/bin/env python3
"""Deterministic unit identity helpers.

Human labels may vary ("U1", "Unidad 1", "Unidad 1: Conceptos básicos").
This module maps them to a stable machine id such as ``unidad-1`` so artifact,
concept and figure scoping never depends on display text equality.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def normalize(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(value.split())


def slug(text: Any) -> str:
    value = normalize(text)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def canonical_unit_id(value: Any) -> str:
    raw = normalize(value)
    if not raw:
        return ""
    m = re.search(r"\b(?:unidad|unit|u)\s*[-_ ]?\s*(\d+)\b", raw)
    if not m:
        m = re.fullmatch(r"u(\d+)", raw)
    if m:
        return f"unidad-{int(m.group(1))}"
    return slug(raw)


def _read_academic(course: Path) -> dict[str, Any]:
    path = course / "academico" / "academic.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def unit_rows(course: Path) -> list[dict[str, Any]]:
    data = _read_academic(course)
    rows = data.get("units", []) if isinstance(data, dict) else []
    return [x for x in rows if isinstance(x, dict)]


def aliases_for_unit(row: dict[str, Any]) -> set[str]:
    values = {
        row.get("unit_id", ""),
        row.get("id", ""),
        row.get("name", ""),
        row.get("title", ""),
    }
    aliases: set[str] = set()
    for value in values:
        if value:
            aliases.add(normalize(value))
            aliases.add(canonical_unit_id(value))
    uid = stable_unit_id_from_row(row)
    if uid:
        aliases.add(uid)
    return {x for x in aliases if x}


def stable_unit_id_from_row(row: dict[str, Any]) -> str:
    explicit = canonical_unit_id(row.get("unit_id", ""))
    if explicit:
        return explicit
    for key in ("id", "name", "title"):
        value = canonical_unit_id(row.get(key, ""))
        if value:
            return value
    return ""


def resolve_unit(course: Path, scope: Any) -> dict[str, str]:
    """Resolve a scope/label to stable id + display label without mutating files."""
    raw = str(scope or "").strip()
    target_norm = normalize(raw)
    target_id = canonical_unit_id(raw)
    for row in unit_rows(course):
        aliases = aliases_for_unit(row)
        if target_norm in aliases or target_id in aliases:
            uid = stable_unit_id_from_row(row) or target_id
            label = str(row.get("name") or row.get("title") or raw or uid)
            return {"unit_id": uid, "label": label}
    return {"unit_id": target_id, "label": raw}


def record_unit_id(course: Path, item: dict[str, Any]) -> str:
    explicit = canonical_unit_id(item.get("unit_id", ""))
    if explicit:
        return explicit
    legacy = item.get("unit", "")
    if legacy:
        return resolve_unit(course, legacy)["unit_id"]
    return ""


def scope_matches_record(course: Path, item: dict[str, Any], scope: Any) -> bool:
    target = resolve_unit(course, scope)["unit_id"]
    if not target:
        return True
    return record_unit_id(course, item) == target
