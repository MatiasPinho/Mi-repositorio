#!/usr/bin/env python3
"""Deterministic concept knowledge graph for the university study system."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

if __package__:
    from .course_layout import LayoutError, load_registry, resolve_source, save_registry
    from .unit_identity import canonical_unit_id, resolve_unit
else:
    from course_layout import LayoutError, load_registry, resolve_source, save_registry
    from unit_identity import canonical_unit_id, resolve_unit

DEFAULT = {"version": 2, "concepts": {}}
RELATION_TYPES = {
    "prerequisite-of",
    "depends-on",
    "example-of",
    "contrast-with",
    "special-case-of",
    "used-by",
    "frequently-confused-with",
    "related-to",
}
RELEVANCE = {"confirmed", "likely", "unknown", "excluded", "not-assessed"}


def graph_path(course: Path) -> Path:
    return course / "conocimiento" / "concepts.json"


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFC", str(text or "")).casefold()
    return " ".join(value.strip().split())


def display_text(text: str) -> str:
    return unicodedata.normalize("NFC", str(text or "").strip())


def slugify(text: str) -> str:
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "concepto"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(course: Path) -> dict:
    data = load_registry(course, "concepts")
    data.setdefault("version", 2)
    data.setdefault("concepts", {})
    return data


def save(course: Path, data: dict) -> None:
    try:
        save_registry(course, "concepts", data)
    except LayoutError as exc:
        raise SystemExit(str(exc)) from exc


def find_key(data: dict, name: str) -> str | None:
    target = normalize(name)
    for key, item in data.get("concepts", {}).items():
        if normalize(item.get("name", "")) == target or normalize(key) == target:
            return key
    return None



def canonical_assessment(course: Path, value: str) -> str:
    p = course / "academico" / "academic.json"
    if not p.exists():
        return value.strip()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return value.strip()
    assessments = data.get("assessments", [])
    if not assessments:
        return value.strip()
    target = normalize(value)
    matches = [a for a in assessments if normalize(a.get("id", "")) == target]
    if not matches:
        matches = [a for a in assessments if normalize(a.get("name", "")) == target]
    if not matches:
        raise SystemExit(f"Unknown assessment: {value}. Register it in academico/academic.json first.")
    if len(matches) > 1:
        raise SystemExit(f"Ambiguous assessment name: {value}; use its id")
    return matches[0].get("id", value).strip()


def relevance_map(item: dict) -> dict:
    """Return assessment-specific relevance, migrating legacy single-status shape in memory."""
    raw = item.get("assessment_relevance", {})
    if isinstance(raw, dict) and "by_assessment" in raw:
        return raw.setdefault("by_assessment", {})
    if isinstance(raw, dict) and raw.get("status"):
        legacy = {"_legacy": {"status": raw.get("status", "unknown"), "evidence": raw.get("evidence", "")}}
        item["assessment_relevance"] = {"by_assessment": legacy}
        return legacy
    item["assessment_relevance"] = {"by_assessment": {}}
    return item["assessment_relevance"]["by_assessment"]


def ensure(data: dict, name: str, unit: str = "") -> tuple[str, dict]:
    canonical_name = display_text(name)
    key = find_key(data, canonical_name) or normalize(canonical_name)
    if key not in data["concepts"]:
        data["concepts"][key] = {
            "id": slugify(canonical_name),
            "name": canonical_name,
            "unit": unit.strip(),
            "unit_id": canonical_unit_id(unit) if unit else "",
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
    item = data["concepts"][key]
    relevance_map(item)
    if not item.get("name"):
        item["name"] = canonical_name
    if unit and not item.get("unit"):
        item["unit"] = unit.strip()
    if unit and not item.get("unit_id"):
        item["unit_id"] = canonical_unit_id(unit)
    return key, item


def uniq_strings(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = display_text(value)
        k = normalize(cleaned)
        if cleaned and k not in seen:
            seen.add(k)
            result.append(cleaned)
    return result


def cmd_upsert(args):
    course = Path(args.course)
    data = load(course)
    _, item = ensure(data, args.concept, args.unit or "")
    if args.unit is not None:
        resolved = resolve_unit(course, args.unit)
        item["unit_id"] = resolved.get("unit_id", "")
        item["unit"] = resolved.get("label") or resolved.get("unit_id") or args.unit.strip()
    if args.summary is not None:
        item["summary"] = args.summary.strip()
    if args.definition is not None:
        item["precise_definition"] = args.definition.strip()
    if args.prerequisite:
        item["prerequisites"] = uniq_strings(item.get("prerequisites", []) + args.prerequisite)
    if args.example:
        item["examples"] = uniq_strings(item.get("examples", []) + args.example)
    if args.trap:
        item["traps"] = uniq_strings(item.get("traps", []) + args.trap)
    item["last_updated"] = date.today().isoformat()
    save(course, data)
    print(json.dumps(item, ensure_ascii=False, indent=2))


def cmd_link(args):
    if args.type not in RELATION_TYPES:
        raise SystemExit(f"--type must be one of: {', '.join(sorted(RELATION_TYPES))}")
    course = Path(args.course)
    data = load(course)
    _, source = ensure(data, args.concept)
    ensure(data, args.target)
    rel = {"type": args.type, "target": display_text(args.target)}
    existing = {(r.get("type"), normalize(r.get("target", ""))) for r in source.get("relations", [])}
    if (rel["type"], normalize(rel["target"])) not in existing:
        source.setdefault("relations", []).append(rel)
    if args.type == "depends-on":
        source["prerequisites"] = uniq_strings(source.get("prerequisites", []) + [args.target])
    elif args.type == "prerequisite-of":
        _, target = ensure(data, args.target)
        target["prerequisites"] = uniq_strings(target.get("prerequisites", []) + [args.concept])
        target["last_updated"] = date.today().isoformat()
    source["last_updated"] = date.today().isoformat()
    save(course, data)
    print(json.dumps(source, ensure_ascii=False, indent=2))


def cmd_source(args):
    course = Path(args.course)
    data = load(course)
    _, item = ensure(data, args.concept)
    src = {"file": args.file.strip()}
    if args.pages:
        src["pages"] = args.pages.strip()
    if args.section:
        src["section"] = args.section.strip()
    if args.note:
        src["note"] = args.note.strip()
    if args.kind:
        src["kind"] = args.kind.strip()
    elif args.file.replace("\\", "/").lower().startswith("transcripciones/") or Path(args.file).suffix.lower() in {".srt", ".vtt"}:
        src["kind"] = "transcript"
    elif args.file.replace("\\", "/").lower().startswith("oficiales/"):
        src["kind"] = "official"
    if args.timestamp:
        src["timestamp"] = args.timestamp.strip()
    if args.speaker:
        src["speaker"] = args.speaker.strip()

    try:
        source_path = resolve_source(course, args.file, item.get("unit_id") or item.get("unit", ""))
    except LayoutError:
        source_path = None
    if source_path is not None:
        src["sha256"] = sha256(source_path)
    else:
        src["fingerprint_status"] = "source-file-not-found"

    def same_locator(x: dict) -> bool:
        return (
            normalize(x.get("file", "")) == normalize(src.get("file", ""))
            and normalize(x.get("pages", "")) == normalize(src.get("pages", ""))
            and normalize(x.get("section", "")) == normalize(src.get("section", ""))
            and normalize(x.get("timestamp", "")) == normalize(src.get("timestamp", ""))
        )

    sources = item.setdefault("sources", [])
    replaced = False
    for idx, existing in enumerate(sources):
        if same_locator(existing):
            sources[idx] = src
            replaced = True
            break
    if not replaced:
        sources.append(src)
    item["last_updated"] = date.today().isoformat()
    save(course, data)
    print(json.dumps(item, ensure_ascii=False, indent=2))


def cmd_error(args):
    course = Path(args.course)
    data = load(course)
    _, item = ensure(data, args.concept)
    today = date.today().isoformat()
    target = normalize(args.error)
    found = None
    for err in item.setdefault("recurring_errors", []):
        if normalize(err.get("text", "")) == target:
            found = err
            break
    if found:
        found["count"] = int(found.get("count", 1)) + 1
        found["last_seen"] = today
    else:
        item["recurring_errors"].append({"text": display_text(args.error), "count": 1, "last_seen": today})
    item["last_updated"] = today
    save(course, data)
    print(json.dumps(item, ensure_ascii=False, indent=2))


def cmd_relevance(args):
    if args.status not in RELEVANCE:
        raise SystemExit(f"--status must be one of: {', '.join(sorted(RELEVANCE))}")
    course = Path(args.course)
    data = load(course)
    _, item = ensure(data, args.concept)
    mapping = relevance_map(item)
    assessment_id = canonical_assessment(course, args.assessment)
    mapping[normalize(assessment_id)] = {
        "assessment_id": assessment_id,
        "status": args.status,
        "evidence": (args.evidence or "").strip(),
    }
    item["last_updated"] = date.today().isoformat()
    save(course, data)
    print(json.dumps(item, ensure_ascii=False, indent=2))


def stale_rows(course: Path, file: str = "") -> list[dict]:
    data = load(course)
    target_file = normalize(file) if file else None
    stale = []
    for item in data.get("concepts", {}).values():
        for src in item.get("sources", []):
            if target_file and normalize(src.get("file", "")) != target_file:
                continue
            try:
                path = resolve_source(course, src.get("file", ""), item.get("unit_id") or item.get("unit", ""))
            except LayoutError:
                path = None
            reason = None
            current_hash = None
            if path is None:
                reason = "source-missing"
            elif not src.get("sha256"):
                reason = "missing-fingerprint"
                current_hash = sha256(path)
            else:
                current_hash = sha256(path)
                if current_hash != src.get("sha256"):
                    reason = "source-changed"
            if reason:
                stale.append({
                    "concept": item.get("name"),
                    "unit": item.get("unit", ""),
                    "source": src.get("file"),
                    "pages": src.get("pages", ""),
                    "section": src.get("section", ""),
                    "timestamp": src.get("timestamp", ""),
                    "kind": src.get("kind", ""),
                    "reason": reason,
                    "stored_sha256": src.get("sha256"),
                    "current_sha256": current_hash,
                })
    return stale


def cmd_stale(args):
    course = Path(args.course)
    print(json.dumps(stale_rows(course, args.file or ""), ensure_ascii=False, indent=2))


def cmd_emphasis(args):
    course = Path(args.course)
    data = load(course)
    _, item = ensure(data, args.concept)
    signal = {
        "type": args.type,
        "text": display_text(args.text),
        "file": args.file.strip(),
        "confidence": args.confidence,
    }
    if args.timestamp:
        signal["timestamp"] = args.timestamp.strip()
    if args.speaker:
        signal["speaker"] = args.speaker.strip()
    if args.assessment:
        signal["assessment_id"] = canonical_assessment(course, args.assessment)
    target = (normalize(signal.get("file", "")), normalize(signal.get("timestamp", "")), normalize(signal.get("text", "")), signal.get("type"))
    rows = item.setdefault("teaching_signals", [])
    replaced = False
    for idx, existing in enumerate(rows):
        key = (normalize(existing.get("file", "")), normalize(existing.get("timestamp", "")), normalize(existing.get("text", "")), existing.get("type"))
        if key == target:
            rows[idx] = signal
            replaced = True
            break
    if not replaced:
        rows.append(signal)
    item["last_updated"] = date.today().isoformat()
    save(course, data)
    print(json.dumps(item, ensure_ascii=False, indent=2))


def progress_map(course: Path) -> dict:
    raw = load_registry(course, "progress")
    return raw.get("concepts", {})


def merged_card(course: Path, data: dict, key: str) -> dict:
    item = dict(data["concepts"][key])
    progress = progress_map(course)
    p = progress.get(normalize(item["name"]))
    item["progress"] = p or {
        "mastery": 0.0,
        "attempts": 0,
        "last_rating": None,
        "last_review": None,
        "next_review": None,
    }
    return item


def cmd_show(args):
    course = Path(args.course)
    data = load(course)
    if args.concept:
        key = find_key(data, args.concept)
        if key is None:
            raise SystemExit(f"Unknown concept: {args.concept}")
        print(json.dumps(merged_card(course, data, key), ensure_ascii=False, indent=2))
        return
    cards = [merged_card(course, data, key) for key in sorted(data.get("concepts", {}))]
    print(json.dumps(cards, ensure_ascii=False, indent=2))


def cmd_gaps(args):
    course = Path(args.course)
    data = load(course)
    progress = progress_map(course)
    gaps = []
    for _, item in data.get("concepts", {}).items():
        reasons = []
        if not item.get("summary"):
            reasons.append("missing-summary")
        if not item.get("precise_definition"):
            reasons.append("missing-definition")
        if not item.get("sources"):
            reasons.append("missing-source")
        for prereq in item.get("prerequisites", []):
            if find_key(data, prereq) is None:
                reasons.append(f"unknown-prerequisite:{prereq}")
        p = progress.get(normalize(item.get("name", "")))
        if not p:
            reasons.append("never-tested")
        elif float(p.get("mastery", 0)) < args.mastery_below:
            reasons.append("low-mastery")
        if reasons:
            gaps.append({"name": item.get("name"), "unit": item.get("unit", ""), "reasons": reasons})
    print(json.dumps(gaps, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("upsert")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--unit")
    p.add_argument("--summary")
    p.add_argument("--definition")
    p.add_argument("--prerequisite", action="append")
    p.add_argument("--example", action="append")
    p.add_argument("--trap", action="append")
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("link")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--type", required=True)
    p.add_argument("--target", required=True)
    p.set_defaults(func=cmd_link)

    p = sub.add_parser("source")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--pages")
    p.add_argument("--section")
    p.add_argument("--note")
    p.add_argument("--kind", choices=["official", "transcript", "student-note", "external", "other"])
    p.add_argument("--timestamp", help="Transcript time or interval, e.g. 00:42:17-00:48:03")
    p.add_argument("--speaker")
    p.set_defaults(func=cmd_source)

    p = sub.add_parser("emphasis")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--timestamp")
    p.add_argument("--speaker")
    p.add_argument("--type", required=True, choices=["important", "exam-cue", "excluded-cue", "common-error", "question-pattern", "example", "definition", "other"])
    p.add_argument("--text", required=True)
    p.add_argument("--confidence", default="ambiguous", choices=["explicit", "strong-cue", "ambiguous"])
    p.add_argument("--assessment", help="Assessment id/name only when the signal refers to a concrete assessment")
    p.set_defaults(func=cmd_emphasis)

    p = sub.add_parser("error")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--error", required=True)
    p.set_defaults(func=cmd_error)

    p = sub.add_parser("relevance")
    p.add_argument("--course", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--assessment", required=True, help="Assessment id/name this relevance applies to")
    p.add_argument("--status", required=True, choices=sorted(RELEVANCE))
    p.add_argument("--evidence")
    p.set_defaults(func=cmd_relevance)

    p = sub.add_parser("stale")
    p.add_argument("--course", required=True)
    p.add_argument("--file", help="Optional source path relative to fuentes/")
    p.set_defaults(func=cmd_stale)

    p = sub.add_parser("show")
    p.add_argument("--course", required=True)
    p.add_argument("--concept")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("gaps")
    p.add_argument("--course", required=True)
    p.add_argument("--mastery-below", type=float, default=0.7)
    p.set_defaults(func=cmd_gaps)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
