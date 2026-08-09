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


def derived_key(value: str) -> str:
    raw = value.strip()
    if raw.startswith("derived:"):
        tail = raw.split(":", 1)[1]
    else:
        tail = raw
    return "derived:" + safe_id(tail)


def safe_course_asset(course: Path, value: str) -> tuple[Path, str]:
    raw = Path(value)
    path = raw if raw.is_absolute() else course / raw
    path = path.resolve()
    asset_root = (course / "assets" / "figures").resolve()
    if not path.is_relative_to(asset_root):
        raise SystemExit("Derived figure asset must live under assets/figures/")
    if not path.is_file():
        raise SystemExit(f"Derived figure asset does not exist: {path}")
    return path, path.relative_to(course).as_posix()


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
        # Source figures may be registered before a raster/vector asset has been
        # extracted. JSON null means "known pedagogical figure, asset pending" and
        # is valid for source records. Derived figures, however, must always point
        # at a concrete generated asset. Never stringify null to "None": that used
        # to create both false asset-missing errors and false collisions.
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


def require_fitz():
    try:
        import fitz  # type: ignore
        return fitz
    except Exception as exc:
        raise SystemExit(
            "Visual PDF support needs PyMuPDF. Install it explicitly with: "
            f"{sys.executable} -m pip install -r requirements-visual.txt\n{exc}"
        )


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


def page_metrics(page: Any) -> dict[str, Any]:
    images = page.get_images(full=True)
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    text = " ".join(page.get_text("text").split())
    words = page.get_text("words")
    area = max(float(page.rect.width * page.rect.height), 1.0)
    # Heuristic only: identify pages worth inspecting, never academic relevance.
    vector_score = min(len(drawings), 80) / 8.0
    image_score = min(len(images), 12) * 2.0
    sparse_bonus = 1.5 if len(text) < 500 and (images or len(drawings) >= 8) else 0.0
    visual_score = round(image_score + vector_score + sparse_bonus, 2)
    return {
        "images": len(images),
        "drawings": len(drawings),
        "words": len(words),
        "text_chars": len(text),
        "visual_score": visual_score,
        "candidate": bool(images or len(drawings) >= 8),
        "text_preview": text[:280],
        "width": round(float(page.rect.width), 1),
        "height": round(float(page.rect.height), 1),
    }


def scan_pdf(path: Path, relative: str) -> dict[str, Any]:
    fitz = require_fitz()
    doc = fitz.open(path)
    pages = []
    try:
        for i, page in enumerate(doc):
            row = {"page": i + 1, **page_metrics(page)}
            pages.append(row)
    finally:
        doc.close()
    return {
        "file": relative,
        "sha256": sha256(path),
        "pages": len(pages),
        "candidates": sum(1 for p in pages if p["candidate"]),
        "page_metrics": pages,
    }


def cmd_scan(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    official = course / "fuentes" / "oficiales"
    rows = []
    if official.exists():
        for p in sorted(official.rglob("*.pdf")):
            rel = p.relative_to(course / "fuentes").as_posix()
            rows.append(scan_pdf(p, rel))
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": rows,
        "note": "Candidate is a deterministic visual-density heuristic, not a judgement of teaching value.",
    }
    if args.write:
        out = course / ".study" / "figure-pages.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def safe_id(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-")
    if not value:
        raise SystemExit("Figure id must contain letters or numbers")
    return value[:90]


