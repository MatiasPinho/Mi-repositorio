#!/usr/bin/env python3
"""Deterministic PDF health/text-layer probe.

The probe classifies structural PDF conditions only. It does not perform OCR and
never assigns academic relevance. Corrupt or locked PDFs are reported per-file
instead of aborting a batch scan.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402


def require_pymupdf():
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import pymupdf  # type: ignore
        return pymupdf
    except Exception as exc:
        raise SystemExit(
            "PDF diagnostics need PyMuPDF. Install it explicitly with: "
            f"{sys.executable} -m pip install -r requirements-visual.txt\n{exc}"
        )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def page_probe(page: Any, number: int) -> dict[str, Any]:
    images = page.get_images(full=True)
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    text = " ".join(page.get_text("text").split())
    words = page.get_text("words")
    has_text = bool(text)
    image_only = bool(images) and not has_text
    blank = not has_text and not images and not drawings
    return {
        "page": number,
        "rotation": int(page.rotation or 0),
        "width": round(float(page.rect.width), 1),
        "height": round(float(page.rect.height), 1),
        "text_chars": len(text),
        "words": len(words),
        "images": len(images),
        "drawings": len(drawings),
        "has_text_layer": has_text,
        "image_only": image_only,
        "likely_scanned": image_only,
        "blank": blank,
        "text_preview": text[:280],
    }


def probe_pdf(path: Path, relative: str | None = None) -> dict[str, Any]:
    """Return a machine-readable PDF diagnostic without leaking library chatter."""
    fitz = require_pymupdf()
    label = relative or path.name
    digest = sha256(path)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            doc = fitz.open(path)
            try:
                if getattr(doc, "needs_pass", False):
                    return {
                        "file": label,
                        "sha256": digest,
                        "ok": False,
                        "error": {"type": "encrypted", "message": "PDF requires a password"},
                        "pages": 0,
                        "page_metrics": [],
                    }
                metrics = [page_probe(page, idx) for idx, page in enumerate(doc, 1)]
            finally:
                doc.close()
    except Exception as exc:
        return {
            "file": label,
            "sha256": digest,
            "ok": False,
            "error": {"type": "unreadable", "message": str(exc)},
            "pages": 0,
            "page_metrics": [],
        }

    return {
        "file": label,
        "sha256": digest,
        "ok": True,
        "error": None,
        "pages": len(metrics),
        "text_pages": sum(1 for row in metrics if row["has_text_layer"]),
        "image_only_pages": sum(1 for row in metrics if row["image_only"]),
        "blank_pages": sum(1 for row in metrics if row["blank"]),
        "rotated_pages": sum(1 for row in metrics if row["rotation"] % 360 != 0),
        "page_metrics": metrics,
    }


def scan_course(course: Path) -> dict[str, Any]:
    official = course / "fuentes" / "oficiales"
    rows: list[dict[str, Any]] = []
    if official.exists():
        for path in sorted(official.rglob("*.pdf")):
            rel = path.relative_to(course / "fuentes").as_posix()
            rows.append(probe_pdf(path, rel))
    return {
        "version": 1,
        "files": rows,
        "total": len(rows),
        "healthy": sum(1 for row in rows if row["ok"]),
        "unreadable": sum(1 for row in rows if not row["ok"]),
        "needs_attention": [row["file"] for row in rows if (not row["ok"] or row.get("image_only_pages", 0) > 0)],
        "note": "likely_scanned means image-only without an extractable text layer; no OCR is performed.",
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("probe", help="Probe one PDF path")
    one.add_argument("file", type=Path)
    scan = sub.add_parser("scan", help="Probe official PDFs in one course")
    scan.add_argument("--course", required=True)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "probe":
        result = probe_pdf(args.file.resolve(), args.file.name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    course = resolve_course(args.course)
    result = scan_course(course)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
