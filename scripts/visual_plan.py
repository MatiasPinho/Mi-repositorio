#!/usr/bin/env python3
"""Validate and materialize planned study figures before prose drafting."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
from scripts.figure_assets import derived_key, load_registry  # noqa: E402
from scripts.sketch_figure import SketchSpecError, generate_and_register, validate_spec  # noqa: E402
from scripts.unit_identity import record_unit_id, resolve_unit  # noqa: E402


SELECTED_NEEDS = {"visual_required", "visual_helpful"}
NEEDS = SELECTED_NEEDS | {"visual_not_needed"}
TREATMENTS = {"reinterpret", "preserve", "preserve+derived_sketch"}
DERIVED_TREATMENTS = {"reinterpret", "preserve+derived_sketch"}
RECONSTRUCTIBLE_KINDS = {"flow", "tree", "concept-map", "relations", "technical-schematic"}


class VisualPlanError(ValueError):
    """A plan cannot be materialized without violating the visual contract."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisualPlanError(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise VisualPlanError(f"{label} must be a JSON object: {path}")
    return payload


def _visual_rows(plan: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    raw = plan.get("visuals", [])
    if isinstance(raw, list):
        rows: list[tuple[str, dict[str, Any]]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise VisualPlanError(f"visuals[{index}] must be an object")
            rows.append((f"visuals[{index}]", dict(item)))
        return rows
    if isinstance(raw, dict):
        rows = []
        for key, item in raw.items():
            if not isinstance(item, dict):
                raise VisualPlanError(f"visuals.{key} must be an object")
            normalized = dict(item)
            normalized.setdefault("concept_id", str(key))
            rows.append((f"visuals.{key}", normalized))
        return rows
    raise VisualPlanError("visuals must be an array or an object keyed by concept id")


def _registry_match(figures: dict[str, Any], figure_id: str) -> tuple[str, dict[str, Any]] | None:
    direct = figures.get(figure_id)
    if isinstance(direct, dict):
        return figure_id, direct
    for key, item in figures.items():
        if isinstance(item, dict) and _text(item.get("id")) == figure_id:
            return key, item
    return None


def _source_figure(
    course: Path,
    figures: dict[str, Any],
    unit_id: str,
    figure_id: str,
    location: str,
) -> tuple[str, dict[str, Any]]:
    match = _registry_match(figures, figure_id)
    if match is None:
        raise VisualPlanError(f"{location}.source_figure_id is not registered: {figure_id}")
    key, item = match
    if item.get("origin") != "source":
        raise VisualPlanError(f"{location}.source_figure_id must identify a source figure: {figure_id}")
    if unit_id and record_unit_id(course, item) != unit_id:
        raise VisualPlanError(f"{location}.source_figure_id belongs to another unit: {figure_id}")
    if not _text(item.get("asset")):
        raise VisualPlanError(f"{location}.source_figure_id has no reusable source asset: {figure_id}")
    return key, item


def inspect_plan(course: Path, unit_value: str, plan_path: Path) -> list[dict[str, Any]]:
    """Return normalized selected visual entries after strict contract validation."""
    plan_path = plan_path.resolve()
    plan = _load_json(plan_path, "visual plan")
    unit_id = _text(resolve_unit(course, unit_value).get("unit_id"))
    if not unit_id:
        raise VisualPlanError(f"Could not resolve stable unit id from: {unit_value}")
    registry = load_registry(course)
    figures = registry.get("figures", {}) if isinstance(registry, dict) else {}
    if not isinstance(figures, dict):
        raise VisualPlanError("figure registry must contain a figures object")

    selected: list[dict[str, Any]] = []
    for location, item in _visual_rows(plan):
        need = _text(item.get("need"))
        if need not in NEEDS:
            raise VisualPlanError(f"{location}.need must be one of {sorted(NEEDS)}")
        if need == "visual_not_needed":
            continue

        treatment = _text(item.get("visual_treatment"))
        if treatment not in TREATMENTS:
            raise VisualPlanError(f"{location}.visual_treatment must be one of {sorted(TREATMENTS)}")
        concept_id = _text(item.get("concept_id"))
        if not concept_id:
            raise VisualPlanError(f"{location}.concept_id must be non-empty")
        if not _text(item.get("reason")):
            raise VisualPlanError(f"{location}.reason must explain the pedagogical value")

        source_key = ""
        source_item: dict[str, Any] | None = None
        source_id = _text(item.get("source_figure_id"))
        fidelity_reason = _text(item.get("fidelity_reason"))
        if treatment in {"preserve", "preserve+derived_sketch"}:
            if not source_id:
                raise VisualPlanError(f"{location}.source_figure_id is required for {treatment}")
            source_key, source_item = _source_figure(course, figures, unit_id, source_id, location)
            if not fidelity_reason:
                raise VisualPlanError(
                    f"{location}.fidelity_reason is required when source pixels are preserved"
                )
        elif source_id:
            raise VisualPlanError(
                f"{location}.source_figure_id cannot select a source asset for reinterpret; "
                "use figure:<id> in based_on as provenance"
            )

        normalized: dict[str, Any] = {
            "location": location,
            "concept_id": concept_id,
            "need": need,
            "visual_treatment": treatment,
            "reason": _text(item.get("reason")),
            "fidelity_reason": fidelity_reason,
            "source_figure_id": source_key,
            "source_asset": _text(source_item.get("asset")) if source_item else "",
        }

        if treatment in DERIVED_TREATMENTS:
            derived_id = _text(item.get("derived_figure_id"))
            if not derived_id:
                raise VisualPlanError(f"{location}.derived_figure_id is required for {treatment}")
            try:
                normalized_id = derived_key(derived_id)
            except (ValueError, SystemExit) as exc:
                raise VisualPlanError(f"{location}.derived_figure_id is invalid: {derived_id}") from exc
            based_on = item.get("based_on")
            if not isinstance(based_on, list) or not based_on or any(not _text(ref) for ref in based_on):
                raise VisualPlanError(f"{location}.based_on must be a non-empty reference array")
            spec_value = _text(item.get("sketch_spec"))
            if not spec_value:
                raise VisualPlanError(f"{location}.sketch_spec is required for {treatment}")
            spec_rel = Path(spec_value)
            if spec_rel.is_absolute():
                raise VisualPlanError(f"{location}.sketch_spec must be run-relative")
            spec_path = (plan_path.parent / spec_rel).resolve()
            sketch_root = (plan_path.parent / "02-sketches").resolve()
            if not spec_path.is_relative_to(sketch_root) or spec_path.suffix.lower() != ".json":
                raise VisualPlanError(f"{location}.sketch_spec must stay under 02-sketches/")
            spec_raw = _load_json(spec_path, "sketch spec")
            try:
                spec = validate_spec(spec_raw)
            except SketchSpecError as exc:
                raise VisualPlanError(f"{location}.sketch_spec is invalid: {exc}") from exc
            if normalized_id != derived_key(spec["id"]):
                raise VisualPlanError(f"{location}.derived_figure_id does not match sketch spec id")
            if spec["visual_treatment"] != treatment:
                raise VisualPlanError(f"{location}.visual_treatment does not match sketch spec")
            if set(map(str, based_on)) != set(spec["based_on"]):
                raise VisualPlanError(f"{location}.based_on must match sketch spec provenance")
            if treatment == "preserve+derived_sketch" and spec.get("source_figure_id") != source_id:
                raise VisualPlanError(f"{location}.source_figure_id does not match sketch spec")
            normalized.update({
                "derived_figure_id": normalized_id,
                "based_on": list(map(str, based_on)),
                "sketch_spec": spec_rel.as_posix(),
                "sketch_spec_path": spec_path,
                "figure_kind": spec["kind"],
                "spec": spec,
            })
        else:
            if item.get("derived_figure_id") or item.get("sketch_spec"):
                raise VisualPlanError(f"{location}.preserve must not declare a derived figure or sketch spec")
            figure_kind = _text(item.get("figure_kind") or (source_item or {}).get("kind"))
            normalized["figure_kind"] = figure_kind
            if figure_kind in RECONSTRUCTIBLE_KINDS and not fidelity_reason:
                raise VisualPlanError(
                    f"{location}.fidelity_reason is required to override reinterpret for {figure_kind}"
                )
        selected.append(normalized)
    return selected


def materialize_plan(course: Path, unit_value: str, plan_path: Path) -> dict[str, Any]:
    """Generate/register every planned sketch and return a stable build report."""
    plan_path = plan_path.resolve()
    rows = inspect_plan(course, unit_value, plan_path)
    unit_id = _text(resolve_unit(course, unit_value).get("unit_id"))
    built: list[dict[str, Any]] = []
    for row in rows:
        output = {
            "concept_id": row["concept_id"],
            "visual_treatment": row["visual_treatment"],
            "source_figure_id": row.get("source_figure_id") or None,
        }
        if row["visual_treatment"] in DERIVED_TREATMENTS:
            result = generate_and_register(course, unit_id, row["spec"])
            record = result["record"]
            output.update({
                "derived_figure_id": result["key"],
                "asset": record["asset"],
                "asset_sha256": record["asset_sha256"],
                "spec": record["generation"]["spec"],
                "spec_sha256": record["generation"]["spec_sha256"],
            })
        else:
            source_match = _registry_match(load_registry(course)["figures"], row["source_figure_id"])
            if source_match is None:  # pragma: no cover - inspect_plan already guarantees this
                raise VisualPlanError(f"source figure disappeared during materialization: {row['source_figure_id']}")
            _key, record = source_match
            output.update({"asset": record["asset"], "asset_sha256": record.get("asset_sha256")})
        built.append(output)
    return {
        "version": 1,
        "ok": True,
        "unit_id": unit_id,
        "plan_sha256": sha256(plan_path),
        "entries": built,
    }


def artifact_usage_issues(
    course: Path,
    unit_value: str,
    plan_path: Path,
    used_figure_ids: set[str],
) -> tuple[list[str], int]:
    """Bind final Markdown figure IDs to the treatment selected in 02-plan.json."""
    try:
        rows = inspect_plan(course, unit_value, plan_path)
    except VisualPlanError as exc:
        return [f"visual-plan-invalid:{exc}"], 0

    figures = load_registry(course).get("figures", {})
    issues: list[str] = []

    def check_derived(row: dict[str, Any]) -> None:
        concept_id = row["concept_id"]
        treatment = row["visual_treatment"]
        derived_id = row["derived_figure_id"]
        record = figures.get(derived_id)
        generation = record.get("generation") if isinstance(record, dict) else None
        if not isinstance(record, dict) or record.get("origin") != "derived":
            issues.append(f"planned-derived-figure-not-registered:{concept_id}:{derived_id}")
        elif record.get("visual_treatment") != treatment:
            issues.append(f"planned-derived-treatment-mismatch:{concept_id}:{derived_id}")
        elif not isinstance(generation, dict) or generation.get("method") != "deterministic-svg":
            issues.append(f"planned-derived-generator-missing:{concept_id}:{derived_id}")

    for row in rows:
        treatment = row["visual_treatment"]
        concept_id = row["concept_id"]
        source_id = row.get("source_figure_id") or ""
        if treatment == "reinterpret":
            derived_id = row["derived_figure_id"]
            if derived_id not in used_figure_ids:
                issues.append(f"planned-reinterpret-derived-not-used:{concept_id}:{derived_id}")
            for ref in row.get("based_on", []):
                if not ref.startswith("figure:"):
                    continue
                referenced = ref.split(":", 1)[1]
                match = _registry_match(figures, referenced)
                if match and match[1].get("origin") == "source" and match[0] in used_figure_ids:
                    issues.append(f"planned-reinterpret-uses-source-asset:{concept_id}:{match[0]}")
            check_derived(row)
        elif treatment == "preserve":
            if source_id not in used_figure_ids:
                issues.append(f"planned-preserve-source-not-used:{concept_id}:{source_id}")
        else:
            derived_id = row["derived_figure_id"]
            if source_id not in used_figure_ids:
                issues.append(f"planned-companion-source-not-used:{concept_id}:{source_id}")
            if derived_id not in used_figure_ids:
                issues.append(f"planned-companion-derived-not-used:{concept_id}:{derived_id}")
            check_derived(row)
    return issues, len(rows)


def _safe_file(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise VisualPlanError(f"File not found: {value}")
    return path


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize deterministic figures selected by 02-plan.json")
    parser.add_argument("--course", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--write", required=True)
    args = parser.parse_args()
    course = resolve_course(args.course)
    try:
        report = materialize_plan(course, args.unit, _safe_file(args.plan))
        output = Path(args.write)
        if not output.is_absolute():
            output = (ROOT / output).resolve()
        _write_report(output, report)
    except (VisualPlanError, SketchSpecError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
