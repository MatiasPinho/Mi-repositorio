#!/usr/bin/env python3
"""Authoritative finish/status for guarded Hybrid V1 summaries.

Kept separate from ``resumen_guard.py`` so a failed first academic review remains
valid history when a bound second review accepts the repaired candidate.  The
legacy portable validator already models that two-review lifecycle; this module
adds only the guard-specific plan/review/attestation requirements.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import pipeline_run, resumen_guard  # noqa: E402
from scripts.academic_eval import evaluate_review  # noqa: E402


def _binding_only(run: Path, slot: int) -> list[str]:
    """Return handoff/reviewer-binding defects, not expected academic rejection."""
    all_issues = resumen_guard._review_binding_issues(run, slot)
    _candidate, _handoff, review_path = resumen_guard._review_paths(run, slot)
    review = resumen_guard.load(review_path, {})
    academic = {
        f"review-{slot}-{issue}"
        for issue in evaluate_review(review)
    } if isinstance(review, dict) else set()
    return [issue for issue in all_issues if issue not in academic]


def validate(run: Path) -> dict[str, object]:
    resumen_guard._check_lock(run)
    pipeline_run._planned_derived_treatments = resumen_guard._selected_treatments  # type: ignore[attr-defined]
    base = pipeline_run.validate_run(run)
    errors = list(base.get("errors", [])) if isinstance(base, dict) else ["invalid-validation-result"]

    first_path = run / "05-review.json"
    if first_path.is_file():
        errors.extend(_binding_only(run, 1))
        first_review = resumen_guard.load(first_path, {})
        if evaluate_review(first_review):
            # A failed first review is legitimate when it triggered repair.  The
            # legacy validator already requires and evaluates slot 2; here we
            # additionally require slot-2 handoff/reviewer provenance.
            errors.extend(_binding_only(run, 2))

    return {
        "ok": not errors,
        "pipeline": "resumen",
        "errors": sorted(set(errors)),
    }


def cmd_finish(args: argparse.Namespace) -> None:
    run = resumen_guard._run(args.run)
    result = validate(run)
    if not result["ok"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    pipeline_run._planned_derived_treatments = resumen_guard._selected_treatments  # type: ignore[attr-defined]
    pipeline_run.cmd_finish(argparse.Namespace(run=str(run)))
    resumen_guard.save(run / resumen_guard.FINISH_NAME, resumen_guard._attestation_payload(run))
    print(json.dumps({
        "ok": True,
        "effective_status": "finished",
        "attestation": (run / resumen_guard.FINISH_NAME).relative_to(ROOT).as_posix(),
    }, ensure_ascii=False, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    run = resumen_guard._run(args.run)
    manifest = resumen_guard.load(run / "manifest.json", {})
    try:
        validation = validate(run)
    except resumen_guard.GuardError as exc:
        validation = {"ok": False, "pipeline": "resumen", "errors": [str(exc)]}

    manifest_status = manifest.get("status") if isinstance(manifest, dict) else None
    attestation_issues = (
        resumen_guard._attestation_issues(run)
        if manifest_status == "finished"
        else []
    )
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Authoritative guarded resumen finish/status")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("finish")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_finish)
    p = sub.add_parser("status")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_status)
    args = ap.parse_args()
    try:
        args.func(args)
    except resumen_guard.GuardError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
