#!/usr/bin/env python3
"""Resolve structured academic claims into two explicit canonical views.

This module never extracts claims from prose and never calls an LLM. It receives
already-structured evidence and answers two separate questions:

- academic_truth: what value is best supported academically?
- assessment_expectation: what value is best supported as the course/teacher expectation?

Raw teacher transcripts are evidence, but their authority is deliberately lower
than explicit confirmed teacher statements. Conflicts are preserved rather than
silently merged.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "semantic_claim_policy.json"
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "semantic_claims" / "cases.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy(path: Path | None = None) -> dict[str, Any]:
    policy = load_json(path or DEFAULT_POLICY)
    validate_policy(policy)
    return policy


def validate_policy(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise ValueError("semantic claim policy must be an object")
    if not isinstance(policy.get("version"), int) or policy["version"] < 1:
        raise ValueError("semantic claim policy requires a positive integer version")
    domains = policy.get("domains")
    source_types = policy.get("source_types")
    if not isinstance(domains, list) or not domains:
        raise ValueError("domains must be a non-empty list")
    if not isinstance(source_types, list) or not source_types:
        raise ValueError("source_types must be a non-empty list")
    profiles = policy.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != {"academic_truth", "assessment_expectation"}:
        raise ValueError("profiles must define academic_truth and assessment_expectation")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ValueError(f"profile {name} must be an object")
        if not isinstance(profile.get("minimum_gap"), int) or profile["minimum_gap"] < 0:
            raise ValueError(f"profile {name}.minimum_gap must be a non-negative integer")
        ranks = profile.get("ranks")
        if not isinstance(ranks, dict):
            raise ValueError(f"profile {name}.ranks must be an object")
        missing = [source for source in source_types if source not in ranks]
        if missing:
            raise ValueError(f"profile {name} misses source ranks: {missing}")
    allowed = policy.get("supersedes_allowed")
    if not isinstance(allowed, dict):
        raise ValueError("supersedes_allowed must be an object")
    for domain in domains:
        values = allowed.get(domain)
        if not isinstance(values, list):
            raise ValueError(f"supersedes_allowed.{domain} must be a list")


def canonical_value(value: Any) -> str:
    """Stable value identity for booleans, strings, numbers, arrays and objects."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_key(claim: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(claim.get("domain", "")).strip(),
        str(claim.get("subject", "")).strip(),
        str(claim.get("predicate", "")).strip(),
        str(claim.get("object", "")).strip(),
    )


def validate_claims(claims: Any, policy: dict[str, Any] | None = None) -> list[str]:
    policy = policy or load_policy()
    issues: list[str] = []
    if not isinstance(claims, list):
        return ["claims-not-list"]

    seen: set[str] = set()
    ids = {str(item.get("id")) for item in claims if isinstance(item, dict) and item.get("id")}
    for idx, claim in enumerate(claims):
        prefix = f"claim-{idx}"
        if not isinstance(claim, dict):
            issues.append(f"{prefix}-not-object")
            continue
        claim_id = str(claim.get("id") or "").strip()
        if not claim_id:
            issues.append(f"{prefix}-id-missing")
        elif claim_id in seen:
            issues.append(f"claim-id-duplicate:{claim_id}")
        else:
            seen.add(claim_id)

        domain = str(claim.get("domain") or "").strip()
        if domain not in policy["domains"]:
            issues.append(f"{claim_id or prefix}-invalid-domain:{domain}")
        for field in ("subject", "predicate", "source"):
            value = claim.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"{claim_id or prefix}-{field}-missing")
        if "value" not in claim:
            issues.append(f"{claim_id or prefix}-value-missing")
        source_type = str(claim.get("source_type") or "").strip()
        if source_type not in policy["source_types"]:
            issues.append(f"{claim_id or prefix}-invalid-source-type:{source_type}")

        supersedes = claim.get("supersedes", [])
        if not isinstance(supersedes, list) or not all(isinstance(item, str) and item for item in supersedes):
            issues.append(f"{claim_id or prefix}-supersedes-invalid")
            supersedes = []
        if supersedes and source_type not in policy["supersedes_allowed"].get(domain, []):
            issues.append(f"{claim_id or prefix}-supersedes-not-authorized")
        for target in supersedes:
            if target not in ids:
                issues.append(f"{claim_id or prefix}-supersedes-unknown:{target}")
            if target == claim_id:
                issues.append(f"{claim_id or prefix}-supersedes-self")
    return issues


