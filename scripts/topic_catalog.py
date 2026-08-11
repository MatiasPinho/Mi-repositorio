#!/usr/bin/env python3
"""Canonical observed-topic catalog for one V4 unit.

The catalog groups concepts after semantic ingestion.  It deliberately keeps
the official syllabus topics in ``academic.json`` separate, and stores no
mastery of its own: topic progress is always derived from concept progress.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __package__:
    from .course_layout import (
        LayoutError,
        academic_units,
        canonical_unit_id,
        has_unit_layout,
        load_registry,
        read_json,
        save_registry,
    )
    from .unit_identity import record_unit_id, stable_unit_id_from_row
else:
    from course_layout import (
        LayoutError,
        academic_units,
        canonical_unit_id,
        has_unit_layout,
        load_registry,
        read_json,
        save_registry,
    )
    from unit_identity import record_unit_id, stable_unit_id_from_row

CATALOG_VERSION = 1


class TopicCatalogError(RuntimeError):
    pass


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return " ".join(text.split())


def slugify(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "tema"


def empty_catalog(unit_id: str) -> dict[str, Any]:
    return {
        "version": CATALOG_VERSION,
        "unit_id": unit_id,
        "topics": {},
        "unassigned_concept_ids": [],
    }


def _unit_row(course: Path, unit_id: str) -> dict[str, Any] | None:
    for row in academic_units(course):
        if stable_unit_id_from_row(row) == unit_id:
            return row
    return None


def declared_topics(course: Path, unit: str) -> list[str]:
    unit_id = canonical_unit_id(course, unit)
    row = _unit_row(course, unit_id)
    values = row.get("topics", []) if isinstance(row, dict) else []
    return [str(value) for value in values if isinstance(value, str) and value.strip()]


def _concept_index(course: Path, unit: str) -> tuple[dict[str, str], dict[str, Any]]:
    unit_id = canonical_unit_id(course, unit)
    graph = load_registry(course, "concepts", unit_id)
    rows = graph.get("concepts", {}) if isinstance(graph, dict) else {}
    if not isinstance(rows, dict):
        raise TopicCatalogError("concepts.json debe contener un objeto 'concepts'")
    aliases: dict[str, str] = {}
    canonical: dict[str, Any] = {}
    only_unit = len(academic_units(course)) == 1
    for key, item in rows.items():
        if not isinstance(item, dict):
            raise TopicCatalogError(f"Concepto inválido en concepts.json: {key}")
        if not has_unit_layout(course):
            owner = record_unit_id(course, item)
            if owner != unit_id and not (not owner and only_unit):
                continue
        concept_id = str(item.get("id") or key).strip()
        if not concept_id:
            raise TopicCatalogError(f"Concepto sin id estable: {key}")
        if concept_id in canonical and canonical[concept_id] != item:
            raise TopicCatalogError(f"Id de concepto duplicado en la unidad: {concept_id}")
        canonical[concept_id] = item
        for alias in (key, concept_id):
            token = normalize(alias)
            previous = aliases.get(token)
            if previous and previous != concept_id:
                raise TopicCatalogError(f"Alias ambiguo de concepto: {alias}")
            aliases[token] = concept_id
    return aliases, canonical


def _canonical_concept_id(value: Any, aliases: dict[str, str]) -> str:
    return aliases.get(normalize(value), "")


def _dedupe_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        token = normalize(text)
        if text and token not in seen:
            seen.add(token)
            result.append(text)
    return result


def _dedupe_json(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        token = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if token not in seen:
            seen.add(token)
            result.append(value)
    return result


def _canonical_declared_matches(
    values: Any,
    official: list[str],
    *,
    topic_name: str,
) -> list[str]:
    if not isinstance(values, list):
        raise TopicCatalogError(f"declared_matches debe ser una lista en el tema '{topic_name}'")
    by_name = {normalize(value): value for value in official}
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise TopicCatalogError(f"declared_matches contiene un valor inválido en '{topic_name}'")
        match = by_name.get(normalize(value))
        if match is None:
            raise TopicCatalogError(
                f"El tema observado '{topic_name}' referencia un tema no declarado en su unidad: {value}"
            )
        if match not in result:
            result.append(match)
    return result


def _legacy_catalog(course: Path, unit_id: str) -> dict[str, Any]:
    """Read an optional V3 root catalog as a compatibility input only."""
    legacy_path = course / "conocimiento" / "topics.json"
    data = read_json(legacy_path, empty_catalog(unit_id))
    rows = data.get("topics", {}) if isinstance(data, dict) else {}
    if not isinstance(rows, dict):
        return empty_catalog(unit_id)
    only_unit = len(academic_units(course)) == 1
    selected: dict[str, Any] = {}
    for key, item in rows.items():
        if not isinstance(item, dict):
            continue
        owner = record_unit_id(course, item)
        if owner == unit_id or (not owner and only_unit):
            selected[str(key)] = item
    aliases, concepts = _concept_index(course, unit_id)
    if not legacy_path.exists():
        return {
            "version": CATALOG_VERSION,
            "unit_id": unit_id,
            "topics": {},
            "unassigned_concept_ids": sorted(concepts),
        }
    unassigned = []
    for value in data.get("unassigned_concept_ids", []) if isinstance(data, dict) else []:
        concept_id = _canonical_concept_id(value, aliases)
        if concept_id in concepts and concept_id not in unassigned:
            unassigned.append(concept_id)
    return {
        "version": int(data.get("version", CATALOG_VERSION) or CATALOG_VERSION),
        "unit_id": unit_id,
        "topics": selected,
        "unassigned_concept_ids": unassigned,
    }


def load_catalog(course: Path, unit: str) -> dict[str, Any]:
    unit_id = canonical_unit_id(course, unit)
    if has_unit_layout(course):
        data = load_registry(course, "topics", unit_id)
        result = dict(data) if isinstance(data, dict) else empty_catalog(unit_id)
        result.setdefault("version", CATALOG_VERSION)
        result.setdefault("unit_id", unit_id)
        result.setdefault("topics", {})
        result.setdefault("unassigned_concept_ids", [])
        return result
    return _legacy_catalog(course, unit_id)


def validate_catalog(
    course: Path,
    unit: str,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unit_id = canonical_unit_id(course, unit)
    aliases, concepts = _concept_index(course, unit_id)
    actual_ids = set(concepts)
    data = catalog if catalog is not None else load_catalog(course, unit_id)
    issues: list[dict[str, Any]] = []

    def issue(code: str, message: str, **extra: Any) -> None:
        issues.append({"severity": "error", "code": code, "message": message, **extra})

    if not isinstance(data, dict):
        issue("invalid-catalog", "topics.json debe contener un objeto JSON")
        data = empty_catalog(unit_id)
    if str(data.get("unit_id", "")) != unit_id:
        issue("unit-mismatch", f"topics.json debe pertenecer a {unit_id}")
    rows = data.get("topics", {})
    if not isinstance(rows, dict):
        issue("invalid-topics", "topics.json debe contener un objeto 'topics'")
        rows = {}
    unassigned = data.get("unassigned_concept_ids", [])
    if not isinstance(unassigned, list):
        issue("invalid-unassigned", "unassigned_concept_ids debe ser una lista")
        unassigned = []

    declared = declared_topics(course, unit_id)
    declared_tokens = {normalize(value): value for value in declared}
    owners: dict[str, str] = {}
    for key, item in rows.items():
        if not isinstance(item, dict):
            issue("invalid-topic", f"El tema '{key}' debe ser un objeto", topic_id=str(key))
            continue
        topic_id = str(item.get("id", ""))
        if topic_id != str(key):
            issue("topic-id-mismatch", f"La clave '{key}' no coincide con id '{topic_id}'", topic_id=str(key))
        if str(item.get("unit_id", "")) != unit_id:
            issue("topic-unit-mismatch", f"El tema '{key}' no pertenece a {unit_id}", topic_id=str(key))
        if not str(item.get("name", "")).strip():
            issue("topic-name-missing", f"El tema '{key}' no tiene name", topic_id=str(key))
        for field in ("aliases", "concept_ids", "declared_matches", "evidence"):
            if not isinstance(item.get(field), list):
                issue("topic-field-invalid", f"{field} debe ser una lista en '{key}'", topic_id=str(key), field=field)
        for field in ("aliases", "concept_ids", "declared_matches"):
            values = item.get(field, [])
            if isinstance(values, list) and any(not isinstance(value, str) or not value.strip() for value in values):
                issue("topic-string-invalid", f"{field} sólo admite strings no vacíos en '{key}'", topic_id=str(key), field=field)
        for match in item.get("declared_matches", []) if isinstance(item.get("declared_matches"), list) else []:
            if isinstance(match, str):
                canonical = declared_tokens.get(normalize(match))
                if canonical is None:
                    issue(
                        "declared-match-missing",
                        f"'{match}' no existe en academic.json -> units[].topics para {unit_id}",
                        topic_id=str(key),
                    )
                elif match != canonical:
                    issue(
                        "declared-match-not-canonical",
                        f"'{match}' debe conservar la forma declarada exacta '{canonical}'",
                        topic_id=str(key),
                    )
        for value in item.get("concept_ids", []) if isinstance(item.get("concept_ids"), list) else []:
            concept_id = _canonical_concept_id(value, aliases)
            if not concept_id or concept_id not in actual_ids:
                issue("concept-missing", f"El concepto '{value}' no existe en concepts.json", topic_id=str(key), concept_id=value)
                continue
            if concept_id in owners:
                issue(
                    "concept-multiple-topics",
                    f"El concepto '{concept_id}' tiene más de un tema principal",
                    concept_id=concept_id,
                    topic_ids=[owners[concept_id], str(key)],
                )
            else:
                owners[concept_id] = str(key)

    explicit_unassigned: list[str] = []
    for value in unassigned:
        concept_id = _canonical_concept_id(value, aliases)
        if not concept_id or concept_id not in actual_ids:
            issue("unassigned-concept-missing", f"El concepto sin tema '{value}' no existe", concept_id=value)
            continue
        if concept_id in explicit_unassigned:
            issue("unassigned-duplicate", f"El concepto '{concept_id}' está repetido en unassigned_concept_ids", concept_id=concept_id)
            continue
        explicit_unassigned.append(concept_id)
        if concept_id in owners:
            issue(
                "concept-assigned-and-unassigned",
                f"El concepto '{concept_id}' figura asignado y sin tema",
                concept_id=concept_id,
                topic_id=owners[concept_id],
            )

    missing = sorted(actual_ids - set(owners) - set(explicit_unassigned))
    if missing:
        issue(
            "concept-assignment-missing",
            "Hay conceptos sin tema principal y no declarados como unassigned",
            concept_ids=missing,
        )
    return {
        "ok": not issues,
        "unit_id": unit_id,
        "topic_count": len(rows),
        "concept_count": len(actual_ids),
        "unassigned_concept_ids": sorted(explicit_unassigned),
        "missing_assignment_concept_ids": missing,
        "issues": issues,
    }


def _proposal_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = []
        for key, item in value.items():
            if not isinstance(item, dict):
                raise TopicCatalogError(f"Propuesta de tema inválida: {key}")
            row = dict(item)
            row.setdefault("id", str(key))
            rows.append(row)
    else:
        raise TopicCatalogError("La propuesta debe contener una lista u objeto 'topics'")
    if any(not isinstance(row, dict) for row in rows):
        raise TopicCatalogError("Cada propuesta de tema debe ser un objeto")
    return rows


def reconcile_topics(
    course: Path,
    unit: str,
    proposal: dict[str, Any] | None = None,
    *,
    write: bool = False,
) -> dict[str, Any]:
    """Upsert semantic topic proposals while preserving stable existing ids."""
    if not has_unit_layout(course):
        raise TopicCatalogError("La reconciliación de temas requiere layout V4; sincronizá o migrá la materia")
    unit_id = canonical_unit_id(course, unit)
    aliases, concepts = _concept_index(course, unit_id)
    actual_ids = set(concepts)
    official = declared_topics(course, unit_id)
    current = load_catalog(course, unit_id)
    current_rows = current.get("topics", {}) if isinstance(current.get("topics"), dict) else {}
    rows: dict[str, dict[str, Any]] = {}
    removed_missing: list[str] = []

    for key, item in current_rows.items():
        if not isinstance(item, dict):
            raise TopicCatalogError(f"Tema existente inválido: {key}")
        topic_id = str(item.get("id") or key).strip()
        if topic_id != str(key):
            raise TopicCatalogError(f"La clave del tema '{key}' no coincide con su id '{topic_id}'")
        name = str(item.get("name", "")).strip()
        if not name:
            raise TopicCatalogError(f"Tema existente sin nombre: {topic_id}")
        for field in ("aliases", "concept_ids", "declared_matches", "evidence"):
            if not isinstance(item.get(field, []), list):
                raise TopicCatalogError(f"{field} debe ser una lista en el tema existente '{topic_id}'")
        concept_ids: list[str] = []
        for value in item.get("concept_ids", []):
            concept_id = _canonical_concept_id(value, aliases)
            if concept_id in actual_ids:
                if concept_id not in concept_ids:
                    concept_ids.append(concept_id)
            else:
                removed_missing.append(str(value))
        row = dict(item)
        row.update({
            "id": topic_id,
            "unit_id": unit_id,
            "name": name,
            "aliases": _dedupe_strings(item.get("aliases", [])),
            "concept_ids": concept_ids,
            "declared_matches": _dedupe_strings(item.get("declared_matches", [])),
            "evidence": _dedupe_json(item.get("evidence", [])),
        })
        rows[topic_id] = row

    proposed = proposal or {"topics": []}
    if not isinstance(proposed, dict):
        raise TopicCatalogError("La propuesta de reconciliación debe ser un objeto JSON")
    candidates = _proposal_rows(proposed.get("topics", []))
    used_targets: set[str] = set()
    created: list[str] = []
    reused: list[str] = []
    proposal_assignments: dict[str, list[str]] = {}

    def semantic_tokens(item: dict[str, Any]) -> set[str]:
        values = [item.get("name", ""), *item.get("aliases", [])]
        return {normalize(value) for value in values if normalize(value)}

    for candidate in candidates:
        name = str(candidate.get("name", "")).strip()
        if not name:
            raise TopicCatalogError("Cada propuesta de tema requiere name")
        for field in ("aliases", "concept_ids", "declared_matches", "evidence"):
            if field in candidate and not isinstance(candidate[field], list):
                raise TopicCatalogError(f"{field} debe ser una lista en la propuesta '{name}'")
        requested_id = str(candidate.get("id", "")).strip()
        target_id = requested_id if requested_id in rows else ""
        if not target_id:
            candidate_tokens = semantic_tokens(candidate)
            lexical = [topic_id for topic_id, item in rows.items() if candidate_tokens & semantic_tokens(item)]
            if len(lexical) > 1:
                raise TopicCatalogError(
                    f"La propuesta '{name}' coincide con varios temas existentes; indicá uno de sus ids: {', '.join(lexical)}"
                )
            if lexical:
                target_id = lexical[0]
        if not target_id:
            base = slugify(requested_id or name)
            target_id = base
            suffix = 2
            while target_id in rows:
                target_id = f"{base}-{suffix}"
                suffix += 1
            rows[target_id] = {
                "id": target_id,
                "unit_id": unit_id,
                "name": name,
                "aliases": [],
                "concept_ids": [],
                "declared_matches": [],
                "evidence": [],
            }
            created.append(target_id)
        else:
            reused.append(target_id)
        if target_id in used_targets:
            raise TopicCatalogError(f"Más de una propuesta intenta actualizar el tema '{target_id}'")
        used_targets.add(target_id)

        row = rows[target_id]
        old_name = str(row.get("name", "")).strip()
        merged_aliases = list(row.get("aliases", [])) + list(candidate.get("aliases", []))
        if old_name and normalize(old_name) != normalize(name):
            merged_aliases.append(old_name)
        declared = row.get("declared_matches", [])
        if "declared_matches" in candidate:
            declared = _canonical_declared_matches(candidate["declared_matches"], official, topic_name=name)
        evidence = _dedupe_json(list(row.get("evidence", [])) + list(candidate.get("evidence", [])))
        row.update({
            "id": target_id,
            "unit_id": unit_id,
            "name": name,
            "aliases": [alias for alias in _dedupe_strings(merged_aliases) if normalize(alias) != normalize(name)],
            "declared_matches": declared,
            "evidence": evidence,
        })
        requested_concepts = candidate.get("concept_ids", [])
        if not isinstance(requested_concepts, list):
            raise TopicCatalogError(f"concept_ids debe ser una lista en el tema '{name}'")
        canonical_ids: list[str] = []
        for value in requested_concepts:
            concept_id = _canonical_concept_id(value, aliases)
            if not concept_id or concept_id not in actual_ids:
                raise TopicCatalogError(f"El concepto '{value}' no existe en concepts.json de {unit_id}")
            if concept_id not in canonical_ids:
                canonical_ids.append(concept_id)
        proposal_assignments[target_id] = canonical_ids

    raw_unassigned = proposed.get("unassigned_concept_ids", [])
    if not isinstance(raw_unassigned, list):
        raise TopicCatalogError("unassigned_concept_ids debe ser una lista")
    explicit_unassigned: list[str] = []
    for value in raw_unassigned:
        concept_id = _canonical_concept_id(value, aliases)
        if not concept_id or concept_id not in actual_ids:
            raise TopicCatalogError(f"El concepto sin tema '{value}' no existe en concepts.json de {unit_id}")
        if concept_id not in explicit_unassigned:
            explicit_unassigned.append(concept_id)

    unassigned: list[str] = []
    for value in current.get("unassigned_concept_ids", []):
        concept_id = _canonical_concept_id(value, aliases)
        if concept_id in actual_ids and concept_id not in unassigned:
            unassigned.append(concept_id)
        elif concept_id not in actual_ids:
            removed_missing.append(str(value))

    touched = set(explicit_unassigned)
    for values in proposal_assignments.values():
        touched.update(values)
    for concept_id in touched:
        unassigned = [value for value in unassigned if value != concept_id]
        for row in rows.values():
            row["concept_ids"] = [value for value in row.get("concept_ids", []) if value != concept_id]
    for target_id, values in proposal_assignments.items():
        rows[target_id]["concept_ids"] = sorted(set(rows[target_id].get("concept_ids", [])) | set(values))
    unassigned.extend(value for value in explicit_unassigned if value not in unassigned)

    owners: dict[str, str] = {}
    for topic_id, row in rows.items():
        normalized_ids: list[str] = []
        for concept_id in row.get("concept_ids", []):
            if concept_id in owners:
                raise TopicCatalogError(
                    f"El concepto '{concept_id}' conserva dos temas principales: {owners[concept_id]} y {topic_id}"
                )
            owners[concept_id] = topic_id
            normalized_ids.append(concept_id)
        row["concept_ids"] = sorted(normalized_ids)
    new_unassigned = sorted(actual_ids - set(owners) - set(unassigned))
    unassigned = sorted(set(unassigned) | set(new_unassigned))

    result_catalog = {
        "version": CATALOG_VERSION,
        "unit_id": unit_id,
        "topics": dict(sorted(rows.items())),
        "unassigned_concept_ids": unassigned,
    }
    validation = validate_catalog(course, unit_id, result_catalog)
    if not validation["ok"]:
        raise TopicCatalogError("Catálogo reconciliado inválido: " + "; ".join(row["message"] for row in validation["issues"]))
    if write:
        try:
            save_registry(course, "topics", result_catalog, unit_id)
        except LayoutError as exc:
            raise TopicCatalogError(str(exc)) from exc
    return {
        "ok": True,
        "written": write,
        "unit_id": unit_id,
        "created_topic_ids": created,
        "reused_topic_ids": sorted(set(reused)),
        "newly_unassigned_concept_ids": new_unassigned,
        "removed_missing_concept_ids": sorted(set(removed_missing)),
        "catalog": result_catalog,
        "validation": validation,
    }


def _progress_index(rows: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key, item in rows.items():
        if not isinstance(item, dict):
            continue
        for alias in (key, item.get("id", ""), item.get("name", "")):
            token = normalize(alias)
            if token:
                result.setdefault(token, item)
    return result


def topic_progress(course: Path, unit: str) -> dict[str, Any]:
    unit_id = canonical_unit_id(course, unit)
    catalog = load_catalog(course, unit_id)
    validation = validate_catalog(course, unit_id, catalog)
    if not validation["ok"]:
        raise TopicCatalogError("No se puede derivar progreso desde un topics.json inválido")
    _aliases, concepts = _concept_index(course, unit_id)
    progress_data = load_registry(course, "progress", unit_id)
    progress_rows = progress_data.get("concepts", {}) if isinstance(progress_data, dict) else {}
    progress = _progress_index(progress_rows if isinstance(progress_rows, dict) else {})

    def metric(concept_ids: list[str]) -> dict[str, Any]:
        tracked: list[dict[str, Any]] = []
        tested = 0
        for concept_id in concept_ids:
            concept = concepts.get(concept_id, {})
            row = None
            for alias in (concept_id, concept.get("id", ""), concept.get("name", "")):
                row = progress.get(normalize(alias))
                if row is not None:
                    break
            if row is not None:
                tracked.append(row)
                if int(row.get("attempts", 0) or 0) > 0:
                    tested += 1
        total = len(concept_ids)
        average = None
        if tracked:
            average = sum(float(row.get("mastery", 0) or 0) for row in tracked) / len(tracked)
        return {
            "concept_count": total,
            "tracked_concept_count": len(tracked),
            "tested_concept_count": tested,
            "tested_coverage": tested / total if total else None,
            "average_mastery": average,
        }

    topics: dict[str, Any] = {}
    for topic_id, item in catalog["topics"].items():
        topics[topic_id] = {
            "topic_id": topic_id,
            "name": item.get("name", topic_id),
            **metric(item.get("concept_ids", [])),
        }
    return {
        "unit_id": unit_id,
        "topics": topics,
        "unassigned": {
            "concept_ids": catalog["unassigned_concept_ids"],
            **metric(catalog["unassigned_concept_ids"]),
        },
    }


def _resolve_course(value: str) -> Path:
    from study import resolve_course

    return resolve_course(value, interactive=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("--course", required=True)
    reconcile.add_argument("--unit", required=True)
    reconcile.add_argument("--input", help="JSON de propuestas; si se omite sólo normaliza y explicita unassigned")
    reconcile.add_argument("--write", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--course", required=True)
    validate.add_argument("--unit", required=True)
    progress = sub.add_parser("progress")
    progress.add_argument("--course", required=True)
    progress.add_argument("--unit", required=True)
    args = parser.parse_args()
    try:
        course = _resolve_course(args.course)
        if args.command == "reconcile":
            proposal = read_json(Path(args.input), {}) if args.input else None
            result = reconcile_topics(course, args.unit, proposal, write=args.write)
        elif args.command == "validate":
            result = validate_catalog(course, args.unit)
        else:
            result = topic_progress(course, args.unit)
    except (TopicCatalogError, LayoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == "validate" and not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
