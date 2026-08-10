#!/usr/bin/env python3
"""Generate adversarial PDFs and verify deterministic probe behavior."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "pdf_stress" / "cases.jsonl"

import sys
sys.path.insert(0, str(ROOT))

from scripts.pdf_probe import probe_pdf, require_pymupdf, scan_course  # noqa: E402


def iter_cases(path: Path):
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"PDF stress case at line {line_number} must be an object")
        yield line_number, case


def _new_doc(path: Path, builder) -> None:
    fitz = require_pymupdf()
    doc = fitz.open()
    try:
        builder(fitz, doc)
        doc.save(path)
    finally:
        doc.close()


def make_pdf(path: Path, kind: str) -> None:
    fitz = require_pymupdf()
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "corrupt":
        path.write_bytes(b"%PDF-1.7\nthis is intentionally truncated and invalid\n")
        return

    if kind == "encrypted":
        doc = fitz.open()
        try:
            page = doc.new_page()
            page.insert_text((72, 72), "Protected academic material")
            doc.save(
                path,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="owner-secret",
                user_pw="student-secret",
            )
        finally:
            doc.close()
        return

    def build_text(_fitz, doc):
        page = doc.new_page()
        page.insert_text((72, 72), "Programming concepts and deterministic PDF text layer")

    def build_image_only(_fitz, doc):
        page = doc.new_page()
        pix = _fitz.Pixmap(_fitz.csRGB, _fitz.IRect(0, 0, 32, 32), False)
        pix.clear_with(190)
        page.insert_image(_fitz.Rect(80, 80, 400, 500), pixmap=pix)

    def build_rotated(_fitz, doc):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "Rotated page keeps its text layer")
        page.set_rotation(90)

    def build_table(_fitz, doc):
        page = doc.new_page()
        x0, y0, cell_w, cell_h = 80, 100, 120, 40
        for row in range(4):
            y = y0 + row * cell_h
            page.draw_line((x0, y), (x0 + 2 * cell_w, y))
        for col in range(3):
            x = x0 + col * cell_w
            page.draw_line((x, y0), (x, y0 + 3 * cell_h))
        page.insert_text((95, 125), "Concept")
        page.insert_text((215, 125), "Value")
        page.insert_text((95, 165), "Array")
        page.insert_text((215, 165), "Indexed")

    def build_blank(_fitz, doc):
        doc.new_page()

    def build_multipage(_fitz, doc):
        p1 = doc.new_page()
        p1.insert_text((72, 72), "Page one has text")
        doc.new_page()
        p3 = doc.new_page(width=595, height=842)
        p3.insert_text((72, 72), "Page three is rotated")
        p3.set_rotation(90)

    builders = {
        "text": build_text,
        "image-only": build_image_only,
        "rotated": build_rotated,
        "table": build_table,
        "blank": build_blank,
        "multipage": build_multipage,
    }
    builder = builders.get(kind)
    if builder is None:
        raise ValueError(f"unsupported PDF generator kind: {kind}")
    _new_doc(path, builder)


def compare_result(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in expected.items():
        if key == "error_type":
            actual_value = (actual.get("error") or {}).get("type")
        elif key == "needs_attention_contains":
            if value not in actual.get("needs_attention", []):
                issues.append(f"needs_attention missing {value!r}")
            continue
        else:
            actual_value = actual.get(key)
        if actual_value != value:
            issues.append(f"{key}: expected={value!r} actual={actual_value!r}")
    return issues


def compare_page(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in expected.items():
        if key.endswith("_min"):
            actual_key = key[:-4]
            actual_value = actual.get(actual_key, 0)
            if actual_value < value:
                issues.append(f"{actual_key}: expected>={value!r} actual={actual_value!r}")
        elif actual.get(key) != value:
            issues.append(f"{key}: expected={value!r} actual={actual.get(key)!r}")
    return issues


def run_single_case(case: dict[str, Any]) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / str(case["filename"])
        make_pdf(path, str(case["kind"]))
        result = probe_pdf(path, str(case["filename"]))
        issues = compare_result(result, case["expected"])
        page_expected = case.get("page_expected")
        if page_expected:
            metrics = result.get("page_metrics", [])
            if not metrics:
                issues.append("missing-page-metrics")
            else:
                issues.extend(compare_page(metrics[0], page_expected))
        return issues


def run_batch_case(case: dict[str, Any]) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        course = Path(td) / "course"
        official = course / "fuentes" / "oficiales"
        official.mkdir(parents=True)
        make_pdf(official / "bueno.pdf", "text")
        make_pdf(official / "corrupto.pdf", "corrupt")
        result = scan_course(course)
        return compare_result(result, case["expected"])


def run_case(case: dict[str, Any]) -> list[str]:
    if case.get("kind") == "batch":
        return run_batch_case(case)
    return run_single_case(case)


def run_benchmark(cases_path: Path = DEFAULT_CASES) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for line_number, case in iter_cases(cases_path):
        case_id = str(case.get("id") or f"line-{line_number}")
        try:
            issues = run_case(case)
        except Exception as exc:
            issues = [f"exception:{type(exc).__name__}:{exc}"]
        results.append({"id": case_id, "ok": not issues, "issues": issues})
    passed = sum(1 for row in results if row["ok"])
    return {
        "ok": passed == len(results),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("benchmark")
    one = sub.add_parser("case")
    one.add_argument("--id", required=True)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "benchmark":
        result = run_benchmark(args.cases)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    selected = None
    for _, case in iter_cases(args.cases):
        if case.get("id") == args.id:
            selected = case
            break
    if selected is None:
        raise SystemExit(f"unknown PDF stress case: {args.id}")
    issues = run_case(selected)
    result = {"id": args.id, "ok": not issues, "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
