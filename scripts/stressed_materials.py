#!/usr/bin/env python3
"""Deterministic adversarial benchmark for study-material ingestion boundaries."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "stressed_materials" / "cases.jsonl"

import sys
sys.path.insert(0, str(ROOT))

from study import scan_materials  # noqa: E402
from scripts.transcript_tools import inspect as inspect_transcript  # noqa: E402


def iter_cases(path: Path):
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"stress case at line {line_number} must be an object")
        yield line_number, case


def make_course(base: Path) -> Path:
    course = base / "course"
    (course / "fuentes").mkdir(parents=True)
    return course


def write_file(course: Path, spec: dict[str, Any]) -> Path:
    path = course / "fuentes" / str(spec["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = str(spec.get("encoding", "utf-8"))
    text = str(spec.get("text", ""))
    path.write_bytes(text.encode(encoding))
    return path


def commit_index(course: Path, current: dict[str, Any]) -> None:
    target = course / ".study" / "materials-index.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"files": current}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_mutations(course: Path, mutations: list[dict[str, Any]]) -> None:
    base = course / "fuentes"
    for mutation in mutations:
        op = mutation.get("op")
        if op == "write":
            write_file(course, mutation)
        elif op == "rename":
            src = base / str(mutation["from"])
            dst = base / str(mutation["to"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
        elif op == "delete":
            (base / str(mutation["path"])).unlink()
        elif op == "touch":
            os.utime(base / str(mutation["path"]), None)
        else:
            raise ValueError(f"unsupported stress mutation: {op}")


def compare_scan(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key in ("added", "changed", "removed"):
        if actual.get(key) != expected.get(key):
            issues.append(f"{key}: expected={expected.get(key)!r} actual={actual.get(key)!r}")
    if actual.get("total") != expected.get("total"):
        issues.append(f"total: expected={expected.get('total')!r} actual={actual.get('total')!r}")
    return issues


def run_scan_case(case: dict[str, Any], lifecycle: bool) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        course = make_course(Path(td))
        for spec in case.get("files", []):
            write_file(course, spec)

        if lifecycle:
            current, _ = scan_materials(course)
            commit_index(course, current)
            apply_mutations(course, case.get("mutations", []))

        _, diff = scan_materials(course)
        return compare_scan(diff, case["expected"])


def run_transcript_case(case: dict[str, Any]) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        course = make_course(Path(td))
        path = write_file(course, case["file"])
        row = inspect_transcript(path, course)
        expected = case["expected"]
        issues: list[str] = []

        for key in ("segments", "timestamped_segments"):
            if row.get(key) != expected.get(key):
                issues.append(f"{key}: expected={expected.get(key)!r} actual={row.get(key)!r}")

        cue_types = {
            cue_type
            for cue in row.get("cue_candidates", [])
            for cue_type in cue.get("cue_types", [])
        }
        for cue_type in expected.get("cue_types_contains", []):
            if cue_type not in cue_types:
                issues.append(f"missing-cue-type:{cue_type}")

        texts = [str(cue.get("text", "")) for cue in row.get("cue_candidates", [])]
        for needle in expected.get("text_contains", []):
            if not any(str(needle).lower() in text.lower() for text in texts):
                issues.append(f"missing-text:{needle}")

        speaker = expected.get("speaker_contains")
        if speaker is not None:
            speakers = [str(cue.get("speaker") or "") for cue in row.get("cue_candidates", [])]
            if not any(str(speaker) in value for value in speakers):
                issues.append(f"missing-speaker:{speaker}")
        return issues


def run_case(case: dict[str, Any]) -> list[str]:
    kind = case.get("kind")
    if kind == "scan":
        return run_scan_case(case, lifecycle=False)
    if kind == "scan-lifecycle":
        return run_scan_case(case, lifecycle=True)
    if kind == "transcript":
        return run_transcript_case(case)
    return [f"unknown-kind:{kind}"]


def run_benchmark(cases_path: Path = DEFAULT_CASES) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for line_number, case in iter_cases(cases_path):
        case_id = str(case.get("id") or f"line-{line_number}")
        try:
            issues = run_case(case)
        except Exception as exc:  # benchmark should report crashes as failures
            issues = [f"exception:{type(exc).__name__}:{exc}"]
        results.append({"id": case_id, "ok": not issues, "issues": issues})
    passed = sum(1 for item in results if item["ok"])
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
        raise SystemExit(f"unknown stress case: {args.id}")
    issues = run_case(selected)
    result = {"id": args.id, "ok": not issues, "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
