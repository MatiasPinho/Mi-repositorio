#!/usr/bin/env python3
"""Build a compact deterministic fidelity-risk ledger before summary drafting.

The summary writer and academic reviewer should not spend a model call
rediscovering contradictions that the canonical claim resolver already knows.
This adapter resolves the structured claims in academic.json and emits only
risky groups (unresolved, split-view, or contradictory evidence) plus the
minimum source metadata needed to preserve the distinction in prose.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
try:
    from .semantic_claims import resolve_claims
    from .unit_identity import canonical_unit_id, resolve_unit
except ImportError:
    from semantic_claims import resolve_claims  # type: ignore
    from unit_identity import canonical_unit_id, resolve_unit  # type: ignore


def _scope_unit_id(course: Path, scope: str) -> str:
    if not scope.strip():
        return ""
    try:
        return str(resolve_unit(course, scope).get("unit_id") or "")
    except Exception:
        return ""


def _claim_unit_id(claim: dict[str, Any]) -> str:
    return canonical_unit_id(claim.get("unit_id") or claim.get("unit") or "")


def _minimal_evidence(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(claim.get("id") or ""),
        "value": claim.get("value"),
        "source_type": str(claim.get("source_type") or ""),
        "source": str(claim.get("source") or ""),
    }


def _handling(status: str, relation: str) -> str:
    if status == "unresolved":
        return "attribute-competing-evidence; do-not-pick-winner"
    if status == "split-view":
        return "separate-academic-truth-from-assessment-expectation"
    if relation == "contradiction":
        return "use-resolved-canonical-view; keep-source-disagreement-explicit-when-relevant"
    return "use-canonical-view"


def build_constraints(course: Path, scope: str = "") -> dict[str, Any]:
    academic_path = course / "academico" / "academic.json"
    if not academic_path.is_file():
        return {
            "version": 1,
            "ok": False,
            "unit_id": "",
            "issues": [f"academic-json-missing:{academic_path}"],
            "constraints": [],
        }

    try:
        academic = json.loads(academic_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "version": 1,
            "ok": False,
            "unit_id": "",
            "issues": [f"academic-json-invalid:{exc}"],
            "constraints": [],
        }

    raw_claims = academic.get("claims", []) if isinstance(academic, dict) else []
    if not isinstance(raw_claims, list):
        return {
            "version": 1,
            "ok": False,
            "unit_id": "",
            "issues": ["claims-not-list"],
            "constraints": [],
        }

    unit_id = _scope_unit_id(course, scope)
    claims: list[dict[str, Any]] = []
    for claim in raw_claims:
        if not isinstance(claim, dict):
            continue
        claim_unit = _claim_unit_id(claim)
        if claim_unit and unit_id and claim_unit != unit_id:
            continue
        claims.append(claim)

    result = resolve_claims(claims)
    issues = list(result.get("issues", [])) if isinstance(result.get("issues", []), list) else []
    by_id = {str(row.get("id") or ""): row for row in claims if row.get("id")}
    constraints: list[dict[str, Any]] = []

    for group in result.get("groups", []) if isinstance(result.get("groups"), list) else []:
        if not isinstance(group, dict):
            continue
        status = str(group.get("status") or "")
        relation = str(group.get("relation") or "")
        if status == "resolved" and relation != "contradiction":
            continue
        key = group.get("key", {}) if isinstance(group.get("key"), dict) else {}
        claim_ids = [str(value) for value in group.get("active_claim_ids", []) if value]
        constraints.append({
            "id": "claim:" + ":".join(str(key.get(field) or "") for field in ("domain", "subject", "predicate", "object")),
            "status": status,
            "relation": relation,
            "key": key,
            "handling": _handling(status, relation),
            "academic_truth": group.get("academic_truth"),
            "assessment_expectation": group.get("assessment_expectation"),
            "active_claim_ids": claim_ids,
            "evidence": [_minimal_evidence(by_id[cid]) for cid in claim_ids if cid in by_id],
        })

    return {
        "version": 1,
        # Unresolved claims are expected study-state, not a script failure. `ok`
        # means the ledger was derived from structurally valid claims.
        "ok": not issues,
        "unit_id": unit_id,
        "claims_considered": len(claims),
        "semantic_resolution_ok": bool(result.get("ok")),
        "constraints_count": len(constraints),
        "issues": issues,
        "constraints": constraints,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build compact summary fidelity constraints from canonical claims")
    ap.add_argument("--course", required=True)
    ap.add_argument("--scope", default="")
    ap.add_argument("--write", required=True)
    args = ap.parse_args()

    course = resolve_course(args.course)
    report = build_constraints(course, args.scope)
    out = Path(args.write).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
