#!/usr/bin/env python3
"""Deterministic run contract for the persistent browser quiz action.

Quiz uses the shared pipeline-run snapshot/engine machinery but has JSON-specific
review/publication stages instead of the Markdown staged-artifact contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts import pipeline_run as shared
from scripts.course_layout import LayoutError, unit_root

REQUIRED_REVIEW_CHECKS = (
    "canonical_fidelity",
    "single_best_answer",
    "distractor_quality",
    "no_answer_cues",
    "feedback_quality",
    "topic_coverage",
)


def _validate_review(run: Path, errors: list[str]) -> None:
    candidate = run / "02-quiz.json"
    review_path = run / "03-review.json"
    final = run / "04-final.json"
    for path in (candidate, review_path, final):
        if not path.is_file():
            errors.append(f"missing-{path.name}")
    if errors:
        return
    try:
        review = shared.load(review_path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("quiz-review-invalid-json")
        return
    if not isinstance(review, dict):
        errors.append("quiz-review-invalid")
        return
    candidate_hash = shared.sha(candidate)
    if review.get("candidate_sha256") != candidate_hash:
        errors.append("quiz-review-candidate-hash-mismatch")
    if review.get("pass") is not True:
        errors.append("quiz-review-failed")
    issues = review.get("issues")
    if not isinstance(issues, list) or issues:
        errors.append("quiz-review-issues-present")
    checks = review.get("checks")
    if not isinstance(checks, dict):
        errors.append("quiz-review-checks-missing")
    else:
        for name in REQUIRED_REVIEW_CHECKS:
            if checks.get(name) is not True:
                errors.append(f"quiz-review-check-failed:{name}")
    if shared.sha(final) != candidate_hash:
        errors.append("quiz-final-not-reviewed-candidate")


def _validate_integrity(run: Path, errors: list[str]) -> None:
    path = run / "10-integrity.json"
    if not path.is_file():
        errors.append("missing-10-integrity.json")
        return
    try:
        payload = shared.load(path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("quiz-integrity-invalid-json")
        return
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        errors.append("quiz-integrity-failed")
        return
    if payload.get("source_sha256") != shared.sha(run / "04-final.json"):
        errors.append("quiz-integrity-json-hash-mismatch")
    if payload.get("html_sha256") != shared.sha(run / "09-rendered.html"):
        errors.append("quiz-integrity-html-hash-mismatch")


def _validate_publication(run: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    report_path = run / "11-publication.json"
    if not report_path.is_file():
        errors.append("missing-11-publication.json")
        return
    try:
        report = shared.load(report_path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("quiz-publication-invalid-json")
        return
    if not isinstance(report, dict) or report.get("ok") is not True:
        errors.append("quiz-publication-failed")
        return
    rows = report.get("files")
    if not isinstance(rows, list):
        errors.append("quiz-publication-files-missing")
        return
    by_role = {
        row.get("role"): row
        for row in rows
        if isinstance(row, dict) and row.get("role")
    }
    if set(by_role) != {"json", "html"}:
        errors.append("quiz-publication-roles-invalid")
        return

    course_rel = str(manifest.get("course", "")).strip()
    course = (shared.ROOT / course_rel).resolve() if course_rel else None
    if not course or not course.is_dir():
        errors.append("quiz-publication-course-invalid")
        return
    run_input = shared.load(run / "01-input.json", {})
    unit_id = str(run_input.get("unit_id", "")).strip() if isinstance(run_input, dict) else ""
    if not unit_id:
        errors.append("quiz-publication-unit-missing")
        return
    try:
        root = unit_root(course, unit_id).resolve()
    except LayoutError:
        errors.append(f"quiz-publication-unit-invalid:{unit_id}")
        return

    expected = {
        "json": (
            (run / "04-final.json").resolve(),
            (root / "preguntas" / "_source" / f"{unit_id}-quiz.json").resolve(),
        ),
        "html": (
            (run / "09-rendered.html").resolve(),
            (root / "preguntas" / f"{unit_id}-quiz.html").resolve(),
        ),
    }
    for role, (expected_source, expected_destination) in expected.items():
        row = by_role[role]
        source = shared._resolve_repo_path(row.get("source", ""))
        destination = shared._resolve_repo_path(row.get("destination", ""))
        if source != expected_source:
            errors.append(f"quiz-publication-source-invalid:{role}")
        if destination != expected_destination:
            errors.append(f"quiz-publication-destination-invalid:{role}")
        if not source.is_file() or not destination.is_file():
            errors.append(f"quiz-publication-file-missing:{role}")
            continue
        source_hash = shared.sha(source)
        destination_hash = shared.sha(destination)
        if row.get("source_sha256") != source_hash:
            errors.append(f"quiz-publication-source-mutated:{role}")
        if row.get("published_sha256") != destination_hash or row.get("destination_sha256") != destination_hash:
            errors.append(f"quiz-publication-hash-mismatch:{role}")
        if source_hash != destination_hash or row.get("transform") != "identity":
            errors.append(f"quiz-publication-not-identity:{role}")
        if row.get("source_bytes") != source.stat().st_size or row.get("bytes") != destination.stat().st_size:
            errors.append(f"quiz-publication-size-mismatch:{role}")


def validate_quiz_run(run: Path) -> dict[str, Any]:
    manifest = shared.load(run / "manifest.json", {})
    errors: list[str] = []
    if manifest.get("pipeline") != "quiz":
        errors.append("quiz-run-wrong-pipeline")
        return {"ok": False, "pipeline": manifest.get("pipeline"), "errors": errors}

    rendered = run / "09-rendered.html"
    if not rendered.is_file():
        errors.append("missing-09-rendered.html")
    elif not rendered.read_text(encoding="utf-8").strip():
        errors.append("quiz-rendered-empty")

    _validate_review(run, errors)
    _validate_integrity(run, errors)
    shared._validate_canonical_snapshot(run, errors)
    shared._validate_visual_audit(run, errors)
    _validate_publication(run, manifest, errors)
    shared._validate_engine_snapshot(manifest, errors)

    course_rel = str(manifest.get("course", "")).strip()
    course = (shared.ROOT / course_rel).resolve() if course_rel else None
    if course and course.is_dir():
        before = set(manifest.get("course_script_snapshot", []))
        after = set(shared.course_script_snapshot(course))
        for rel in sorted(after - before):
            errors.append(f"unexpected-course-script:{rel}")

    return {"ok": not errors, "pipeline": "quiz", "errors": errors}


def cmd_start(args: argparse.Namespace) -> None:
    shared.cmd_start(
        SimpleNamespace(
            course=args.course,
            pipeline="quiz",
            scope=args.unit,
            executor=args.executor,
        )
    )


def cmd_validate(args: argparse.Namespace) -> None:
    run = shared.resolve_run(args.run)
    result = validate_quiz_run(run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


def cmd_finish(args: argparse.Namespace) -> None:
    run = shared.resolve_run(args.run)
    result = validate_quiz_run(run)
    if not result["ok"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    manifest = shared.load(run / "manifest.json", {})
    manifest["status"] = "finished"
    manifest["finished_at"] = shared.now()
    manifest["stages"] = {
        p.name: "present"
        for p in sorted(run.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    for rel in (
        "visual-audit/audit.json",
        "visual-audit/desktop.png",
        "visual-audit/mobile.png",
        "11-publication.json",
    ):
        manifest["stages"][rel] = "present"
    shared.save(run / "manifest.json", manifest)
    print(json.dumps({"ok": True, "run": run.relative_to(shared.ROOT).as_posix()}, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description="Persistent browser-quiz run manager")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start")
    p.add_argument("--course", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--executor", choices=["portable", "claude", "codex"], default="portable")
    p.set_defaults(func=cmd_start)

    for name, func in (("validate", cmd_validate), ("finish", cmd_finish)):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        p.set_defaults(func=func)

    args = ap.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
