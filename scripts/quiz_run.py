#!/usr/bin/env python3
"""Deterministic run contract for the persistent browser quiz action.

Quiz uses the shared pipeline-run snapshot/engine machinery but has JSON-specific
review/publication stages instead of the Markdown staged-artifact contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import pipeline_run as shared  # noqa: E402
from scripts.course_layout import LayoutError, unit_root  # noqa: E402

REQUIRED_REVIEW_CHECKS = (
    "canonical_fidelity",
    "single_best_answer",
    "distractor_quality",
    "no_answer_cues",
    "feedback_quality",
    "topic_coverage",
)
INTERACTION_SCREENSHOTS = {
    "practice_feedback": "practice-feedback.png",
    "exam_question_mobile": "exam-question-mobile.png",
    "exam_result_mobile": "exam-result-mobile.png",
}


def _load_review(path: Path, errors: list[str], label: str) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"missing-{path.name}")
        return None
    try:
        payload = shared.load(path, {})
    except (json.JSONDecodeError, OSError):
        errors.append(f"{label}-invalid-json")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label}-invalid")
        return None
    return payload


def _validate_review_binding(
    review: dict[str, Any],
    candidate: Path,
    errors: list[str],
    *,
    label: str,
    require_pass: bool,
) -> None:
    if not candidate.is_file():
        errors.append(f"missing-{candidate.name}")
        return
    if review.get("candidate_sha256") != shared.sha(candidate):
        errors.append(f"{label}-candidate-hash-mismatch")

    passed = review.get("pass") is True
    if require_pass and not passed:
        errors.append(f"{label}-failed")
    if not require_pass and passed:
        errors.append(f"{label}-expected-failure")

    issues = review.get("issues")
    if not isinstance(issues, list):
        errors.append(f"{label}-issues-invalid")
    elif require_pass and issues:
        errors.append(f"{label}-issues-present")
    elif not require_pass and not issues:
        errors.append(f"{label}-failed-without-issues")

    checks = review.get("checks")
    if not isinstance(checks, dict):
        errors.append(f"{label}-checks-missing")
        return
    seen_false = False
    for name in REQUIRED_REVIEW_CHECKS:
        value = checks.get(name)
        if not isinstance(value, bool):
            errors.append(f"{label}-check-invalid:{name}")
        elif require_pass and value is not True:
            errors.append(f"{label}-check-failed:{name}")
        elif value is False:
            seen_false = True
    if not require_pass and not seen_false:
        errors.append(f"{label}-failed-without-failed-check")


def _accepted_json(run: Path) -> Path:
    first_review = run / "03-review.json"
    if first_review.is_file():
        try:
            payload = shared.load(first_review, {})
        except (json.JSONDecodeError, OSError):
            payload = {}
        if isinstance(payload, dict) and payload.get("pass") is True:
            return run / "04-final.json"
    return run / "06-final.json"


def _validate_review(run: Path, errors: list[str]) -> None:
    candidate = run / "02-quiz.json"
    if not candidate.is_file():
        errors.append("missing-02-quiz.json")
        return
    first = _load_review(run / "03-review.json", errors, "quiz-review-1")
    if first is None:
        return

    if first.get("pass") is True:
        _validate_review_binding(first, candidate, errors, label="quiz-review-1", require_pass=True)
        final = run / "04-final.json"
        if not final.is_file():
            errors.append("missing-04-final.json")
        elif shared.sha(final) != shared.sha(candidate):
            errors.append("quiz-final-not-reviewed-candidate")
        for unexpected in ("04-repair.json", "05-review.json", "06-final.json"):
            if (run / unexpected).exists():
                errors.append(f"quiz-unexpected-repair-after-pass:{unexpected}")
        return

    _validate_review_binding(first, candidate, errors, label="quiz-review-1", require_pass=False)
    repair = run / "04-repair.json"
    second = _load_review(run / "05-review.json", errors, "quiz-review-2")
    final = run / "06-final.json"
    if not repair.is_file():
        errors.append("missing-04-repair.json")
    if second is not None and repair.is_file():
        _validate_review_binding(second, repair, errors, label="quiz-review-2", require_pass=True)
    if not final.is_file():
        errors.append("missing-06-final.json")
    elif repair.is_file() and shared.sha(final) != shared.sha(repair):
        errors.append("quiz-final-not-reviewed-repair")
    if (run / "04-final.json").exists():
        errors.append("quiz-first-pass-final-present-after-failed-review")
    for forbidden in ("07-review.json", "07-repair.json", "08-final.json"):
        if (run / forbidden).exists():
            errors.append(f"quiz-third-review-cycle-forbidden:{forbidden}")


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
    accepted = _accepted_json(run)
    if payload.get("source_sha256") != shared.sha(accepted):
        errors.append("quiz-integrity-json-hash-mismatch")
    if payload.get("html_sha256") != shared.sha(run / "09-rendered.html"):
        errors.append("quiz-integrity-html-hash-mismatch")


def _validate_interaction(run: Path, errors: list[str]) -> None:
    path = run / "10-interaction.json"
    if not path.is_file():
        errors.append("missing-10-interaction.json")
        return
    try:
        payload = shared.load(path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("quiz-interaction-invalid-json")
        return
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        errors.append("quiz-interaction-failed")
        return
    if payload.get("engine") != "playwright-chromium":
        errors.append("quiz-interaction-wrong-engine")
    accepted = _accepted_json(run)
    if payload.get("source_sha256") != shared.sha(accepted):
        errors.append("quiz-interaction-json-hash-mismatch")
    if payload.get("html_sha256") != shared.sha(run / "09-rendered.html"):
        errors.append("quiz-interaction-html-hash-mismatch")
    modes = payload.get("modes")
    if not isinstance(modes, dict):
        errors.append("quiz-interaction-modes-missing")
    else:
        for mode in ("practice", "exam"):
            row = modes.get(mode)
            if not isinstance(row, dict) or row.get("ok") is not True:
                errors.append(f"quiz-interaction-mode-failed:{mode}")

    screenshots = payload.get("screenshots")
    if not isinstance(screenshots, dict):
        errors.append("quiz-interaction-screenshots-missing")
        return
    audit_root = (run / "interaction-audit").resolve()
    for key, filename in INTERACTION_SCREENSHOTS.items():
        expected = (audit_root / filename).resolve()
        raw = str(screenshots.get(key, "")).strip()
        if not raw:
            errors.append(f"quiz-interaction-screenshot-report-missing:{key}")
            continue
        reported = Path(raw).resolve()
        if reported != expected:
            errors.append(f"quiz-interaction-screenshot-path-invalid:{key}")
        if not expected.is_file() or expected.stat().st_size <= 0:
            errors.append(f"quiz-interaction-screenshot-missing:{key}")


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
            _accepted_json(run).resolve(),
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
    _validate_interaction(run, errors)
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
        "10-interaction.json",
        "interaction-audit/practice-feedback.png",
        "interaction-audit/exam-question-mobile.png",
        "interaction-audit/exam-result-mobile.png",
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
