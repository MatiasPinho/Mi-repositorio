#!/usr/bin/env python3
"""Hard runtime guard for the active hybrid ``/resumen`` pipeline.

This module closes the gaps discovered in the portable-model benchmark without
relying on agent obedience:

- warns early when optional Cloudflare illustration credentials are missing;
- validates and locks the semantic/visual plan before materialization;
- permits at most one narrowly-scoped provider fallback;
- preserves unit figure-registry root metadata while allowing planned derived
  figures to be appended;
- renders run-local candidates with deterministic unit-relative image rebasing,
  so no symlinks or repo-root ``assets/`` workarounds are needed;
- binds academic reviews to immutable candidate handoffs and records whether the
  reviewer was actually isolated or merely portable-handoff mode;
- makes ``finished`` an effective, revalidated state backed by an attestation.

The legacy engines remain importable for compatibility.  The active hybrid
summary pipeline must use this guard for PLAN validation, visual build, render,
review validation, status and finish.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
from scripts import pipeline_run, render_study, visual_plan_hybrid  # noqa: E402
from scripts.academic_eval import evaluate_review  # noqa: E402
from scripts.course_layout import has_unit_layout, registry_path, unit_root  # noqa: E402
from scripts.illustration_figure import MODEL as ILLUSTRATION_MODEL  # noqa: E402
from scripts.illustration_figure import _credential as illustration_credential  # noqa: E402
from scripts.unit_identity import resolve_unit  # noqa: E402

LOCK_NAME = "02-plan-lock.json"
BUILD_NAME = "02-visual-build.json"
FINISH_NAME = "13-finish.json"
SELECTED_NEEDS = {"visual_required", "visual_helpful"}
LOCAL_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")


class GuardError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _run(value: str) -> Path:
    return pipeline_run.resolve_run(value)


def _repo_path(value: Any) -> Path:
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _context(run: Path) -> tuple[Path, str, Path]:
    inp = load(run / "01-input.json", {})
    if not isinstance(inp, dict):
        raise GuardError("01-input.json is missing or invalid")
    course_rel = str(inp.get("course") or "").strip()
    unit_id = str(inp.get("unit_id") or "").strip()
    if not course_rel or not unit_id:
        raise GuardError("01-input.json must contain course and stable unit_id")
    course = (ROOT / course_rel).resolve()
    if not course.is_dir():
        raise GuardError(f"course directory does not exist: {course_rel}")
    base = unit_root(course, unit_id) if has_unit_layout(course) else course
    return course, unit_id, base


def _plan(run: Path) -> tuple[Path, dict[str, Any]]:
    path = run / "02-plan.json"
    data = load(path, {})
    if not path.is_file() or not isinstance(data, dict):
        raise GuardError("02-plan.json is missing or invalid")
    return path, data


def _visual_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("visuals", [])
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        raise GuardError("02-plan.json visuals must be an array or object")
    return [row for row in raw if isinstance(row, dict)]


def _selected_treatments(run: Path) -> dict[str, str]:
    """Correct planned-derived set: omitted visuals are not selected figures."""
    _path, plan = _plan(run)
    result: dict[str, str] = {}
    for row in _visual_rows(plan):
        if str(row.get("need") or "").strip() not in SELECTED_NEEDS:
            continue
        treatment = str(row.get("visual_treatment") or "").strip()
        if treatment not in {"reinterpret", "preserve+derived_sketch"}:
            continue
        figure_id = str(row.get("derived_figure_id") or "").strip()
        if not figure_id:
            continue
        key = figure_id if figure_id.startswith("derived:") else f"derived:{figure_id}"
        result[key] = treatment
    return result


def _canonical_concept_ids(run: Path) -> set[str]:
    inp = load(run / "01-input.json", {})
    path = _repo_path(inp.get("concepts_file", "")) if isinstance(inp, dict) else Path()
    data = load(path, {})
    rows = data.get("concepts", {}) if isinstance(data, dict) else {}
    return {str(key).strip() for key in rows if str(key).strip()} if isinstance(rows, dict) else set()


def _canonical_topic_ids(run: Path) -> set[str]:
    inp = load(run / "01-input.json", {})
    path = _repo_path(inp.get("topics_file", "")) if isinstance(inp, dict) else Path()
    data = load(path, {})
    rows = data.get("topics", {}) if isinstance(data, dict) else {}
    return {str(key).strip() for key in rows if str(key).strip()} if isinstance(rows, dict) else set()


def _plan_coverage_issues(run: Path, plan: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    canonical_concepts = _canonical_concept_ids(run)
    assigned: set[str] = set()
    order = plan.get("concept_order", [])
    if not isinstance(order, list):
        issues.append("plan-concept-order-invalid")
        order = []
    for section in order:
        if not isinstance(section, dict):
            continue
        concepts = section.get("concepts", [])
        if isinstance(concepts, list):
            assigned.update(str(value).strip() for value in concepts if str(value).strip())
    unassigned = plan.get("unassigned_concepts", [])
    if not isinstance(unassigned, list):
        issues.append("plan-unassigned-concepts-invalid")
        unassigned = []
    for concept_id in sorted(str(value).strip() for value in unassigned if str(value).strip()):
        issues.append(f"plan-unassigned-concept:{concept_id}")
    for concept_id in sorted(canonical_concepts - assigned):
        issues.append(f"plan-canonical-concept-missing:{concept_id}")
    for concept_id in sorted(assigned - canonical_concepts):
        issues.append(f"plan-unknown-concept:{concept_id}")

    canonical_topics = _canonical_topic_ids(run)
    coverage = plan.get("topic_coverage", {})
    if not isinstance(coverage, dict):
        issues.append("plan-topic-coverage-invalid")
        coverage = {}
    covered_topics = {str(key).strip() for key in coverage if str(key).strip()}
    for topic_id in sorted(canonical_topics - covered_topics):
        issues.append(f"plan-topic-missing:{topic_id}")
    return issues


def _spec_hashes(run: Path, plan: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in _visual_rows(plan):
        if str(row.get("need") or "").strip() not in SELECTED_NEEDS:
            continue
        if str(row.get("visual_medium") or "diagram").strip() != "diagram":
            continue
        spec_value = str(row.get("sketch_spec") or "").strip()
        if not spec_value:
            continue
        path = (run / spec_value).resolve()
        if not path.is_relative_to((run / "02-sketches").resolve()) or not path.is_file():
            raise GuardError(f"invalid or missing sketch spec: {spec_value}")
        digest = sha(path)
        if not digest:
            raise GuardError(f"cannot hash sketch spec: {spec_value}")
        result[spec_value] = digest
    return dict(sorted(result.items()))


def _lock_payload(run: Path, *, fallback_used: bool = False, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    plan_path, plan = _plan(run)
    return {
        "version": 1,
        "plan_sha256": sha(plan_path),
        "sketch_specs": _spec_hashes(run, plan),
        "fallback_used": bool(fallback_used),
        "fallback": fallback,
        "locked_at": now(),
    }


def _check_lock(run: Path) -> dict[str, Any]:
    lock_path = run / LOCK_NAME
    lock = load(lock_path, {})
    if not isinstance(lock, dict) or not lock_path.is_file():
        raise GuardError(f"{LOCK_NAME} is missing; run validate-plan first")
    plan_path, plan = _plan(run)
    if lock.get("plan_sha256") != sha(plan_path):
        raise GuardError("02-plan.json changed after plan lock")
    if lock.get("sketch_specs") != _spec_hashes(run, plan):
        raise GuardError("one or more sketch specs changed after plan lock")
    return lock


def cmd_preflight(args: argparse.Namespace) -> None:
    # Resolve the course early too: a typo should fail before a 20-minute run.
    resolve_course(args.course)
    account = illustration_credential("CLOUDFLARE_ACCOUNT_ID")
    token = illustration_credential("CLOUDFLARE_API_TOKEN")
    missing = [
        name
        for name, value in (
            ("CLOUDFLARE_ACCOUNT_ID", account),
            ("CLOUDFLARE_API_TOKEN", token),
        )
        if not value
    ]
    print(json.dumps({
        "ok": True,
        "cloudflare_illustrations": {
            "available": not missing,
            "blocking": False,
            "model": ILLUSTRATION_MODEL,
            "missing": missing,
            "message": (
                "Cloudflare illustrations are ready."
                if not missing
                else "Optional Cloudflare illustrations are unavailable; deterministic diagrams and text remain available."
            ),
        },
    }, ensure_ascii=False, indent=2))


def cmd_validate_plan(args: argparse.Namespace) -> None:
    run = _run(args.run)
    course, unit_id, _base = _context(run)
    plan_path, plan = _plan(run)
    issues = _plan_coverage_issues(run, plan)
    try:
        selected = visual_plan_hybrid.inspect_plan(course, unit_id, plan_path)
    except Exception as exc:  # contract validators use ValueError/SystemExit subclasses
        raise GuardError(f"hybrid visual plan invalid: {exc}") from exc
    if issues:
        print(json.dumps({"ok": False, "issues": issues}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    lock_path = run / LOCK_NAME
    new_lock = _lock_payload(run)
    if lock_path.is_file():
        existing = load(lock_path, {})
        stable_existing = {k: v for k, v in existing.items() if k != "locked_at"} if isinstance(existing, dict) else {}
        stable_new = {k: v for k, v in new_lock.items() if k != "locked_at"}
        if stable_existing != stable_new:
            raise GuardError("plan lock already exists with different content; arbitrary re-locking is forbidden")
    else:
        save(lock_path, new_lock)
    print(json.dumps({
        "ok": True,
        "plan_sha256": new_lock["plan_sha256"],
        "selected_visuals": len(selected),
        "canonical_concepts": len(_canonical_concept_ids(run)),
        "canonical_topics": len(_canonical_topic_ids(run)),
        "lock": lock_path.relative_to(ROOT).as_posix(),
    }, ensure_ascii=False, indent=2))


def cmd_fallback(args: argparse.Namespace) -> None:
    run = _run(args.run)
    lock = _check_lock(run)
    if lock.get("fallback_used"):
        raise GuardError("the single optional-illustration fallback was already used")
    build = load(run / BUILD_NAME, {})
    unavailable = build.get("illustration_unavailable", []) if isinstance(build, dict) else []
    unavailable_ids = {
        str(row.get("concept_id") or "").strip()
        for row in unavailable
        if isinstance(row, dict)
    }
    if args.concept not in unavailable_ids:
        raise GuardError("fallback is only allowed for an illustration reported unavailable by the previous build")

    plan_path, plan = _plan(run)
    target: dict[str, Any] | None = None
    for row in _visual_rows(plan):
        if str(row.get("concept_id") or "").strip() == args.concept:
            target = row
            break
    if not target:
        raise GuardError(f"visual row not found for concept: {args.concept}")
    if str(target.get("need") or "") != "visual_helpful" or str(target.get("visual_medium") or "") != "illustration":
        raise GuardError("provider fallback is only valid for visual_helpful illustrations")
    old_derived = str(target.get("derived_figure_id") or "").strip()
    target["need"] = "visual_not_needed"
    target["reason"] = "Optional physical-recognition illustration omitted because the configured provider is unavailable for this run."
    for key in ("visual_medium", "derived_figure_id", "illustration", "sketch_spec", "source_figure_id"):
        target.pop(key, None)

    review = plan.get("physical_recognition_review")
    if isinstance(review, dict):
        candidates = review.get("candidates", [])
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if old_derived and str(candidate.get("derived_figure_id") or "").strip() == old_derived:
                    candidate["decision"] = "visual_not_needed"
                    candidate["reason"] = "Optional physical-recognition illustration omitted because the configured provider is unavailable for this run."
                    candidate.pop("derived_figure_id", None)

    save(plan_path, plan)
    course, unit_id, _base = _context(run)
    try:
        visual_plan_hybrid.inspect_plan(course, unit_id, plan_path)
    except Exception as exc:
        raise GuardError(f"bounded fallback produced an invalid plan: {exc}") from exc
    updated = _lock_payload(
        run,
        fallback_used=True,
        fallback={"concept_id": args.concept, "decision": "visual_not_needed", "previous_derived_figure_id": old_derived},
    )
    save(run / LOCK_NAME, updated)
    print(json.dumps({"ok": True, "fallback": updated["fallback"], "plan_sha256": updated["plan_sha256"]}, ensure_ascii=False, indent=2))


def _figure_registry_path(run: Path) -> Path:
    inp = load(run / "01-input.json", {})
    if not isinstance(inp, dict) or not inp.get("figures_file"):
        raise GuardError("01-input.json figures_file missing")
    return _repo_path(inp["figures_file"])


def _root_metadata(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key not in {"version", "figures"}}


def cmd_build(args: argparse.Namespace) -> None:
    run = _run(args.run)
    lock = _check_lock(run)
    course, unit_id, _base = _context(run)
    plan_path, _plan_data = _plan(run)
    figures_path = _figure_registry_path(run)
    before = load(figures_path, {})
    if not isinstance(before, dict):
        raise GuardError("figures registry is invalid before visual build")
    before_meta = _root_metadata(before)

    try:
        report = visual_plan_hybrid.materialize_plan(course, unit_id, plan_path)
    finally:
        # The V4 save layer historically dropped unit/root metadata when appending
        # derived rows through a merged registry.  Restore the exact pre-build
        # metadata while preserving only the newly materialized figure rows.
        current = load(figures_path, {})
        if isinstance(current, dict) and isinstance(current.get("figures"), dict):
            repaired = dict(before_meta)
            repaired["version"] = current.get("version", before.get("version", 2))
            repaired["figures"] = current["figures"]
            save(figures_path, repaired)

    report["plan_lock_sha256"] = sha(run / LOCK_NAME)
    report["plan_sha256"] = lock.get("plan_sha256")
    save(run / BUILD_NAME, report)
    after = load(figures_path, {})
    if not isinstance(after, dict) or _root_metadata(after) != before_meta:
        raise GuardError("figure registry root metadata changed during hybrid build")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("ok") is not True:
        raise SystemExit(2)


def _rebase_candidate_images(markdown: str, run: Path, unit_base: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        alt, src, title = match.group(1), match.group(2), match.group(3)
        if re.match(r"^[a-z]+://", src) or src.startswith("data:"):
            return match.group(0)
        direct = (run / src).resolve()
        unit_target = (unit_base / src).resolve()
        if direct.is_file():
            target = direct
        elif unit_target.is_file() and unit_target.is_relative_to(unit_base.resolve()):
            target = unit_target
        else:
            return match.group(0)
        rel = os.path.relpath(target, run).replace(os.sep, "/")
        title_part = f' "{title}"' if title else ""
        return f"![{alt}]({rel}{title_part})"
    return LOCAL_IMAGE_RE.sub(replace, markdown)


def cmd_render(args: argparse.Namespace) -> None:
    run = _run(args.run)
    _check_lock(run)
    _course, _unit_id, unit_base = _context(run)
    source = _repo_path(args.markdown)
    output = _repo_path(args.html)
    if not source.is_file() or not source.is_relative_to(run):
        raise GuardError("render markdown must be an existing run-local candidate")
    if not output.is_relative_to(run):
        raise GuardError("render HTML must stay inside the run")
    temp = run / "09-render-input.md"
    rewritten = _rebase_candidate_images(source.read_text(encoding="utf-8"), run, unit_base)
    temp.write_text(rewritten, encoding="utf-8")
    try:
        issues = render_study.render(temp, output, args.kind, course=args.course_title, scope=args.scope_title)
    finally:
        try:
            temp.unlink()
        except OSError:
            pass
    if issues:
        print(json.dumps({"ok": False, "issues": issues}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(json.dumps({"ok": True, "html": output.relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2))


def _review_paths(run: Path, slot: int) -> tuple[Path, Path, Path]:
    if slot == 1:
        return run / "04-humanized.md", run / "05-review-handoff.json", run / "05-review.json"
    return run / "06-repair.md", run / "07-review-handoff.json", run / "07-review.json"


def cmd_prepare_review(args: argparse.Namespace) -> None:
    run = _run(args.run)
    lock = _check_lock(run)
    default_candidate, handoff_path, _review = _review_paths(run, args.slot)
    candidate = _repo_path(args.candidate) if args.candidate else default_candidate
    if not candidate.is_file() or not candidate.is_relative_to(run):
        raise GuardError("review candidate must be an existing run-local markdown file")
    inp = load(run / "01-input.json", {})
    handoff = {
        "version": 1,
        "slot": args.slot,
        "candidate": candidate.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha(candidate),
        "plan_sha256": lock.get("plan_sha256"),
        "concepts_sha256": inp.get("concepts_sha256") if isinstance(inp, dict) else None,
        "topics_sha256": inp.get("topics_sha256") if isinstance(inp, dict) else None,
        "academic_sha256": inp.get("academic_sha256") if isinstance(inp, dict) else None,
        "review_contract": "Review only the bound candidate against canonical evidence/rules. Do not inherit or defend the author's reasoning.",
        "created_at": now(),
    }
    save(handoff_path, handoff)
    print(json.dumps({"ok": True, "handoff": handoff_path.relative_to(ROOT).as_posix(), "handoff_sha256": sha(handoff_path)}, ensure_ascii=False, indent=2))


def _review_binding_issues(run: Path, slot: int) -> list[str]:
    candidate, handoff_path, review_path = _review_paths(run, slot)
    issues: list[str] = []
    handoff = load(handoff_path, {})
    review = load(review_path, {})
    if not isinstance(handoff, dict) or not handoff_path.is_file():
        return [f"review-{slot}-handoff-missing"]
    if not isinstance(review, dict) or not review_path.is_file():
        return [f"review-{slot}-missing"]
    if handoff.get("candidate_sha256") != sha(candidate):
        issues.append(f"review-{slot}-candidate-changed")
    if review.get("handoff_sha256") != sha(handoff_path):
        issues.append(f"review-{slot}-handoff-hash-mismatch")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        issues.append(f"review-{slot}-reviewer-metadata-missing")
    else:
        mode = reviewer.get("mode")
        if mode not in {"isolated", "portable-handoff"}:
            issues.append(f"review-{slot}-reviewer-mode-invalid")
        independent = reviewer.get("independent")
        if mode == "isolated" and independent is not True:
            issues.append(f"review-{slot}-isolated-not-independent")
        if mode == "portable-handoff" and independent is not False:
            issues.append(f"review-{slot}-portable-must-not-claim-independence")
    issues.extend(f"review-{slot}-{item}" for item in evaluate_review(review))
    return issues


def cmd_validate_review(args: argparse.Namespace) -> None:
    run = _run(args.run)
    _check_lock(run)
    issues = _review_binding_issues(run, args.slot)
    print(json.dumps({"ok": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)


def _attestation_payload(run: Path) -> dict[str, Any]:
    manifest = run / "manifest.json"
    return {
        "version": 1,
        "ok": True,
        "validated_at": now(),
        "manifest_sha256": sha(manifest),
        "plan_sha256": sha(run / "02-plan.json"),
        "plan_lock_sha256": sha(run / LOCK_NAME),
        "visual_build_sha256": sha(run / BUILD_NAME),
        "integrity_sha256": sha(run / "10-integrity.json"),
        "publication_sha256": sha(run / "11-publication.json"),
    }


def _attestation_issues(run: Path) -> list[str]:
    path = run / FINISH_NAME
    data = load(path, {})
    if not path.is_file() or not isinstance(data, dict) or data.get("ok") is not True:
        return ["finish-attestation-missing"]
    expected = _attestation_payload(run)
    issues: list[str] = []
    for key in (
        "manifest_sha256", "plan_sha256", "plan_lock_sha256", "visual_build_sha256",
        "integrity_sha256", "publication_sha256",
    ):
        if data.get(key) != expected.get(key):
            issues.append(f"finish-attestation-{key}-mismatch")
    return issues


def _runtime_validation(run: Path) -> dict[str, Any]:
    _check_lock(run)
    # Correct the legacy helper for the active hybrid semantics. Python resolves
    # the global at call time, so both visual-build and figure-drift validation
    # now ignore explicitly omitted visual_not_needed rows.
    pipeline_run._planned_derived_treatments = _selected_treatments  # type: ignore[attr-defined]
    result = pipeline_run.validate_run(run)
    errors = list(result.get("errors", [])) if isinstance(result, dict) else ["invalid-validation-result"]
    first_review = run / "05-review.json"
    if first_review.is_file():
        errors.extend(_review_binding_issues(run, 1))
        if evaluate_review(load(first_review, {})):
            errors.extend(_review_binding_issues(run, 2))
    return {"ok": not errors, "pipeline": "resumen", "errors": sorted(set(errors))}


def cmd_finish(args: argparse.Namespace) -> None:
    run = _run(args.run)
    result = _runtime_validation(run)
    if not result["ok"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    pipeline_run._planned_derived_treatments = _selected_treatments  # type: ignore[attr-defined]
    pipeline_run.cmd_finish(argparse.Namespace(run=str(run)))
    save(run / FINISH_NAME, _attestation_payload(run))
    print(json.dumps({"ok": True, "effective_status": "finished", "attestation": (run / FINISH_NAME).relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    run = _run(args.run)
    manifest = load(run / "manifest.json", {})
    try:
        validation = _runtime_validation(run)
    except GuardError as exc:
        validation = {"ok": False, "pipeline": "resumen", "errors": [str(exc)]}
    manifest_status = manifest.get("status") if isinstance(manifest, dict) else None
    attestation_issues = _attestation_issues(run) if manifest_status == "finished" else []
    if manifest_status == "finished" and validation.get("ok") and not attestation_issues:
        effective = "finished"
    elif validation.get("ok"):
        effective = "ready_to_finish"
    else:
        effective = "failed"
    print(json.dumps({
        "effective_status": effective,
        "manifest_status": manifest_status,
        "validation": validation,
        "attestation_issues": attestation_issues,
    }, ensure_ascii=False, indent=2))
    if effective == "failed":
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Hard guard for the hybrid resumen pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("preflight")
    p.add_argument("--course", required=True)
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("validate-plan")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_validate_plan)

    p = sub.add_parser("fallback")
    p.add_argument("--run", required=True)
    p.add_argument("--concept", required=True)
    p.set_defaults(func=cmd_fallback)

    p = sub.add_parser("build")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("render")
    p.add_argument("--run", required=True)
    p.add_argument("--markdown", required=True)
    p.add_argument("--html", required=True)
    p.add_argument("--kind", choices=["summary", "guide", "rapid-review", "learn", "explain"], default="summary")
    p.add_argument("--course-title", default="")
    p.add_argument("--scope-title", default="")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("prepare-review")
    p.add_argument("--run", required=True)
    p.add_argument("--slot", type=int, choices=[1, 2], default=1)
    p.add_argument("--candidate")
    p.set_defaults(func=cmd_prepare_review)

    p = sub.add_parser("validate-review")
    p.add_argument("--run", required=True)
    p.add_argument("--slot", type=int, choices=[1, 2], default=1)
    p.set_defaults(func=cmd_validate_review)

    p = sub.add_parser("finish")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_finish)

    p = sub.add_parser("status")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_status)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except GuardError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
