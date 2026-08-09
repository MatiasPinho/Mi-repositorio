#!/usr/bin/env python3
"""Deterministic PDF visual scanner and selected-page renderer.

Requires PyMuPDF (pip install -r requirements-visual.txt) only for PDF visual features.
No AI calls are made.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import resolve_course  # noqa: E402
from unit_identity import resolve_unit, record_unit_id  # noqa: E402


def visual_capabilities() -> dict[str, Any]:
    available = importlib.util.find_spec("fitz") is not None
    return {
        "pdf_visuals": available,
        "pymupdf": "available" if available else "missing",
        "install": None if available else f"{sys.executable} -m pip install -r requirements-visual.txt",
    }


def registry_path(course: Path) -> Path:
    return course / "conocimiento" / "figures.json"


def load_registry(course: Path) -> dict[str, Any]:
    path = registry_path(course)
    if not path.exists():
        return {"version": 2, "figures": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("figures.json must be a JSON object")
    data.setdefault("version", 2)
    data.setdefault("figures", {})
    if not isinstance(data["figures"], dict):
        raise SystemExit("figures.json figures must be an object")
    return data


def save_registry(course: Path, data: dict[str, Any]) -> None:
    path = registry_path(course)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_id(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-")
    if not value:
        raise SystemExit("Figure id must contain letters or numbers")
    return value[:90]


def derived_key(value: str) -> str:
    raw = value.strip()
    if raw.startswith("derived:"):
        raw = raw.split(":", 1)[1]
    return "derived:" + safe_id(raw)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_source(course: Path, value: str) -> Path:
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [course / "fuentes" / raw, course / raw]
    for p in candidates:
        try:
            rp = p.resolve()
            if rp.is_file() and rp.is_relative_to((course / "fuentes").resolve()):
                return rp
        except OSError:
            pass
    raise SystemExit(f"Source file not found under fuentes/: {value}")


def registry_issues(course: Path, data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = data or load_registry(course)
    figures = data.get("figures", {})
    issues: list[dict[str, Any]] = []
    seen_ids: dict[str, str] = {}
    seen_assets: dict[str, tuple[str, str]] = {}
    for key, item in figures.items():
        if not isinstance(item, dict):
            issues.append({"figure": key, "reason": "invalid-record"})
            continue
        origin = str(item.get("origin") or ("source" if item.get("source_file") else "")).strip().lower()
        fid = str(item.get("id", key)).strip()
        if not fid:
            issues.append({"figure": key, "reason": "missing-id"})
        if fid in seen_ids and seen_ids[fid] != key:
            issues.append({"figure": key, "reason": "duplicate-id", "other": seen_ids[fid], "id": fid})
        else:
            seen_ids[fid] = key
        if origin == "derived":
            if not key.startswith("derived:") or not fid.startswith("derived:"):
                issues.append({"figure": key, "reason": "derived-id-not-namespaced"})
            if not item.get("unit_id"):
                issues.append({"figure": key, "reason": "derived-unit-id-missing"})
            if not item.get("based_on"):
                issues.append({"figure": key, "reason": "derived-provenance-missing"})
        elif origin and origin != "source":
            issues.append({"figure": key, "reason": "invalid-origin", "origin": origin})

        asset_value = item.get("asset")
        asset = asset_value.strip() if isinstance(asset_value, str) else ""
        if origin == "derived" and not asset:
            issues.append({"figure": key, "reason": "derived-asset-missing"})
        if asset:
            target = (course / asset).resolve()
            if not target.is_file():
                issues.append({"figure": key, "reason": "asset-missing", "asset": asset})
            prior = seen_assets.get(asset)
            if prior and prior[0] != key:
                issues.append({"figure": key, "reason": "asset-collision", "asset": asset, "other": prior[0], "origins": [prior[1], origin]})
            else:
                seen_assets[asset] = (key, origin)

        source = item.get("source_file")
        expected = item.get("source_sha256")
        if source and expected:
            try:
                src = resolve_source(course, str(source))
                if sha256(src) != expected:
                    issues.append({"figure": key, "reason": "source-changed", "source": source})
            except SystemExit:
                issues.append({"figure": key, "reason": "source-missing", "source": source})
    return issues


def visual_capabilities() -> dict[str, Any]:
    available = importlib.util.find_spec("fitz") is not None
    return {"pdf_visuals": available, "pymupdf": "available" if available else "missing"}


def cmd_preflight(args: argparse.Namespace) -> None:
    print(json.dumps(visual_capabilities(), ensure_ascii=False, indent=2))


def cmd_migrate_registry(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    data = load_registry(course)
    figures = data.get("figures", {})
    migrated: dict[str, dict[str, Any]] = {}
    changes: list[dict[str, Any]] = []
    for old_key, raw in figures.items():
        if not isinstance(raw, dict):
            migrated[old_key] = raw
            continue
        item = dict(raw)
        origin = str(item.get("origin") or ("source" if item.get("source_file") else "")).strip().lower()
        new_key = old_key
        if origin == "derived":
            new_key = derived_key(str(item.get("id") or old_key))
            if new_key in migrated and new_key != old_key:
                raise SystemExit(f"Cannot migrate legacy figure; target id already exists: {new_key}")
            if item.get("id") != new_key:
                changes.append({"figure": old_key, "change": "namespace-id", "to": new_key})
            item["id"] = new_key
            if not item.get("unit_id"):
                resolved = resolve_unit(course, item.get("unit", ""))
                if resolved.get("unit_id"):
                    item["unit_id"] = resolved["unit_id"]
                    changes.append({"figure": old_key, "change": "add-unit-id", "to": resolved["unit_id"]})
            if not item.get("based_on"):
                concepts = [str(x).strip() for x in item.get("concepts", []) if str(x).strip()]
                item["based_on"] = [f"concept:{x}" for x in concepts] or ["legacy-registry:provenance-not-recorded"]
                changes.append({"figure": old_key, "change": "add-explicit-legacy-provenance"})
        migrated[new_key] = item
    data["figures"] = migrated
    data["version"] = max(int(data.get("version", 1) or 1), 2)
    issues = registry_issues(course, data)
    if issues:
        print(json.dumps({"ok": False, "changes": changes, "issues": issues}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    if changes and not args.dry_run:
        save_registry(course, data)
    print(json.dumps({"ok": True, "dry_run": bool(args.dry_run), "changed": bool(changes), "changes": changes, "figures": len(migrated)}, ensure_ascii=False, indent=2))


def cmd_verify(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    data = load_registry(course)
    issues = registry_issues(course, data)
    result = {"ok": not issues, "issues": issues, "figures": len(data.get("figures", {}))}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preflight"); p.add_argument("--course", required=True); p.set_defaults(func=cmd_preflight)
    p = sub.add_parser("migrate-registry"); p.add_argument("--course", required=True); p.add_argument("--dry-run", action="store_true"); p.set_defaults(func=cmd_migrate_registry)
    p = sub.add_parser("verify"); p.add_argument("--course", required=True); p.set_defaults(func=cmd_verify)
    return ap


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
