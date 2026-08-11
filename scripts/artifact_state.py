#!/usr/bin/env python3
"""Track generated study artifacts against the academic/concept state they depend on.

This tool is deterministic. It never calls an LLM. Artifacts are marked after an
AI action generates them. Their current/stale status is computed from hashes of
academic.json and the relevant concept subset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .course_layout import artifact_directories, has_unit_layout, load_registry, unit_ids
    from .unit_identity import normalize as normalize_unit_text, resolve_unit, record_unit_id
else:
    from course_layout import artifact_directories, has_unit_layout, load_registry, unit_ids
    from unit_identity import normalize as normalize_unit_text, resolve_unit, record_unit_id

MANIFEST_VERSION = 1
# Bump whenever the student-facing generation contract changes in a way that
# should force summaries/guides/reviews/questions to be regenerated.
ARTIFACT_CONTRACT_VERSION = 9
VISUAL_ARTIFACT_TYPES = {"summary", "guide", "rapid-review"}
GENERATED_DIRS = ("resumenes", "preguntas", "simulacros")


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return " ".join(value.split())


def stable_json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_path(course: Path) -> Path:
    return course / ".study" / "artifacts.json"


def load_manifest(course: Path) -> dict[str, Any]:
    data = read_json(manifest_path(course), {"version": MANIFEST_VERSION, "artifacts": {}})
    data.setdefault("version", MANIFEST_VERSION)
    data.setdefault("artifacts", {})
    return data


def save_manifest(course: Path, data: dict[str, Any]) -> None:
    p = manifest_path(course)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def academic_fingerprint(course: Path) -> str:
    data = read_json(course / "academico" / "academic.json", {})
    return stable_json_hash(data)


def scoped_figures(course: Path, scope: str) -> dict[str, Any]:
    data = load_registry(course, "figures")
    figures = data.get("figures", {}) if isinstance(data, dict) else {}
    target = normalize(scope)
    if not target:
        return figures

    target_unit_id = resolve_unit(course, scope).get("unit_id", "")
    selected: dict[str, Any] = {}
    for key, item in figures.items():
        if not isinstance(item, dict):
            continue
        item_unit_id = record_unit_id(course, item)
        concepts = [normalize(x) for x in item.get("concepts", []) if x]
        fid = normalize(item.get("id", key))
        # Unit scoping is machine-id based. Human ids/concepts remain supported
        # for explicit topic/figure scopes, but never substitute for unit identity.
        if target_unit_id and item_unit_id and target_unit_id == item_unit_id:
            selected[key] = item
        elif target in {fid, normalize(key)}:
            selected[key] = item
        elif any(target == c or target in c or c in target for c in concepts if c):
            selected[key] = item
    return selected


def figure_fingerprint(course: Path, scope: str) -> tuple[str, int]:
    figures = scoped_figures(course, scope)
    return stable_json_hash(figures), len(figures)


def scoped_topics(course: Path, scope: str) -> dict[str, Any]:
    """Return observed topics without ever constructing a mixed global registry."""
    target_unit_id = resolve_unit(course, scope).get("unit_id", "") if scope else ""
    if has_unit_layout(course):
        if target_unit_id:
            return load_registry(course, "topics", target_unit_id)
        return {
            unit_id: load_registry(course, "topics", unit_id)
            for unit_id in unit_ids(course)
        }
    return read_json(
        course / "conocimiento" / "topics.json",
        {"version": 1, "unit_id": target_unit_id, "topics": {}, "unassigned_concept_ids": []},
    )


def topic_fingerprint(course: Path, scope: str) -> tuple[str, int, int]:
    data = scoped_topics(course, scope)
    if has_unit_layout(course) and not scope:
        count = sum(len(row.get("topics", {})) for row in data.values() if isinstance(row, dict))
        unassigned = sum(len(row.get("unassigned_concept_ids", [])) for row in data.values() if isinstance(row, dict))
    else:
        count = len(data.get("topics", {})) if isinstance(data, dict) else 0
        unassigned = len(data.get("unassigned_concept_ids", [])) if isinstance(data, dict) else 0
    return stable_json_hash(data), count, unassigned


def scoped_concepts(course: Path, scope: str) -> tuple[dict[str, Any], str]:
    data = load_registry(course, "concepts")
    concepts = data.get("concepts", {}) if isinstance(data, dict) else {}
    target = normalize(scope)
    if not target:
        return concepts, "all"

    target_unit_id = resolve_unit(course, scope).get("unit_id", "")
    selected: dict[str, Any] = {}
    for key, item in concepts.items():
        if not isinstance(item, dict):
            continue
        name = normalize(item.get("name", ""))
        cid = normalize(item.get("id", ""))
        item_unit_id = record_unit_id(course, item)
        if target_unit_id and item_unit_id and target_unit_id == item_unit_id:
            selected[key] = item
        elif target in {name, cid, normalize(key)}:
            selected[key] = item

    if selected:
        # Include transitive prerequisite/relation dependencies even when they live
        # in another unit. A Unit 2 summary that depends on a changed Unit 1
        # concept must become stale.
        by_name: dict[str, str] = {}
        for key, item in concepts.items():
            if not isinstance(item, dict):
                continue
            for candidate in (key, item.get("name", ""), item.get("id", "")):
                if candidate:
                    by_name[normalize(candidate)] = key
        queue = list(selected)
        seen = set(selected)
        while queue:
            key = queue.pop(0)
            item = concepts.get(key, {})
            refs = list(item.get("prerequisites", []))
            refs += [
                relation.get("target", "")
                for relation in item.get("relations", [])
                if isinstance(relation, dict) and relation.get("type") == "depends-on"
            ]
            for ref in refs:
                target_key = by_name.get(normalize(ref))
                if target_key and target_key not in seen:
                    seen.add(target_key)
                    selected[target_key] = concepts[target_key]
                    queue.append(target_key)
        return selected, "matched+dependencies"
    return concepts, "all-fallback"


def concept_fingerprint(course: Path, scope: str) -> tuple[str, str, int]:
    concepts, mode = scoped_concepts(course, scope)
    return stable_json_hash(concepts), mode, len(concepts)


def design_fingerprint() -> str:
    theme = Path(__file__).resolve().parents[1] / "assets" / "study-theme.css"
    if not theme.exists():
        return "missing"
    return hashlib.sha256(theme.read_bytes()).hexdigest()


def current_fingerprints(course: Path, scope: str, artifact_type: str = "") -> dict[str, Any]:
    c_hash, mode, count = concept_fingerprint(course, scope)
    t_hash, t_count, unassigned_count = topic_fingerprint(course, scope)
    f_hash, f_count = figure_fingerprint(course, scope)
    result = {
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "academic_sha256": academic_fingerprint(course),
        "concepts_sha256": c_hash,
        "topics_sha256": t_hash,
        "figures_sha256": f_hash,
        "concept_scope_mode": mode,
        "concept_count": count,
        "topic_count": t_count,
        "unassigned_concept_count": unassigned_count,
        "figure_count": f_count,
    }
    if artifact_type in VISUAL_ARTIFACT_TYPES:
        result["design_sha256"] = design_fingerprint()
    return result


def safe_artifact_path(course: Path, value: str) -> tuple[Path, str]:
    raw = Path(value)
    path = raw if raw.is_absolute() else course / raw
    path = path.resolve()
    course_resolved = course.resolve()
    if not path.is_relative_to(course_resolved):
        raise SystemExit("Artifact must live inside the course folder")
    rel = path.relative_to(course_resolved).as_posix()
    return path, rel


def artifact_status(course: Path, rel: str, entry: dict[str, Any]) -> dict[str, Any]:
    path = course / rel
    scope = str(entry.get("scope", ""))
    current = current_fingerprints(course, scope, str(entry.get("type", "")))
    reasons: list[str] = []
    if not path.exists():
        reasons.append("artifact-missing")
    if entry.get("artifact_contract_version") != current["artifact_contract_version"]:
        reasons.append("artifact-contract-changed")
    if entry.get("academic_sha256") != current["academic_sha256"]:
        reasons.append("academic-context-changed")
    if entry.get("concepts_sha256") != current["concepts_sha256"]:
        reasons.append("knowledge-changed")
    if entry.get("topics_sha256") != current["topics_sha256"]:
        reasons.append("topic-knowledge-changed")
    if entry.get("figures_sha256") != current["figures_sha256"]:
        reasons.append("visual-knowledge-changed")
    if "design_sha256" in current and entry.get("design_sha256") != current["design_sha256"]:
        reasons.append("design-system-changed")
    return {
        "file": rel,
        "type": entry.get("type", "unknown"),
        "scope": scope,
        "generated_at": entry.get("generated_at"),
        "stale": bool(reasons),
        "reasons": reasons,
        "concept_scope_mode": current["concept_scope_mode"],
        "concept_count": current["concept_count"],
        "topic_count": current["topic_count"],
        "unassigned_concept_count": current["unassigned_concept_count"],
        "figure_count": current["figure_count"],
    }


def mark_artifact(course: Path, file: str, artifact_type: str, scope: str = "") -> dict[str, Any]:
    """Record an artifact using the same deterministic core used by the CLI/MCP."""
    try:
        path, rel = safe_artifact_path(course, file)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    if not path.exists() or not path.is_file():
        raise ValueError(f"Artifact does not exist: {path}")
    unit_id = resolve_unit(course, scope).get("unit_id", "") if scope else ""
    if unit_id and has_unit_layout(course):
        expected = (course / "unidades" / unit_id).resolve()
        if not path.is_relative_to(expected):
            raise ValueError(
                f"El artefacto de {unit_id} debe vivir dentro de unidades/{unit_id}/"
            )
    manifest = load_manifest(course)
    fp = current_fingerprints(course, scope or "", artifact_type)
    manifest["artifacts"][rel] = {
        "type": artifact_type,
        "scope": scope or "",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **fp,
    }
    save_manifest(course, manifest)
    return artifact_status(course, rel, manifest["artifacts"][rel])


def cmd_mark(args: argparse.Namespace) -> None:
    course = Path(args.course)
    try:
        result = mark_artifact(course, args.file, args.type, args.scope or "")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


def generated_files(course: Path) -> set[str]:
    rows: set[str] = set()
    for d in artifact_directories(course):
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if "_source" in p.parts:
                continue
            if p.is_file() and p.suffix.lower() in {".md", ".html", ".txt", ".json"}:
                rows.add(p.relative_to(course).as_posix())
    return rows


def all_status(course: Path) -> list[dict[str, Any]]:
    manifest = load_manifest(course)
    rows = [artifact_status(course, rel, entry) for rel, entry in sorted(manifest["artifacts"].items())]
    tracked = set(manifest["artifacts"])
    for rel in sorted(generated_files(course) - tracked):
        rows.append({
            "file": rel,
            "type": "untracked",
            "scope": "",
            "generated_at": None,
            "stale": True,
            "reasons": ["untracked-artifact"],
            "concept_scope_mode": "unknown",
            "concept_count": None,
        })
    return rows


def cmd_status(args: argparse.Namespace) -> None:
    course = Path(args.course)
    rows = all_status(course)
    if args.file:
        _, rel = safe_artifact_path(course, args.file)
        rows = [row for row in rows if row["file"] == rel]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def cmd_clean_missing(args: argparse.Namespace) -> None:
    course = Path(args.course)
    manifest = load_manifest(course)
    removed = []
    for rel in list(manifest["artifacts"]):
        if not (course / rel).exists():
            removed.append(rel)
            manifest["artifacts"].pop(rel, None)
    save_manifest(course, manifest)
    print(json.dumps({"removed": removed}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Track generated academic artifacts and stale state")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("mark", help="Record an artifact against the current academic/knowledge state")
    p.add_argument("--course", required=True)
    p.add_argument("--file", required=True, help="Path relative to course, e.g. resumenes/unidad-1-resumen.md")
    p.add_argument("--type", required=True, choices=["summary", "guide", "rapid-review", "questions", "mock-exam", "other"])
    p.add_argument("--scope", default="", help="Unit/topic/assessment scope used to generate the artifact")
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("status", help="Show current/stale state of tracked artifacts")
    p.add_argument("--course", required=True)
    p.add_argument("--file")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("clean-missing", help="Remove manifest entries for files that no longer exist")
    p.add_argument("--course", required=True)
    p.set_defaults(func=cmd_clean_missing)
    return ap


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
