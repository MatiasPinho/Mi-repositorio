#!/usr/bin/env python3
"""Deterministic concept tracker with spaced review + knowledge-graph priorities."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

if __package__:
    from .course_layout import LayoutError, load_registry, save_registry
    from .unit_identity import record_unit_id, resolve_unit
else:
    from course_layout import LayoutError, load_registry, save_registry
    from unit_identity import record_unit_id, resolve_unit

DEFAULT = {"version": 2, "concepts": {}}


def progress_path(course: Path) -> Path:
    return course / "progreso" / "progress.json"


def load(course: Path) -> dict:
    data = load_registry(course, "progress")
    data.setdefault("version", 2)
    data.setdefault("concepts", {})
    return data


def save(course: Path, data: dict) -> None:
    try:
        save_registry(course, "progress", data)
    except LayoutError as exc:
        raise SystemExit(str(exc)) from exc


def key_for(name: str) -> str:
    return " ".join(name.strip().lower().split())


def slugify(text: str) -> str:
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "concepto"


def ensure(data: dict, concept: str, unit: str = "") -> dict:
    k = key_for(concept)
    if k not in data["concepts"]:
        data["concepts"][k] = {
            "name": concept.strip(),
            "unit": unit.strip(),
            "mastery": 0.0,
            "attempts": 0,
            "last_rating": None,
            "streak": 0,
            "ease": 2.5,
            "interval_days": 0,
            "last_review": None,
            "next_review": date.today().isoformat(),
            "notes": [],
        }
    elif unit and not data["concepts"][k].get("unit"):
        data["concepts"][k]["unit"] = unit.strip()
    return data["concepts"][k]


def knowledge(course: Path) -> dict:
    try:
        return load_registry(course, "concepts")
    except (json.JSONDecodeError, OSError, LayoutError):
        return {"concepts": {}}


def graph_item(graph: dict, concept_name: str) -> dict | None:
    key = key_for(concept_name)
    if key in graph.get("concepts", {}):
        return graph["concepts"][key]
    for item in graph.get("concepts", {}).values():
        if key_for(item.get("name", "")) == key:
            return item
    return None


def dependent_count(graph: dict, concept_name: str) -> int:
    """Count unique dependent concepts; do not double-count prerequisite + depends-on representations."""
    target = key_for(concept_name)
    dependents: set[str] = set()
    for item in graph.get("concepts", {}).values():
        item_name = key_for(item.get("name", ""))
        prereqs = {key_for(x) for x in item.get("prerequisites", [])}
        relation_depends = {
            key_for(rel.get("target", ""))
            for rel in item.get("relations", [])
            if rel.get("type") == "depends-on"
        }
        if target in prereqs or target in relation_depends:
            dependents.add(item_name)
    return len(dependents)


def recurring_error_score(item: dict | None) -> tuple[float, list[str]]:
    if not item:
        return 0.0, []
    errors = item.get("recurring_errors", [])
    total = sum(max(1, int(err.get("count", 1))) for err in errors)
    names = [
        err.get("text", "")
        for err in sorted(errors, key=lambda e: -int(e.get("count", 1)))[:3]
        if err.get("text")
    ]
    return min(4.0, total * 0.75), names



def teaching_signal_score(item: dict | None, assessment_id: str | None = None) -> tuple[float, list[str]]:
    """Soft pedagogical signal from class transcripts; never equals confirmed exam scope."""
    if not item:
        return 0.0, []
    score = 0.0
    labels: list[str] = []
    for sig in item.get("teaching_signals", []):
        sig_assessment = sig.get("assessment_id")
        if sig_assessment and assessment_id and key_for(sig_assessment) != key_for(assessment_id):
            continue
        typ = sig.get("type", "")
        confidence = sig.get("confidence", "ambiguous")
        weight = {"explicit": 1.0, "strong-cue": 0.7, "ambiguous": 0.3}.get(confidence, 0.3)
        if typ in {"important", "question-pattern", "exam-cue"}:
            score += 0.6 * weight
            labels.append(typ)
        elif typ == "common-error":
            score += 0.4 * weight
            labels.append(typ)
    return min(1.5, score), sorted(set(labels))



def academic_state(course: Path) -> dict:
    p = course / "academico" / "academic.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_assessment(course: Path, value: str | None) -> tuple[str | None, dict | None]:
    if not value:
        return None, None
    data = academic_state(course)
    assessments = data.get("assessments", [])
    if not assessments:
        return value.strip(), None
    target = key_for(value)
    matches = [a for a in assessments if key_for(a.get("id", "")) == target]
    if not matches:
        matches = [a for a in assessments if key_for(a.get("name", "")) == target]
    if not matches:
        raise SystemExit(f"Unknown assessment: {value}. Register it in academico/academic.json first.")
    if len(matches) > 1:
        raise SystemExit(f"Ambiguous assessment name: {value}; use its id")
    return matches[0].get("id", value).strip(), matches[0]


def scope_relevance(course: Path, item: dict | None, assessment_id: str | None, assessment: dict | None) -> str:
    if not item or not assessment_id:
        return "unknown"

    # Explicit concept-level evidence wins.
    raw = item.get("assessment_relevance", {})
    if isinstance(raw, dict):
        mapping = raw.get("by_assessment", {})
        target = key_for(assessment_id)
        for key, rec in mapping.items():
            rec_id = key_for(rec.get("assessment_id", key)) if isinstance(rec, dict) else key_for(key)
            if key_for(key) == target or rec_id == target:
                return rec.get("status", "unknown") if isinstance(rec, dict) else "unknown"

    # Otherwise infer from the structured unit scope, if the concept has a matching unit.
    if not assessment:
        return "unknown"
    concept_unit = key_for(item.get("unit", ""))
    if not concept_unit:
        return "unknown"
    academic = academic_state(course)
    units = academic.get("units", [])
    aliases: set[str] = {concept_unit}
    for u in units:
        if concept_unit in {key_for(u.get("id", "")), key_for(u.get("name", ""))}:
            aliases.update({key_for(u.get("id", "")), key_for(u.get("name", ""))})
    for scope in assessment.get("scope", []):
        if scope.get("kind") == "unit" and key_for(scope.get("ref", "")) in aliases:
            return scope.get("status", "unknown")
    return "unknown"


def add(args):
    course = Path(args.course)
    data = load(course)
    item = ensure(data, args.concept, args.unit or "")
    save(course, data)
    print(json.dumps(item, ensure_ascii=False, indent=2))


def sync_graph(args):
    course = Path(args.course)
    data = load(course)
    graph = knowledge(course)
    added = []
    updated_units = []
    for concept in graph.get("concepts", {}).values():
        name = concept.get("name", "").strip()
        if not name:
            continue
        key = key_for(name)
        existed = key in data["concepts"]
        before_unit = data["concepts"].get(key, {}).get("unit", "") if existed else ""
        item = ensure(data, name, concept.get("unit", ""))
        if not existed:
            added.append(name)
        elif not before_unit and item.get("unit"):
            updated_units.append(name)
    save(course, data)
    print(json.dumps({"added": added, "updated_units": updated_units, "tracked": len(data["concepts"])}, ensure_ascii=False, indent=2))


def record_graph_error(course: Path, concept: str, error: str) -> None:
    if not error:
        return
    graph = knowledge(course)
    graph.setdefault("version", 2)
    graph.setdefault("concepts", {})
    k = key_for(concept)
    if k not in graph["concepts"]:
        graph["concepts"][k] = {
            "id": slugify(concept),
            "name": concept.strip(),
            "unit": "",
            "summary": "",
            "precise_definition": "",
            "prerequisites": [],
            "relations": [],
            "sources": [],
            "examples": [],
            "traps": [],
            "recurring_errors": [],
            "assessment_relevance": {"by_assessment": {}},
            "teaching_signals": [],
            "last_updated": date.today().isoformat(),
        }
    item = graph["concepts"][k]
    normalized = key_for(error)
    found = next(
        (e for e in item.setdefault("recurring_errors", []) if key_for(e.get("text", "")) == normalized),
        None,
    )
    if found:
        found["count"] = int(found.get("count", 1)) + 1
        found["last_seen"] = date.today().isoformat()
    else:
        item["recurring_errors"].append(
            {"text": error.strip(), "count": 1, "last_seen": date.today().isoformat()}
        )
    item["last_updated"] = date.today().isoformat()
    try:
        save_registry(course, "concepts", graph)
    except LayoutError as exc:
        raise SystemExit(str(exc)) from exc


def record(args):
    if not 0 <= args.rating <= 5:
        raise SystemExit("--rating must be between 0 and 5")
    course = Path(args.course)
    data = load(course)
    item = ensure(data, args.concept, args.unit or "")
    q = args.rating
    item["attempts"] += 1
    item["last_rating"] = q

    observed = q / 5.0
    alpha = 0.35 if item["attempts"] > 1 else 1.0
    item["mastery"] = round((1 - alpha) * item["mastery"] + alpha * observed, 3)

    if q < 3:
        item["streak"] = 0
        item["interval_days"] = 1
        item["ease"] = round(max(1.3, item["ease"] - 0.2), 2)
    else:
        item["streak"] += 1
        if item["streak"] == 1:
            interval = 1
        elif item["streak"] == 2:
            interval = 3
        else:
            interval = max(4, round(max(1, item["interval_days"]) * item["ease"]))
        item["interval_days"] = min(interval, 90)
        item["ease"] = round(
            max(1.3, item["ease"] + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))), 2
        )

    today = date.today()
    item["last_review"] = today.isoformat()
    item["next_review"] = (today + timedelta(days=item["interval_days"])).isoformat()
    if args.note:
        item["notes"].append({"date": today.isoformat(), "rating": q, "text": args.note})
        item["notes"] = item["notes"][-20:]
    save(course, data)

    if args.error:
        record_graph_error(course, args.concept, args.error)

    print(json.dumps(item, ensure_ascii=False, indent=2))


def due(args):
    course = Path(args.course)
    data = load(course)
    graph = knowledge(course)
    assessment_id, assessment = resolve_assessment(course, args.assessment)
    try:
        target = date.fromisoformat(args.on) if args.on else date.today()
    except ValueError as e:
        raise SystemExit("--on must use YYYY-MM-DD") from e
    items = []
    target_unit_id = resolve_unit(course, args.unit).get("unit_id", "") if args.unit else ""
    for item in data["concepts"].values():
        if target_unit_id and record_unit_id(course, item) != target_unit_id:
            continue
        nr = item.get("next_review")
        g = graph_item(graph, item["name"])
        relevance = scope_relevance(course, g, assessment_id, assessment)
        try:
            is_due = not nr or date.fromisoformat(nr) <= target
        except ValueError:
            is_due = True
        include_for_assessment = bool(args.include_not_due and assessment_id and relevance in {"confirmed", "likely"})
        if is_due or include_for_assessment:
            reasons = []
            if include_for_assessment and not is_due:
                reasons.append("assessment-review-not-due")
            try:
                days_overdue = 0 if not nr else max(0, (target - date.fromisoformat(nr)).days)
            except ValueError:
                days_overdue = 0
                reasons.append("invalid-review-date")
            mastery = float(item.get("mastery", 0))
            priority = days_overdue * 2 + (1 - mastery) * 10
            if days_overdue:
                reasons.append(f"overdue:{days_overdue}d")
            if mastery < 0.6:
                reasons.append("low-mastery")
            if (item.get("last_rating") if item.get("last_rating") is not None else 5) <= 2:
                priority += 2
                reasons.append("recent-failure")

            deps = dependent_count(graph, item["name"])
            if deps:
                boost = min(4.0, deps * 0.8)
                priority += boost
                reasons.append(f"prerequisite-for:{deps}")

            err_boost, errors = recurring_error_score(g)
            if err_boost:
                priority += err_boost
                reasons.append("recurring-errors")

            signal_boost, signal_labels = teaching_signal_score(g, assessment_id)
            if signal_boost:
                priority += signal_boost
                reasons.append("teacher-emphasis:" + ",".join(signal_labels))

            if relevance == "confirmed":
                priority += 3
                reasons.append(f"assessment-confirmed:{assessment_id}")
            elif relevance == "likely":
                priority += 1
                reasons.append(f"assessment-likely:{assessment_id}")
            elif relevance in {"excluded", "not-assessed"}:
                priority -= 3
                reasons.append(f"assessment-excluded:{assessment_id}")

            enriched = dict(item)
            enriched["study_priority"] = round(priority, 2)
            enriched["priority_reasons"] = reasons
            enriched["prerequisite_for_count"] = deps
            enriched["recurring_errors"] = errors
            enriched["assessment_relevance"] = relevance
            enriched["assessment"] = assessment_id
            if g:
                enriched["prerequisites"] = g.get("prerequisites", [])
            items.append(enriched)
    items.sort(key=lambda x: (-x["study_priority"], x["name"].lower()))
    print(json.dumps(items, ensure_ascii=False, indent=2))


def status(args):
    course = Path(args.course)
    data = load(course)
    graph = knowledge(course)
    items = list(data["concepts"].values())
    items.sort(key=lambda x: (x.get("mastery", 0), x["name"].lower()))
    if not items:
        print("No concepts tracked yet.")
        return
    avg = sum(float(i.get("mastery", 0)) for i in items) / len(items)
    due_count = 0
    for i in items:
        nr = i.get("next_review")
        if not nr:
            due_count += 1
            continue
        try:
            if date.fromisoformat(nr) <= date.today():
                due_count += 1
        except ValueError:
            due_count += 1
    recurring = []
    for i in items:
        g = graph_item(graph, i["name"])
        if g and g.get("recurring_errors"):
            recurring.append({"name": i["name"], "errors": g["recurring_errors"]})
    summary = {
        "concept_count": len(items),
        "average_mastery": round(avg, 3),
        "due_now": due_count,
        "weakest": [
            {
                "name": i["name"],
                "unit": i.get("unit", ""),
                "mastery": i.get("mastery", 0),
                "next_review": i.get("next_review"),
            }
            for i in items[:10]
        ],
        "recurring_error_concepts": recurring[:10],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--unit")
    p.set_defaults(func=add)

    p = sub.add_parser("sync")
    p.add_argument("--course", required=True)
    p.set_defaults(func=sync_graph)

    p = sub.add_parser("record")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--unit")
    p.add_argument("--rating", required=True, type=int)
    p.add_argument("--note")
    p.add_argument("--error", help="Specific misconception/error to persist in the knowledge graph")
    p.set_defaults(func=record)

    p = sub.add_parser("due")
    p.add_argument("--course", required=True)
    p.add_argument("--on", help="YYYY-MM-DD")
    p.add_argument("--assessment", help="Assessment id/name currently being prepared")
    p.add_argument("--unit", help="Limit reviews to one stable unit")
    p.add_argument("--include-not-due", action="store_true", help="Also return confirmed/likely in-scope concepts even when their spaced-review date is later")
    p.set_defaults(func=due)

    p = sub.add_parser("status")
    p.add_argument("--course", required=True)
    p.set_defaults(func=status)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
