#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ASSESSMENT_TYPES = {
    "parcial", "recuperatorio", "final", "tp", "integrador", "coloquio",
    "quiz", "diagnostico", "otro"
}
SCOPE_STATUSES = {"confirmed", "likely", "unknown", "excluded"}
RULE_KINDS = {
    "promotion", "regularity", "recovery", "final_access", "final",
    "attendance", "grading", "tp", "correlative", "other"
}


def normalize(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def path_for(course: str) -> Path:
    p = Path(course) / "academico" / "academic.json"
    if not p.exists():
        raise SystemExit(f"Academic state not found: {p}")
    return p


def load(course: str) -> tuple[Path, dict[str, Any]]:
    p = path_for(course)
    return p, json.loads(p.read_text(encoding="utf-8"))


def save(p: Path, data: dict[str, Any]) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_assessment(data: dict[str, Any], key: str) -> dict[str, Any]:
    key_l = key.strip().lower()
    matches = [a for a in data.get("assessments", []) if a.get("id", "").lower() == key_l]
    if not matches:
        matches = [a for a in data.get("assessments", []) if a.get("name", "").strip().lower() == key_l]
    if not matches:
        raise SystemExit(f"Assessment not found: {key}")
    if len(matches) > 1:
        raise SystemExit(f"Ambiguous assessment name: {key}; use its id")
    return matches[0]


def add_unit(args: argparse.Namespace) -> None:
    p, data = load(args.course)
    units = data.setdefault("units", [])
    if any(u.get("id") == args.id for u in units):
        raise SystemExit(f"Unit id already exists: {args.id}")
    units.append({
        "id": args.id,
        "name": args.name,
        "topics": args.topic or [],
        "source": args.source or "",
        "status": args.status,
    })
    save(p, data)
    print(json.dumps(units[-1], ensure_ascii=False, indent=2))


def add_assessment(args: argparse.Namespace) -> None:
    p, data = load(args.course)
    assessments = data.setdefault("assessments", [])
    if any(a.get("id") == args.id for a in assessments):
        raise SystemExit(f"Assessment id already exists: {args.id}")
    if args.type not in ASSESSMENT_TYPES:
        raise SystemExit(f"Unsupported assessment type: {args.type}")
    if args.date:
        try:
            date.fromisoformat(args.date)
        except ValueError as e:
            raise SystemExit("Date must use YYYY-MM-DD") from e
    if args.type == "recuperatorio" and not args.parent:
        print("WARNING: recuperatorio created without parent assessment; relationship remains unknown", file=sys.stderr)
    scope = []
    for item in args.scope_unit or []:
        scope.append({"kind": "unit", "ref": item, "status": args.scope_status, "evidence": args.source or ""})
    for item in args.scope_topic or []:
        scope.append({"kind": "topic", "ref": item, "status": args.scope_status, "evidence": args.source or ""})
    if scope and args.scope_status == "confirmed" and not args.source:
        print("WARNING: confirmed assessment scope has no source/evidence reference", file=sys.stderr)
    rec = {
        "id": args.id,
        "type": args.type,
        "name": args.name,
        "date": args.date or "",
        "parent_assessment_id": args.parent or "",
        "format": args.format or "",
        "status": args.status,
        "scope": scope,
        "source": args.source or "",
        "result": {"status": "unknown", "grade": None, "notes": ""}
    }
    assessments.append(rec)
    save(p, data)
    print(json.dumps(rec, ensure_ascii=False, indent=2))


def set_rule(args: argparse.Namespace) -> None:
    p, data = load(args.course)
    if args.kind not in RULE_KINDS:
        raise SystemExit(f"Unsupported rule kind: {args.kind}")
    rules = data.setdefault("rules", [])
    rec = {"kind": args.kind, "text": args.text, "source": args.source or "", "status": args.status}
    rules.append(rec)
    save(p, data)
    print(json.dumps(rec, ensure_ascii=False, indent=2))


def scope(args: argparse.Namespace) -> None:
    _, data = load(args.course)
    a = find_assessment(data, args.assessment)
    out = {
        "assessment": {k: a.get(k) for k in ["id", "type", "name", "date", "parent_assessment_id", "format", "status"]},
        "confirmed": [], "likely": [], "unknown": [], "excluded": [],
        "source": a.get("source", "")
    }
    for s in a.get("scope", []):
        status = s.get("status", "unknown")
        if status not in out:
            status = "unknown"
        out[status].append({k: s.get(k) for k in ["kind", "ref", "evidence"]})
    print(json.dumps(out, ensure_ascii=False, indent=2))


def validate_data(data: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    units = {u.get("id") for u in data.get("units", [])}
    topics = {normalize(t) for u in data.get("units", []) for t in u.get("topics", []) if t}
    assessment_ids = {a.get("id") for a in data.get("assessments", [])}
    names: dict[str, int] = {}
    for a in data.get("assessments", []):
        n = normalize(a.get("name", ""))
        if n:
            names[n] = names.get(n, 0) + 1
    for n, count in names.items():
        if count > 1:
            issues.append({"severity": "warning", "item": n, "message": "duplicate assessment name; use ids to avoid ambiguity"})

    for a in data.get("assessments", []):
        aid = a.get("id", "?")
        if a.get("type") not in ASSESSMENT_TYPES:
            issues.append({"severity": "error", "item": aid, "message": "unknown assessment type"})
        parent = a.get("parent_assessment_id")
        if parent and parent not in assessment_ids:
            issues.append({"severity": "error", "item": aid, "message": f"parent assessment does not exist: {parent}"})
        if a.get("type") == "recuperatorio" and not parent:
            issues.append({"severity": "warning", "item": aid, "message": "recuperatorio has no parent; recovery relationship is unknown"})
        for row in a.get("scope", []):
            status = row.get("status", "unknown")
            if status not in SCOPE_STATUSES:
                issues.append({"severity": "error", "item": aid, "message": f"invalid scope status: {status}"})
            if row.get("kind") == "unit" and row.get("ref") not in units:
                issues.append({"severity": "warning", "item": aid, "message": f"scope references unknown unit: {row.get('ref')}"})
            if row.get("kind") == "topic" and topics and normalize(row.get("ref", "")) not in topics:
                issues.append({"severity": "warning", "item": aid, "message": f"scope references unknown topic: {row.get('ref')}"})
            if status == "confirmed" and not row.get("evidence"):
                issues.append({"severity": "warning", "item": aid, "message": f"confirmed scope lacks evidence: {row.get('kind')} {row.get('ref')}"})
        if not a.get("scope"):
            issues.append({"severity": "info", "item": aid, "message": "assessment scope is unknown/not recorded"})
        if a.get("type") == "final" and not a.get("source"):
            issues.append({"severity": "info", "item": aid, "message": "final has no source; do not assume cumulative scope"})

    for rule in data.get("rules", []):
        if rule.get("status") == "confirmed" and not rule.get("source"):
            issues.append({"severity": "warning", "item": f"rule:{rule.get('kind')}", "message": "confirmed rule has no source reference"})

    return {"valid": not any(i["severity"] == "error" for i in issues), "issues": issues}


def validate(args: argparse.Namespace) -> None:
    _, data = load(args.course)
    print(json.dumps(validate_data(data), ensure_ascii=False, indent=2))


def show(args: argparse.Namespace) -> None:
    _, data = load(args.course)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Manage structured university academic context")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show")
    p.add_argument("--course", required=True)
    p.set_defaults(func=show)

    p = sub.add_parser("add-unit")
    p.add_argument("--course", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--topic", action="append")
    p.add_argument("--source")
    p.add_argument("--status", choices=["planned", "in-progress", "covered", "unknown"], default="unknown")
    p.set_defaults(func=add_unit)

    p = sub.add_parser("add-assessment")
    p.add_argument("--course", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--type", required=True, choices=sorted(ASSESSMENT_TYPES))
    p.add_argument("--name", required=True)
    p.add_argument("--date")
    p.add_argument("--parent")
    p.add_argument("--format")
    p.add_argument("--status", choices=["planned", "completed", "cancelled", "unknown"], default="planned")
    p.add_argument("--scope-unit", action="append")
    p.add_argument("--scope-topic", action="append")
    p.add_argument("--scope-status", choices=sorted(SCOPE_STATUSES), default="unknown")
    p.add_argument("--source")
    p.set_defaults(func=add_assessment)

    p = sub.add_parser("set-rule")
    p.add_argument("--course", required=True)
    p.add_argument("--kind", required=True, choices=sorted(RULE_KINDS))
    p.add_argument("--text", required=True)
    p.add_argument("--source")
    p.add_argument("--status", choices=["confirmed", "likely", "unknown"], default="unknown")
    p.set_defaults(func=set_rule)

    p = sub.add_parser("scope")
    p.add_argument("--course", required=True)
    p.add_argument("--assessment", required=True)
    p.set_defaults(func=scope)

    p = sub.add_parser("validate")
    p.add_argument("--course", required=True)
    p.set_defaults(func=validate)

    return ap


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
