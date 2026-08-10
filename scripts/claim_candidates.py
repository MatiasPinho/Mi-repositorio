#!/usr/bin/env python3
"""Generate auditable claim candidates from high-signal transcript/PDF text.

This is deliberately a candidate extractor, not a truth engine. It never writes
directly to canonical `claims`. With --write it refreshes `claim_candidates` in
`academico/academic.json`; `/procesar` must semantically accept/reject candidates
before they can become canonical claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
from scripts.transcript_tools import SUPPORTED as TRANSCRIPT_EXTS, parse_file  # noqa: E402

DEFAULT_CASES = ROOT / "tests" / "fixtures" / "claim_candidates" / "cases.jsonl"
AUTO_ORIGIN = "automatic-claim-extraction-v1"
REVIEW_STATUSES = {"pending", "accepted", "rejected"}

ASSESSMENT_AFTER = re.compile(
    r"(?P<object>[^.!?\n]{2,100}?)\s+(?P<neg>no\s+)?entra(?:\s+en)?\s+(?:el\s+)?"
    r"(?P<assessment>(?:(?:primer|primero|segundo|tercer|tercero)\s+)?(?:parcial|final|examen))\b",
    re.I,
)
ASSESSMENT_BEFORE = re.compile(
    r"(?:para\s+|en\s+)?(?:el\s+)?"
    r"(?P<assessment>(?:(?:primer|primero|segundo|tercer|tercero)\s+)?(?:parcial|final|examen))"
    r"\s+(?P<neg>no\s+)?entra\s+(?P<object>[^.!?\n]{2,100})",
    re.I,
)
GRADE_RULE = re.compile(
    r"\b(?:se\s+)?(?P<verb>aprueba|promociona|regulariza)"
    r"(?:\s+la\s+materia)?\s+con\s+(?:un\s+)?(?P<grade>\d+(?:[.,]\d+)?)\b",
    re.I,
)
DEFINITION = re.compile(
    r"(?P<subject>[^.!?\n]{2,80}?)\s+se\s+define\s+como\s+(?P<definition>[^.!?\n]{3,220})",
    re.I,
)
CHANGE_SIGNAL = re.compile(
    r"\b(finalmente|a\s+partir\s+de\s+ahora|queda\s+sin\s+efecto|"
    r"se\s+modific[ao]|se\s+cambi[ao]|cambia\s+a|ahora\s+va\s+a\s+ser)\b",
    re.I,
)
DISCOURSE_PREFIX = re.compile(
    r"^(?:bueno|entonces|ahora|ojo|recuerden|atenci[oó]n)\s*[,;:.-]?\s+",
    re.I,
)
AMBIGUOUS_REFERENTS = {
    "esto", "eso", "aquello", "esta parte", "esa parte", "este tema", "ese tema",
    "lo anterior", "lo de antes", "lo que vimos",
}


def compact(text: str) -> str:
    return " ".join(str(text).strip().split())


def key_text(text: str) -> str:
    text = compact(text).lower()
    text = text.translate(str.maketrans("áéíóúüñ", "aeiouun"))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def clean_referent(text: str) -> str:
    text = DISCOURSE_PREFIX.sub("", compact(text))
    text = re.sub(r"^(?:la|el|los|las|una|un)\s+", "", text, flags=re.I)
    return text.strip(" ,;:-")


def is_ambiguous_referent(text: str) -> bool:
    return compact(text).lower() in AMBIGUOUS_REFERENTS or len(compact(text)) < 2


def canonical_assessment(text: str) -> str:
    value = key_text(text).replace("primero-", "primer-").replace("tercero-", "tercer-")
    return value or "assessment"


def number_value(text: str) -> int | float:
    value = float(text.replace(",", "."))
    return int(value) if value.is_integer() else value


def evidence_ref(source: str, locator: dict[str, Any]) -> str:
    if locator.get("timestamp"):
        return f"{source}#{locator['timestamp']}"
    if locator.get("page"):
        return f"{source}#page={locator['page']}"
    if locator.get("segment"):
        return f"{source}#segment={locator['segment']}"
    return source


def candidate_id(source: str, locator: dict[str, Any], kind: str, excerpt: str, hints: dict[str, Any]) -> str:
    payload = json.dumps(
        [source, locator, kind, compact(excerpt), hints],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "cand-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_candidate(
    *,
    kind: str,
    source: str,
    source_type: str,
    locator: dict[str, Any],
    excerpt: str,
    hints: dict[str, Any],
    semantic_ready: bool,
) -> dict[str, Any]:
    excerpt = compact(excerpt)
    return {
        "id": candidate_id(source, locator, kind, excerpt, hints),
        "origin": AUTO_ORIGIN,
        "review_status": "pending",
        "kind": kind,
        "semantic_ready": semantic_ready,
        "source_type_suggestion": source_type,
        "source": source,
        "evidence_ref": evidence_ref(source, locator),
        "locator": locator,
        "excerpt": excerpt,
        "hints": hints,
    }


def extract_candidates_from_text(
    text: str,
    *,
    source: str,
    source_type: str,
    locator: dict[str, Any],
) -> list[dict[str, Any]]:
    text = compact(text)
    if not text:
        return []

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    match = ASSESSMENT_AFTER.search(text) or ASSESSMENT_BEFORE.search(text)
    if match:
        referent = clean_referent(match.group("object"))
        assessment = canonical_assessment(match.group("assessment"))
        semantic_ready = not is_ambiguous_referent(referent)
        hints = {
            "domain": "assessment",
            "subject": assessment,
            "predicate": "includes",
            "object": referent if semantic_ready else "",
            "value": not bool(match.group("neg")),
        }
        row = build_candidate(
            kind="assessment-scope",
            source=source,
            source_type=source_type,
            locator=locator,
            excerpt=text,
            hints=hints,
            semantic_ready=semantic_ready,
        )
        rows.append(row)
        seen.add((row["kind"], json.dumps(hints, ensure_ascii=False, sort_keys=True)))

    match = GRADE_RULE.search(text)
    if match:
        verb = match.group("verb").lower()
        predicate = {
            "aprueba": "minimum-passing-grade",
            "promociona": "minimum-promotion-grade",
            "regulariza": "minimum-regularity-grade",
        }[verb]
        hints = {
            "domain": "assessment",
            "subject": "course",
            "predicate": predicate,
            "object": "",
            "value": number_value(match.group("grade")),
        }
        row = build_candidate(
            kind="grading-rule",
            source=source,
            source_type=source_type,
            locator=locator,
            excerpt=text,
            hints=hints,
            semantic_ready=True,
        )
        sig = (row["kind"], json.dumps(hints, ensure_ascii=False, sort_keys=True))
        if sig not in seen:
            rows.append(row)
            seen.add(sig)

    match = DEFINITION.search(text)
    if match:
        subject = clean_referent(match.group("subject"))
        definition = compact(match.group("definition"))
        semantic_ready = not is_ambiguous_referent(subject)
        hints = {
            "domain": "academic",
            "subject": subject if semantic_ready else "",
            "predicate": "definition",
            "object": "",
            "value": definition,
        }
        row = build_candidate(
            kind="definition",
            source=source,
            source_type=source_type,
            locator=locator,
            excerpt=text,
            hints=hints,
            semantic_ready=semantic_ready,
        )
        sig = (row["kind"], json.dumps(hints, ensure_ascii=False, sort_keys=True))
        if sig not in seen:
            rows.append(row)
            seen.add(sig)

    if CHANGE_SIGNAL.search(text):
        domain = "assessment" if re.search(r"\b(parcial|final|examen|nota|promoci[oó]n|regularidad)\b", text, re.I) else "administrative"
        hints = {
            "domain": domain,
            "subject": "",
            "predicate": "",
            "object": "",
            "value": None,
            "change_signal": True,
        }
        row = build_candidate(
            kind="change-signal",
            source=source,
            source_type=source_type,
            locator=locator,
            excerpt=text,
            hints=hints,
            semantic_ready=False,
        )
        sig = (row["kind"], json.dumps(hints, ensure_ascii=False, sort_keys=True))
        if sig not in seen:
            rows.append(row)

    return rows


def split_pdf_text(text: str) -> Iterable[str]:
    for part in re.split(r"(?<=[.!?])\s+|\n+", text.replace("\r", "\n")):
        value = compact(part)
        if value:
            yield value


def source_label(course: Path, path: Path) -> str:
    return path.relative_to(course / "fuentes").as_posix()


def transcript_candidates(course: Path, path: Path) -> list[dict[str, Any]]:
    source = source_label(course, path)
    rows: list[dict[str, Any]] = []
    for index, segment in enumerate(parse_file(path), 1):
        locator: dict[str, Any] = {"segment": index}
        if segment.get("start"):
            locator["timestamp"] = segment["start"]
        if segment.get("speaker"):
            locator["speaker"] = segment["speaker"]
        rows.extend(
            extract_candidates_from_text(
                segment.get("text", ""),
                source=source,
                source_type="teacher_transcript",
                locator=locator,
            )
        )
    return rows


def pdf_candidates(course: Path, path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import fitz  # type: ignore
    except Exception:
        return [], "pymupdf-unavailable"

    source = source_label(course, path)
    rows: list[dict[str, Any]] = []
    try:
        doc = fitz.open(path)
        try:
            if getattr(doc, "needs_pass", False):
                return [], "pdf-encrypted"
            for page_number, page in enumerate(doc, 1):
                for segment_index, text in enumerate(split_pdf_text(page.get_text("text")), 1):
                    rows.extend(
                        extract_candidates_from_text(
                            text,
                            source=source,
                            source_type="official_course_material",
                            locator={"page": page_number, "segment": segment_index},
                        )
                    )
        finally:
            doc.close()
    except Exception as exc:
        return [], f"pdf-unreadable:{type(exc).__name__}"
    return rows, None


def discover_sources(course: Path) -> list[Path]:
    fuentes = course / "fuentes"
    found: list[Path] = []
    transcripts = fuentes / "transcripciones"
    if transcripts.exists():
        found.extend(
            p for p in transcripts.rglob("*")
            if p.is_file() and p.suffix.lower() in TRANSCRIPT_EXTS
        )
    official = fuentes / "oficiales"
    if official.exists():
        found.extend(p for p in official.rglob("*.pdf") if p.is_file())
    return sorted(set(found))


def resolve_requested_sources(course: Path, values: list[str] | None) -> list[Path]:
    if not values:
        return discover_sources(course)
    sources: list[Path] = []
    for value in values:
        candidate = course / "fuentes" / value
        if not candidate.exists():
            candidate = course / value
        if not candidate.is_file():
            raise SystemExit(f"Source not found: {value}")
        if candidate.suffix.lower() not in TRANSCRIPT_EXTS | {".pdf"}:
            raise SystemExit(f"Unsupported claim source: {value}")
        sources.append(candidate)
    return sorted(set(sources))


def scan_course(course: Path, files: list[str] | None = None) -> dict[str, Any]:
    paths = resolve_requested_sources(course, files)
    candidates: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for path in paths:
        source = source_label(course, path)
        if path.suffix.lower() in TRANSCRIPT_EXTS:
            rows = transcript_candidates(course, path)
            error = None
        else:
            rows, error = pdf_candidates(course, path)
        candidates.extend(rows)
        source_rows.append({"source": source, "candidates": len(rows), "error": error})
    return {
        "version": 1,
        "origin": AUTO_ORIGIN,
        "course": course.name,
        "full_scan": not bool(files),
        "sources": source_rows,
        "candidates": candidates,
        "total": len(candidates),
        "semantic_ready": sum(1 for row in candidates if row["semantic_ready"]),
        "needs_semantic_review": sum(1 for row in candidates if not row["semantic_ready"]),
        "errors": [row for row in source_rows if row["error"]],
    }


def write_candidates(course: Path, result: dict[str, Any]) -> dict[str, Any]:
    academic_path = course / "academico" / "academic.json"
    data = json.loads(academic_path.read_text(encoding="utf-8"))
    existing = data.get("claim_candidates", [])
    if not isinstance(existing, list):
        existing = []
    old_by_id = {
        str(row.get("id")): row
        for row in existing
        if isinstance(row, dict) and row.get("id")
    }
    scanned_sources = {str(row["source"]) for row in result["sources"]}
    live_sources = {source_label(course, path) for path in discover_sources(course)}

    retained: list[dict[str, Any]] = []
    for row in existing:
        if not isinstance(row, dict):
            continue
        if row.get("origin") != AUTO_ORIGIN:
            retained.append(row)
            continue
        source = str(row.get("source") or "")
        if result["full_scan"]:
            if source not in live_sources:
                continue
            if source in scanned_sources:
                continue
            retained.append(row)
        elif source not in scanned_sources:
            retained.append(row)

    refreshed: list[dict[str, Any]] = []
    for row in result["candidates"]:
        previous = old_by_id.get(row["id"])
        if isinstance(previous, dict) and previous.get("review_status") in REVIEW_STATUSES:
            row = dict(row)
            row["review_status"] = previous["review_status"]
            if "review_notes" in previous:
                row["review_notes"] = previous["review_notes"]
        refreshed.append(row)

    data["claim_candidates"] = retained + refreshed
    academic_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = dict(result)
    report["written"] = len(refreshed)
    report["retained"] = len(retained)
    out = course / ".study" / "claim-candidates.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def iter_cases(path: Path):
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"claim candidate case at line {line_number} must be an object")
        yield line_number, case


def run_benchmark(cases_path: Path = DEFAULT_CASES) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for line_number, case in iter_cases(cases_path):
        case_id = str(case.get("id") or f"line-{line_number}")
        rows = extract_candidates_from_text(
            str(case.get("text", "")),
            source="fixture.txt",
            source_type="teacher_transcript",
            locator={"segment": 1, "timestamp": "00:00:01"},
        )
        problems: list[str] = []
        expected_count = case.get("expected_count")
        if expected_count is not None and len(rows) != expected_count:
            problems.append(f"count expected={expected_count} actual={len(rows)}")
        expected_kind = case.get("expected_kind")
        selected = next((row for row in rows if row["kind"] == expected_kind), None) if expected_kind else None
        if expected_kind and selected is None:
            problems.append(f"missing-kind:{expected_kind}")
        expected = case.get("expected", {})
        if selected is not None and isinstance(expected, dict):
            for key, value in expected.items():
                actual = selected.get(key)
                if key.startswith("hints."):
                    actual = selected.get("hints", {}).get(key.split(".", 1)[1])
                if actual != value:
                    problems.append(f"{key} expected={value!r} actual={actual!r}")
        results.append({"id": case_id, "ok": not problems, "issues": problems})
    passed = sum(1 for row in results if row["ok"])
    return {"ok": passed == len(results), "total": len(results), "passed": passed, "failed": len(results) - passed, "results": results}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan")
    scan.add_argument("--course", required=True)
    scan.add_argument("--file", action="append", help="Path relative to fuentes/; repeatable")
    scan.add_argument("--write", action="store_true")

    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "benchmark":
        result = run_benchmark(args.cases)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    course = resolve_course(args.course)
    result = scan_course(course, args.file)
    if args.write:
        result = write_candidates(course, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