def cmd_render_page(args: argparse.Namespace) -> None:
    fitz = require_fitz()
    course = resolve_course(args.course)
    source = resolve_source(course, args.file)
    page_no = args.page
    if page_no < 1:
        raise SystemExit("--page is 1-based and must be >= 1")
    doc = fitz.open(source)
    try:
        if page_no > len(doc):
            raise SystemExit(f"Page {page_no} out of range (PDF has {len(doc)} pages)")
        page = doc[page_no - 1]
        clip = None
        if args.clip:
            nums = [float(x.strip()) for x in args.clip.split(",")]
            if len(nums) != 4:
                raise SystemExit("--clip expects x0,y0,x1,y1 in PDF points")
            clip = fitz.Rect(*nums)
            if clip.is_empty or not page.rect.intersects(clip):
                raise SystemExit("Invalid clip rectangle")
            clip = clip & page.rect
        scale = max(args.dpi, 72) / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        out_dir = course / "assets" / "figures"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{safe_id(args.id)}.png"
        pix.save(out)
    finally:
        doc.close()
    result = {
        "asset": out.relative_to(course).as_posix(),
        "source_file": source.relative_to(course / "fuentes").as_posix(),
        "source_sha256": sha256(source),
        "page": page_no,
        "clip": args.clip or None,
        "dpi": args.dpi,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_preflight(args: argparse.Namespace) -> None:
    result = visual_capabilities()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_register_derived(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    data = load_registry(course)
    figures = data["figures"]
    key = derived_key(args.id)
    if key in figures:
        raise SystemExit(f"Figure id already exists; refusing overwrite: {key}")
    asset_path, asset_rel = safe_course_asset(course, args.asset)
    # Never reuse an asset already owned by a source or another derived record.
    for existing_key, existing in figures.items():
        if isinstance(existing, dict) and str(existing.get("asset", "")) == asset_rel:
            raise SystemExit(f"Figure asset already registered by {existing_key}; refusing collision: {asset_rel}")
    unit = resolve_unit(course, args.unit)
    if not unit.get("unit_id"):
        raise SystemExit(f"Could not resolve stable unit id from: {args.unit}")
    record = {
        "id": key,
        "unit_id": unit["unit_id"],
        "unit": unit.get("label") or args.unit,
        "concepts": args.concept or [],
        "kind": args.kind,
        "role": args.role,
        "description": args.description,
        "learner_focus": args.learner_focus or [],
        "asset": asset_rel,
        "asset_sha256": sha256(asset_path),
        "origin": "derived",
        "based_on": args.based_on or [],
    }
    figures[key] = record
    data["version"] = max(int(data.get("version", 1) or 1), 2)
    issues = registry_issues(course, data)
    if issues:
        figures.pop(key, None)
        print(json.dumps({"ok": False, "issues": issues}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    save_registry(course, data)
    print(json.dumps({"ok": True, "key": key, "record": record}, ensure_ascii=False, indent=2))


def cmd_migrate_registry(args: argparse.Namespace) -> None:
    """Normalize legacy derived records without rereading source material."""
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

def cmd_scope(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    data = load_registry(course)
    target = resolve_unit(course, args.unit)
    rows = {}
    for key, item in data.get("figures", {}).items():
        if isinstance(item, dict) and record_unit_id(course, item) == target.get("unit_id"):
            rows[key] = item
    print(json.dumps({"unit_id": target.get("unit_id"), "count": len(rows), "figures": rows}, ensure_ascii=False, indent=2))


def cmd_verify(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    data = load_registry(course)
    issues = registry_issues(course, data)
    result = {"ok": not issues, "issues": issues, "figures": len(data.get("figures", {}))}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Scan/render source visuals deterministically")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--course", required=True)
    p.add_argument("--write", action="store_true")
    p.set_defaults(func=cmd_scan)
    p = sub.add_parser("render-page")
    p.add_argument("--course", required=True)
    p.add_argument("--file", required=True, help="Path relative to fuentes/, e.g. oficiales/Unidad2.pdf")
    p.add_argument("--page", type=int, required=True, help="1-based PDF page")
    p.add_argument("--id", required=True)
    p.add_argument("--dpi", type=int, default=144)
    p.add_argument("--clip", help="Optional crop x0,y0,x1,y1 in PDF points")
    p.set_defaults(func=cmd_render_page)
    p = sub.add_parser("preflight", help="Report optional PDF visual capability without failing when unavailable")
    p.set_defaults(func=cmd_preflight)
    p = sub.add_parser("register-derived", help="Register a derived figure with collision-safe provenance")
    p.add_argument("--course", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--asset", required=True)
    p.add_argument("--kind", default="diagram", choices=["diagram", "table", "chart", "screenshot", "illustration", "other"])
    p.add_argument("--role", default="supporting", choices=["essential", "supporting"])
    p.add_argument("--description", required=True)
    p.add_argument("--concept", action="append")
    p.add_argument("--learner-focus", action="append")
    p.add_argument("--based-on", action="append", required=True)
    p.set_defaults(func=cmd_register_derived)
    p = sub.add_parser("migrate-registry", help="Normalize legacy derived figure records without reprocessing sources")
    p.add_argument("--course", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_migrate_registry)
    p = sub.add_parser("scope", help="Resolve a unit and list its registered figures")
    p.add_argument("--course", required=True)
    p.add_argument("--unit", required=True)
    p.set_defaults(func=cmd_scope)
    p = sub.add_parser("verify")
    p.add_argument("--course", required=True)
    p.set_defaults(func=cmd_verify)
    return ap


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
