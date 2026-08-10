#!/usr/bin/env python3
"""Deterministic academic evaluation policy and frozen regression benchmark."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "academic_eval_policy.json"
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "academic_eval" / "cases.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy(path: Path | None = None) -> dict[str, Any]:
    policy = load_json(path or DEFAULT_POLICY)
    validate_policy(policy)
    return policy


def validate_policy(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise ValueError("academic evaluation policy must be a JSON object")
    if not isinstance(policy.get("version"), int) or policy["version"] < 1:
        raise ValueError("academic evaluation policy requires a positive integer version")
    minimum = policy.get("score_minimum")
    if not isinstance(minimum, (int, float)):
        raise ValueError("score_minimum must be numeric")
    for key in ("score_gates", "fidelity_checks", "accepted_fidelity_statuses", "issue_fields_must_be_empty"):
        value = policy.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"{key} must be a non-empty list of strings")
    claims = policy.get("claim_checks")
    if not isinstance(claims, dict):
        raise ValueError("claim_checks must be an object")
    if not isinstance(claims.get("minimum"), int) or claims["minimum"] < 0:
        raise ValueError("claim_checks.minimum must be a non-negative integer")
    fields = claims.get("required_text_fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(item, str) and item for item in fields):
        raise ValueError("claim_checks.required_text_fields must be a non-empty list of strings")


def _threshold_label(value: int | float) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def evaluate_review(data: Any, policy: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic gate issues. An empty list means the review is accepted."""
    policy = policy or load_policy()
    validate_policy(policy)
    issues: list[str] = []
    if not isinstance(data, dict):
        return ["review-not-object"]

    minimum = policy["score_minimum"]
    threshold = _threshold_label(minimum)
    scores = data.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}
    for key in policy["score_gates"]:
        try:
            if float(scores.get(key, -1)) < float(minimum):
                issues.append(f"score-{key}-below-{threshold}")
        except (TypeError, ValueError):
            issues.append(f"score-{key}-invalid")

    checks = data.get("fidelity_checks")
    if not isinstance(checks, dict):
        issues.append("fidelity-checks-missing")
    else:
        accepted_statuses = set(policy["accepted_fidelity_statuses"])
        for key in policy["fidelity_checks"]:
            item = checks.get(key)
            if not isinstance(item, dict):
                issues.append(f"fidelity-{key}-missing")
                continue
            if item.get("status") not in accepted_statuses:
                issues.append(f"fidelity-{key}-failed")
            if policy.get("require_fidelity_notes", False):
                notes = item.get("notes")
                if not isinstance(notes, str) or not notes.strip():
                    issues.append(f"fidelity-{key}-notes-missing")

    claim_policy = policy["claim_checks"]
    claim_checks = data.get("claim_checks")
    minimum_claims = claim_policy["minimum"]
    claims_required = bool(claim_policy.get("required", False))
    if not isinstance(claim_checks, list) or (claims_required and len(claim_checks) < minimum_claims):
        issues.append("claim-checks-missing")
    elif isinstance(claim_checks, list):
        required_verdict = claim_policy.get("required_verdict")
        for idx, item in enumerate(claim_checks):
            if not isinstance(item, dict):
                issues.append(f"claim-check-{idx}-invalid")
                continue
            if required_verdict is not None and item.get("verdict") != required_verdict:
                issues.append(f"claim-check-{idx}-not-supported")
            for field in claim_policy["required_text_fields"]:
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    issues.append(f"claim-check-{idx}-{field}-missing")

    for issue_field in policy["issue_fields_must_be_empty"]:
        if data.get(issue_field):
            issues.append(f"{issue_field.replace('_', '-')}-present")
    if policy.get("require_pass_true", False) and data.get("pass") is not True:
        issues.append("review-pass-false")
    return issues


def iter_cases(path: Path):
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"benchmark case at line {line_number} must be an object")
        yield line_number, case


def run_benchmark(cases_path: Path = DEFAULT_CASES, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy()
    validate_policy(policy)
    results: list[dict[str, Any]] = []
    false_accepts = 0
    false_rejects = 0
    expectation_misses = 0

    for line_number, case in iter_cases(cases_path):
        case_id = str(case.get("id") or f"line-{line_number}")
        expected_pass = case.get("expected_pass")
        if not isinstance(expected_pass, bool):
            raise ValueError(f"benchmark case {case_id} requires boolean expected_pass")
        issues = evaluate_review(case.get("review"), policy)
        actual_pass = not issues
        missing_expected_issues = [
            issue for issue in case.get("expected_issues_contains", []) if issue not in issues
        ]
        matched = actual_pass == expected_pass and not missing_expected_issues
        if actual_pass and not expected_pass:
            false_accepts += 1
        if not actual_pass and expected_pass:
            false_rejects += 1
        if missing_expected_issues:
            expectation_misses += 1
        results.append(
            {
                "id": case_id,
                "expected_pass": expected_pass,
                "actual_pass": actual_pass,
                "issues": issues,
                "missing_expected_issues": missing_expected_issues,
                "matched": matched,
            }
        )

    matched = sum(1 for item in results if item["matched"])
    total = len(results)
    return {
        "ok": matched == total,
        "policy_version": policy["version"],
        "total": total,
        "matched": matched,
        "accuracy": (matched / total) if total else 1.0,
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "expectation_misses": expectation_misses,
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Evaluate academic-review gates deterministically")
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    sub = ap.add_subparsers(dest="cmd", required=True)

    evaluate = sub.add_parser("evaluate", help="Evaluate one review JSON file")
    evaluate.add_argument("--review", type=Path, required=True)

    benchmark = sub.add_parser("benchmark", help="Run the frozen academic evaluation corpus")
    benchmark.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    policy = load_policy(args.policy)
    if args.cmd == "evaluate":
        issues = evaluate_review(load_json(args.review), policy)
        print(json.dumps({"ok": not issues, "policy_version": policy["version"], "issues": issues}, ensure_ascii=False, indent=2))
        return 0 if not issues else 1
    result = run_benchmark(args.cases, policy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