def _valid_superseded_ids(claims: list[dict[str, Any]], policy: dict[str, Any]) -> set[str]:
    superseded: set[str] = set()
    ids = {str(claim.get("id")) for claim in claims}
    for claim in claims:
        domain = str(claim.get("domain") or "")
        source_type = str(claim.get("source_type") or "")
        if source_type not in policy["supersedes_allowed"].get(domain, []):
            continue
        for target in claim.get("supersedes", []):
            if target in ids and target != claim.get("id"):
                superseded.add(target)
    return superseded


def resolve_profile(claims: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    ranks = profile["ranks"]
    minimum_gap = profile["minimum_gap"]
    by_value: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        by_value[canonical_value(claim.get("value"))].append(claim)

    if len(by_value) == 1:
        value_key = next(iter(by_value))
        rows = by_value[value_key]
        return {
            "status": "resolved",
            "value": rows[0].get("value"),
            "claim_ids": [str(row.get("id")) for row in rows],
            "reason": "agreement",
        }

    scored: list[tuple[int, str, dict[str, Any]]] = []
    for claim in claims:
        rank = int(ranks.get(str(claim.get("source_type")), 0))
        scored.append((rank, canonical_value(claim.get("value")), claim))
    scored.sort(key=lambda row: row[0], reverse=True)
    top_rank = scored[0][0]
    top_values = {value_key for rank, value_key, _ in scored if rank == top_rank}
    if len(top_values) != 1:
        return {
            "status": "unresolved",
            "value": None,
            "claim_ids": [str(row[2].get("id")) for row in scored if row[0] == top_rank],
            "reason": "equal-authority-conflict",
        }

    winner_key = next(iter(top_values))
    opposing_ranks = [rank for rank, value_key, _ in scored if value_key != winner_key]
    next_rank = max(opposing_ranks) if opposing_ranks else -1
    gap = top_rank - next_rank
    winner_claims = [claim for rank, value_key, claim in scored if value_key == winner_key and rank == top_rank]
    if gap < minimum_gap:
        return {
            "status": "unresolved",
            "value": None,
            "claim_ids": [str(claim.get("id")) for _, _, claim in scored],
            "reason": f"authority-gap-too-small:{gap}<{minimum_gap}",
        }
    return {
        "status": "resolved",
        "value": winner_claims[0].get("value"),
        "claim_ids": [str(claim.get("id")) for claim in winner_claims],
        "reason": f"authority-gap:{gap}",
    }


def resolve_claims(claims: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy()
    issues = validate_claims(claims, policy)
    if issues:
        return {"ok": False, "policy_version": policy["version"], "issues": issues, "groups": []}

    superseded = _valid_superseded_ids(claims, policy)
    active = [claim for claim in claims if str(claim.get("id")) not in superseded]
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for claim in active:
        groups[semantic_key(claim)].append(claim)

    output: list[dict[str, Any]] = []
    unresolved = 0
    split_view = 0
    contradictions = 0
    for key in sorted(groups):
        rows = groups[key]
        distinct_values = {canonical_value(row.get("value")) for row in rows}
        academic = resolve_profile(rows, policy["profiles"]["academic_truth"])
        assessment = resolve_profile(rows, policy["profiles"]["assessment_expectation"])
        relation = "agreement" if len(distinct_values) == 1 else "contradiction"
        if relation == "contradiction":
            contradictions += 1
        if academic["status"] != "resolved" or assessment["status"] != "resolved":
            status = "unresolved"
            unresolved += 1
        elif canonical_value(academic["value"]) != canonical_value(assessment["value"]):
            status = "split-view"
            split_view += 1
        else:
            status = "resolved"
        output.append({
            "key": {"domain": key[0], "subject": key[1], "predicate": key[2], "object": key[3]},
            "relation": relation,
            "status": status,
            "academic_truth": academic,
            "assessment_expectation": assessment,
            "active_claim_ids": [str(row.get("id")) for row in rows],
        })

    return {
        "ok": unresolved == 0,
        "policy_version": policy["version"],
        "claims": len(claims),
        "active_claims": len(active),
        "superseded_claim_ids": sorted(superseded),
        "contradictions": contradictions,
        "split_view": split_view,
        "unresolved": unresolved,
        "groups": output,
    }


def iter_cases(path: Path):
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"semantic case at line {line_number} must be an object")
        yield line_number, case


def _find_group(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any] | None:
    key = expected.get("key", {})
    for group in result.get("groups", []):
        actual = group.get("key", {})
        if all(actual.get(field, "") == key.get(field, "") for field in ("domain", "subject", "predicate", "object")):
            return group
    return None


def run_benchmark(cases_path: Path = DEFAULT_CASES, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy()
    results: list[dict[str, Any]] = []
    for line_number, case in iter_cases(cases_path):
        case_id = str(case.get("id") or f"line-{line_number}")
        result = resolve_claims(case.get("claims", []), policy)
        problems: list[str] = []
        expected_valid = case.get("expected_valid", True)
        if bool(result.get("issues")) == bool(expected_valid):
            problems.append(f"validity expected={expected_valid} issues={result.get('issues', [])}")
        for issue in case.get("expected_issues_contains", []):
            if issue not in result.get("issues", []):
                problems.append(f"missing-issue:{issue}")
        for group_expected in case.get("expected_groups", []):
            group = _find_group(result, group_expected)
            if group is None:
                problems.append(f"missing-group:{group_expected.get('key')}")
                continue
            for field in ("relation", "status"):
                if field in group_expected and group.get(field) != group_expected[field]:
                    problems.append(f"{field}: expected={group_expected[field]!r} actual={group.get(field)!r}")
            for profile_name in ("academic_truth", "assessment_expectation"):
                profile_expected = group_expected.get(profile_name)
                if not isinstance(profile_expected, dict):
                    continue
                actual_profile = group.get(profile_name, {})
                for field in ("status", "value"):
                    if field in profile_expected and actual_profile.get(field) != profile_expected[field]:
                        problems.append(f"{profile_name}.{field}: expected={profile_expected[field]!r} actual={actual_profile.get(field)!r}")
        results.append({"id": case_id, "ok": not problems, "issues": problems})
    passed = sum(1 for row in results if row["ok"])
    return {"ok": passed == len(results), "total": len(results), "passed": passed, "failed": len(results) - passed, "results": results}


def resolve_course(course: Path, write: bool = False) -> dict[str, Any]:
    academic_path = course / "academico" / "academic.json"
    if not academic_path.is_file():
        raise SystemExit(f"Academic state not found: {academic_path}")
    data = load_json(academic_path)
    claims = data.get("claims", [])
    result = resolve_claims(claims)
    if write:
        target = course / ".study" / "semantic-claims.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("resolve")
    p.add_argument("--claims", type=Path, required=True)
    p = sub.add_parser("course")
    p.add_argument("--course", type=Path, required=True)
    p.add_argument("--write", action="store_true")
    p = sub.add_parser("benchmark")
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    policy = load_policy(args.policy)
    if args.cmd == "resolve":
        payload = load_json(args.claims)
        claims = payload.get("claims", payload) if isinstance(payload, dict) else payload
        result = resolve_claims(claims, policy)
    elif args.cmd == "course":
        data = load_json(args.course / "academico" / "academic.json")
        result = resolve_claims(data.get("claims", []), policy)
        if args.write:
            target = args.course / ".study" / "semantic-claims.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        result = run_benchmark(args.cases, policy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
