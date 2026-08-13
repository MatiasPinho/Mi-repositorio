#!/usr/bin/env python3
"""Deterministic PDF visual scanner and selected-page renderer.

Requires PyMuPDF (pip install -r requirements-visual.txt) only for PDF visual features.
No AI calls are made.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VISUAL_TREATMENTS = {
    "reinterpret",
    "preserve",
    "preserve+derived_sketch",
}

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import resolve_course  # noqa: E402
if __package__:
    from .course_layout import (  # noqa: E402
        LayoutError,
        content_path,
        has_unit_layout,
        iter_source_files,
        load_registry as load_layout_registry,
        resolve_source as resolve_layout_source,
        save_registry as save_layout_registry,
        source_ref,
        unit_root,
    )
    from .unit_identity import resolve_unit, record_unit_id  # noqa: E402
else:
    from course_layout import (  # noqa: E402
        LayoutError,
        content_path,
        has_unit_layout,
        iter_source_files,
        load_registry as load_layout_registry,
        resolve_source as resolve_layout_source,
        save_registry as save_layout_registry,
        source_ref,
        unit_root,
    )
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


def load_registry(course: Path, unit: str = "") -> dict[str, Any]:
    data = load_layout_registry(course, "figures", unit)
    if not isinstance(data, dict):
        raise SystemExit("figures.json must be a JSON object")
    data.setdefault("version", 2)
    data.setdefault("figures", {})
    if not isinstance(data["figures"], dict):
        raise SystemExit("figures.json figures must be an object")
    return data


def save_registry(course: Path, data: dict[str, Any], unit: str = "") -> None:
    try:
        save_layout_registry(course, "figures", data, unit)
    except LayoutError as exc:
        raise SystemExit(str(exc)) from exc


def derived_key(value: str) -> str:
    raw = value.strip()
    if raw.startswith("derived:"):
        tail = raw.split(":", 1)[1]
    else:
        tail = raw
    return "derived:" + safe_id(tail)


def safe_course_asset(course: Path, value: str, unit: str = "") -> tuple[Path, str]:
    raw = Path(value)
    if raw.is_absolute():
        path = raw
    elif unit and has_unit_layout(course):
        normalized = value.replace("\\", "/")
        path = course / raw if normalized.startswith("unidades/") else unit_root(course, unit) / raw
    else:
        path = course / raw
    path = path.resolve()
    asset_root = ((unit_root(course, unit) if unit and has_unit_layout(course) else course) / "assets" / "figures").resolve()
    if not path.is_relative_to(asset_root):
        raise SystemExit("Derived figure asset must live under assets/figures/")
    if not path.is_file():
        raise SystemExit(f"Derived figure asset does not exist: {path}")
    base = unit_root(course, unit) if unit and has_unit_layout(course) else course
    return path, path.relative_to(base).as_posix()


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
        if "visual_treatment" in item:
            visual_treatment = str(item.get("visual_treatment") or "").strip()
            if visual_treatment not in VISUAL_TREATMENTS:
                issues.append({
                    "figure": key,
                    "reason": "invalid-visual-treatment",
                    "visual_treatment": visual_treatment,
                })
            elif visual_treatment == "reinterpret" and origin != "derived":
                issues.append({"figure": key, "reason": "reinterpret-origin-invalid"})
            elif visual_treatment == "preserve" and origin != "source":
                issues.append({"figure": key, "reason": "preserve-origin-invalid"})
            elif visual_treatment == "preserve+derived_sketch":
                source_id = str(item.get("source_figure_id") or "").strip()
                if origin != "derived":
                    issues.append({"figure": key, "reason": "derived-sketch-origin-invalid"})
                if not source_id:
                    issues.append({"figure": key, "reason": "derived-sketch-source-missing"})
                else:
                    source_item = figures.get(source_id)
                    if not isinstance(source_item, dict):
                        source_item = next(
                            (
                                candidate for candidate in figures.values()
                                if isinstance(candidate, dict)
                                and str(candidate.get("id") or "").strip() == source_id
                            ),
                            None,
                        )
                    if not isinstance(source_item, dict):
                        issues.append({
                            "figure": key,
                            "reason": "derived-sketch-source-unknown",
                            "source_figure_id": source_id,
                        })
                    else:
                        source_origin = str(
                            source_item.get("origin") or ("source" if source_item.get("source_file") else "")
                        ).strip().lower()
                        if source_origin != "source":
                            issues.append({
                                "figure": key,
                                "reason": "derived-sketch-source-not-original",
                                "source_figure_id": source_id,
                            })
                        source_unit = record_unit_id(course, source_item)
                        item_unit = record_unit_id(course, item)
                        if source_unit and item_unit and source_unit != item_unit:
                            issues.append({
                                "figure": key,
                                "reason": "derived-sketch-source-wrong-unit",
                                "source_figure_id": source_id,
                            })
            elif item.get("source_figure_id"):
                issues.append({"figure": key, "reason": "source-companion-without-derived-sketch"})
        # Source figures may be registered before a raster/vector asset has been
        # extracted. JSON null means "known pedagogical figure, asset pending" and
        # is valid for source records. Derived figures, however, must always point
        # at a concrete generated asset. Never stringify null to "None": that used
        # to create both false asset-missing errors and false collisions.
        asset_value = item.get("asset")
        asset = asset_value.strip() if isinstance(asset_value, str) else ""
        target: Path | None = None
        unit_value = record_unit_id(course, item)
        if origin == "derived" and not asset:
            issues.append({"figure": key, "reason": "derived-asset-missing"})
        if asset:
            target = content_path(course, unit_value, asset) if unit_value and has_unit_layout(course) else (course / asset).resolve()
            if not target.is_file():
                issues.append({"figure": key, "reason": "asset-missing", "asset": asset})
            else:
                expected_asset = str(item.get("asset_sha256") or "").strip()
                if expected_asset and sha256(target) != expected_asset:
                    issues.append({"figure": key, "reason": "asset-changed", "asset": asset})
            asset_identity = f"{unit_value}:{asset}" if has_unit_layout(course) else asset
            prior = seen_assets.get(asset_identity)
            if prior and prior[0] != key:
                issues.append({"figure": key, "reason": "asset-collision", "asset": asset, "other": prior[0], "origins": [prior[1], origin]})
            else:
                seen_assets[asset_identity] = (key, origin)
        generation = item.get("generation")
        if generation is not None:
            if not isinstance(generation, dict):
                issues.append({"figure": key, "reason": "invalid-generation-metadata"})
            else:
                method = str(generation.get("method") or "").strip()
                generator = str(generation.get("generator") or "").strip()
                version = generation.get("version")
                spec_asset = str(generation.get("spec") or "").strip()
                spec_sha = str(generation.get("spec_sha256") or "").strip()
                treatment = str(item.get("visual_treatment") or "").strip()
                if origin != "derived":
                    issues.append({"figure": key, "reason": "generated-origin-invalid"})
                if treatment not in {"reinterpret", "preserve+derived_sketch"}:
                    issues.append({"figure": key, "reason": "generated-treatment-invalid"})
                if method != "deterministic-svg":
                    issues.append({"figure": key, "reason": "invalid-generation-method"})
                if not generator or isinstance(version, bool) or not isinstance(version, int) or version < 1:
                    issues.append({"figure": key, "reason": "invalid-generator-identity"})
                if not asset.lower().endswith(".svg"):
                    issues.append({"figure": key, "reason": "generated-asset-not-svg"})
                if not spec_asset or not spec_sha:
                    issues.append({"figure": key, "reason": "generated-spec-metadata-missing"})
                else:
                    base = unit_root(course, unit_value) if unit_value and has_unit_layout(course) else course
                    spec_path = (base / spec_asset).resolve()
                    figure_root = (base / "assets" / "figures").resolve()
                    if not spec_path.is_relative_to(figure_root):
                        issues.append({"figure": key, "reason": "generated-spec-outside-figures"})
                    elif not spec_path.is_file():
                        issues.append({"figure": key, "reason": "generated-spec-missing", "spec": spec_asset})
                    elif sha256(spec_path) != spec_sha:
                        issues.append({"figure": key, "reason": "generated-spec-changed", "spec": spec_asset})
                    else:
                        try:
                            spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
                        except (json.JSONDecodeError, OSError, UnicodeError):
                            issues.append({"figure": key, "reason": "generated-spec-invalid-json", "spec": spec_asset})
                        else:
                            expected_id = str(item.get("id") or key).removeprefix("derived:")
                            if not isinstance(spec_data, dict) or spec_data.get("schema_version") != 1:
                                issues.append({"figure": key, "reason": "generated-spec-version-invalid"})
                            elif str(spec_data.get("id") or "") != expected_id:
                                issues.append({"figure": key, "reason": "generated-spec-id-mismatch"})
                if target and target.is_file():
                    try:
                        svg_text = target.read_text(encoding="utf-8")
                    except (OSError, UnicodeError):
                        issues.append({"figure": key, "reason": "generated-svg-unreadable"})
                    else:
                        if 'data-study-sketch="1"' not in svg_text:
                            issues.append({"figure": key, "reason": "generated-svg-marker-missing"})
                        if spec_sha and f'data-spec-sha256="{spec_sha}"' not in svg_text:
                            issues.append({"figure": key, "reason": "generated-svg-spec-mismatch"})
                        if generator and f'data-generator="{generator}"' not in svg_text:
                            issues.append({"figure": key, "reason": "generated-svg-generator-mismatch"})
                        if isinstance(version, int) and not isinstance(version, bool) and version >= 2:
                            if 'data-transparent-canvas="1"' not in svg_text:
                                issues.append({"figure": key, "reason": "generated-svg-opaque-canvas"})
                            if 'data-pencil-style="graphite-overlay-v1"' not in svg_text:
                                issues.append({"figure": key, "reason": "generated-svg-pencil-style-missing"})
                            if "<rect" in svg_text or "<pattern" in svg_text:
                                issues.append({"figure": key, "reason": "generated-svg-frame-or-background"})
        source = item.get("source_file")
        expected = item.get("source_sha256")
        if source and expected:
            try:
                src = resolve_source(course, str(source), record_unit_id(course, item))
                if sha256(src) != expected:
                    issues.append({"figure": key, "reason": "source-changed", "source": source})
            except SystemExit:
                issues.append({"figure": key, "reason": "source-missing", "source": source})
    return issues


def require_fitz():
    try:
        # Some dependency builds print compatibility notices during import. The
        # figure commands expose JSON on stdout, so third-party chatter belongs
        # on stderr and can never corrupt the machine-readable payload.
        with contextlib.redirect_stdout(sys.stderr):
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


def resolve_source(course: Path, value: str, unit: str = "") -> Path:
    try:
        return resolve_layout_source(course, value, unit)
    except LayoutError as exc:
        raise SystemExit(str(exc)) from exc


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
    pages = []
    # Keep any library diagnostics away from stdout; cmd_scan prints the sole
    # JSON document only after all PDFs have been inspected.
    with contextlib.redirect_stdout(sys.stderr):
        doc = fitz.open(path)
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
    rows = []
    for p, rel, _unit_id in iter_source_files(course, args.unit or ""):
        if "oficiales" in {part.lower() for part in p.parts} and p.suffix.lower() == ".pdf":
            rows.append(scan_pdf(p, rel))
    note = "Candidate is a deterministic visual-density heuristic, not a judgement of teaching value."
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": rows,
        "note": note,
    }
    if args.write:
        out_base = unit_root(course, args.unit) if args.unit and has_unit_layout(course) else course
        out = out_base / ".study" / "figure-pages.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if out.is_file():
            try:
                loaded = json.loads(out.read_text(encoding="utf-8"))
                existing = loaded if isinstance(loaded, dict) else {}
            except (json.JSONDecodeError, OSError, UnicodeError):
                existing = {}
        same_scan = (
            existing.get("version") == payload["version"]
            and existing.get("files") == rows
            and existing.get("note") == note
            and isinstance(existing.get("generated_at"), str)
            and bool(existing.get("generated_at"))
        )
        if same_scan:
            # Preserve both bytes on disk and the original timestamp when the
            # deterministic scan result is unchanged.
            payload["generated_at"] = existing["generated_at"]
        else:
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
    source = resolve_source(course, args.file, args.unit or "")
    page_no = args.page
    if page_no < 1:
        raise SystemExit("--page is 1-based and must be >= 1")
    with contextlib.redirect_stdout(sys.stderr):
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
            out_base = unit_root(course, args.unit) if args.unit and has_unit_layout(course) else course
            out_dir = out_base / "assets" / "figures"
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"{safe_id(args.id)}.png"
            pix.save(out)
        finally:
            doc.close()
    result = {
        "asset": out.relative_to(out_base).as_posix(),
        "source_file": source_ref(course, source, args.unit or ""),
        "source_sha256": sha256(source),
        "page": page_no,
        "clip": args.clip or None,
        "dpi": args.dpi,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_preflight(args: argparse.Namespace) -> None:
    result = visual_capabilities()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def verify_registry(course: Path) -> dict[str, Any]:
    data = load_registry(course)
    issues = registry_issues(course, data)
    return {"ok": not issues, "issues": issues, "figures": len(data.get("figures", {}))}


def register_derived(
    course: Path,
    figure_id: str,
    unit_value: str,
    asset: str,
    description: str,
    based_on: list[str],
    *,
    concepts: list[str] | None = None,
    learner_focus: list[str] | None = None,
    kind: str = "diagram",
    role: str = "supporting",
    visual_treatment: str | None = None,
    source_figure_id: str | None = None,
    generation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collision-safe derived figure registration for CLI and MCP callers."""
    if not based_on:
        raise ValueError("based_on debe contener al menos una referencia canónica")
    unit = resolve_unit(course, unit_value)
    if not unit.get("unit_id"):
        raise ValueError(f"Could not resolve stable unit id from: {unit_value}")
    data = load_registry(course)
    figures = data["figures"]
    key = derived_key(figure_id)
    if key in figures:
        raise ValueError(f"Figure id already exists; refusing overwrite: {key}")
    try:
        asset_path, asset_rel = safe_course_asset(course, asset, unit["unit_id"])
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    for existing_key, existing in figures.items():
        if (
            isinstance(existing, dict)
            and existing.get("asset")
            and str(existing.get("asset")) == asset_rel
            and (not has_unit_layout(course) or record_unit_id(course, existing) == unit["unit_id"])
        ):
            raise ValueError(f"Figure asset already registered by {existing_key}; refusing collision: {asset_rel}")
    record = {
        "id": key,
        "unit_id": unit["unit_id"],
        "unit": unit.get("label") or unit_value,
        "concepts": concepts or [],
        "kind": kind,
        "role": role,
        "description": description,
        "learner_focus": learner_focus or [],
        "asset": asset_rel,
        "asset_sha256": sha256(asset_path),
        "origin": "derived",
        "based_on": based_on,
    }
    if visual_treatment is not None:
        record["visual_treatment"] = visual_treatment.strip()
    if source_figure_id is not None:
        record["source_figure_id"] = source_figure_id.strip()
    if generation is not None:
        record["generation"] = dict(generation)
    figures[key] = record
    data["version"] = max(int(data.get("version", 1) or 1), 2)
    issues = registry_issues(course, data)
    if issues:
        figures.pop(key, None)
        raise ValueError(json.dumps({"ok": False, "issues": issues}, ensure_ascii=False))
    save_registry(course, data)
    return {"ok": True, "key": key, "record": record}


def cmd_register_derived(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    try:
        result = register_derived(
            course, args.id, args.unit, args.asset, args.description, args.based_on or [],
            concepts=args.concept or [], learner_focus=args.learner_focus or [],
            kind=args.kind, role=args.role, visual_treatment=args.visual_treatment,
            source_figure_id=args.source_figure_id,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))



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
    result = verify_registry(course)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Scan/render source visuals deterministically")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--course", required=True)
    p.add_argument("--unit", help="Stable unit id or label; omit to scan the whole course")
    p.add_argument("--write", action="store_true")
    p.set_defaults(func=cmd_scan)
    p = sub.add_parser("render-page")
    p.add_argument("--course", required=True)
    p.add_argument("--unit", help="Unit owning the source and output asset")
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
    p.add_argument("--visual-treatment", choices=sorted(VISUAL_TREATMENTS))
    p.add_argument("--source-figure-id")
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
