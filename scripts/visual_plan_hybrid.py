#!/usr/bin/env python3
"""Validate and materialize hybrid study visuals.

Summary visuals are always notebook-style derived assets: exact academic
structure uses deterministic SVG diagrams and optional physical recognition
uses bounded generated illustrations. Source figures may provide provenance,
but their raw pixels are never published by the summary pipeline.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course
from scripts.figure_assets import derived_key, load_registry
from scripts.illustration_figure import (
    IllustrationError,
    IllustrationUnavailable,
    generate_and_register as generate_illustration,
    validate_spec as validate_illustration_spec,
)
from scripts.sketch_figure import SketchSpecError, generate_and_register, validate_spec
from scripts.unit_identity import resolve_unit
from scripts.visual_plan import (
    NEEDS,
    VisualPlanError,
    _load_json,
    _registry_match,
    _safe_file,
    _text,
    _visual_rows,
    _write_report,
    sha256,
)

MEDIA = {"diagram", "illustration"}
RECOGNITION_DECISIONS = {"illustration", "visual_not_needed"}
SUMMARY_TREATMENT = "reinterpret"


def _physical_recognition_review(plan: dict[str, Any]) -> list[dict[str, str]]:
    """Require one compact, explicit recognition check inside the existing PLAN pass."""
    raw = plan.get("physical_recognition_review")
    if not isinstance(raw, dict):
        raise VisualPlanError(
            "physical_recognition_review is required; complete it inside the existing PLAN pass"
        )
    if raw.get("complete") is not True:
        raise VisualPlanError("physical_recognition_review.complete must be true")
    candidates = raw.get("candidates")
    if not isinstance(candidates, list):
        raise VisualPlanError("physical_recognition_review.candidates must be an array")

    normalized: list[dict[str, str]] = []
    for index, candidate in enumerate(candidates):
        location = f"physical_recognition_review.candidates[{index}]"
        if not isinstance(candidate, dict):
            raise VisualPlanError(f"{location} must be an object")
        subject = _text(candidate.get("subject"))
        decision = _text(candidate.get("decision"))
        reason = _text(candidate.get("reason"))
        derived_id = _text(candidate.get("derived_figure_id"))
        if not subject:
            raise VisualPlanError(f"{location}.subject must be non-empty")
        if decision not in RECOGNITION_DECISIONS:
            raise VisualPlanError(
                f"{location}.decision must be one of {sorted(RECOGNITION_DECISIONS)}"
            )
        if not reason:
            raise VisualPlanError(f"{location}.reason must explain the decision")
        if decision == "illustration" and not derived_id:
            raise VisualPlanError(f"{location}.derived_figure_id is required for illustration")
        if decision == "visual_not_needed" and derived_id:
            raise VisualPlanError(
                f"{location}.derived_figure_id is only valid when decision=illustration"
            )
        normalized.append({
            "subject": subject,
            "decision": decision,
            "reason": reason,
            "derived_figure_id": derived_id,
        })
    return normalized


def inspect_plan(course: Path, unit_value: str, plan_path: Path) -> list[dict[str, Any]]:
    """Return selected summary visuals after strict hybrid contract validation."""
    plan_path = plan_path.resolve()
    plan = _load_json(plan_path, "visual plan")
    recognition_review = _physical_recognition_review(plan)
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
        if treatment != SUMMARY_TREATMENT:
            raise VisualPlanError(
                f"{location}.visual_treatment must be reinterpret for resumen; "
                "preserve and preserve+derived_sketch are not publishable summary visuals"
            )

        concept_id = _text(item.get("concept_id"))
        if not concept_id:
            raise VisualPlanError(f"{location}.concept_id must be non-empty")
        reason = _text(item.get("reason"))
        if not reason:
            raise VisualPlanError(f"{location}.reason must explain the pedagogical value")

        source_id = _text(item.get("source_figure_id"))
        if source_id:
            raise VisualPlanError(
                f"{location}.source_figure_id cannot publish source pixels in resumen; "
                "use figure:<id> inside based_on as provenance"
            )

        medium = _text(item.get("visual_medium")) or "diagram"
        if medium not in MEDIA:
            raise VisualPlanError(f"{location}.visual_medium must be one of {sorted(MEDIA)}")

        derived_id = _text(item.get("derived_figure_id"))
        if not derived_id:
            raise VisualPlanError(f"{location}.derived_figure_id is required for reinterpret")
        try:
            normalized_id = derived_key(derived_id)
        except (ValueError, SystemExit) as exc:
            raise VisualPlanError(f"{location}.derived_figure_id is invalid: {derived_id}") from exc

        based_on = item.get("based_on")
        if not isinstance(based_on, list) or not based_on or any(not _text(ref) for ref in based_on):
            raise VisualPlanError(f"{location}.based_on must be a non-empty reference array")

        normalized: dict[str, Any] = {
            "location": location,
            "concept_id": concept_id,
            "need": need,
            "visual_treatment": SUMMARY_TREATMENT,
            "visual_medium": medium,
            "reason": reason,
            "fidelity_reason": "",
            "source_figure_id": "",
            "source_asset": "",
            "derived_figure_id": normalized_id,
            "based_on": list(map(str, based_on)),
        }

        if medium == "illustration":
            if need != "visual_helpful":
                raise VisualPlanError(
                    f"{location}.illustration must be visual_helpful; exact/required teaching uses a diagram"
                )
            if item.get("sketch_spec"):
                raise VisualPlanError(f"{location}.illustration must not declare sketch_spec")
            raw_spec = item.get("illustration")
            try:
                spec = validate_illustration_spec(raw_spec)
            except IllustrationError as exc:
                raise VisualPlanError(f"{location}.illustration is invalid: {exc}") from exc
            if normalized_id != derived_key(spec["id"]):
                raise VisualPlanError(f"{location}.derived_figure_id does not match illustration id")
            if set(map(str, based_on)) != set(spec["based_on"]):
                raise VisualPlanError(f"{location}.based_on must match illustration provenance")
            normalized["illustration"] = spec
            normalized["figure_kind"] = "illustration"
        else:
            if item.get("illustration"):
                raise VisualPlanError(f"{location}.diagram must not declare illustration")
            spec_value = _text(item.get("sketch_spec"))
            if not spec_value:
                raise VisualPlanError(f"{location}.sketch_spec is required for diagram reinterpret")
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
            if spec["visual_treatment"] != SUMMARY_TREATMENT:
                raise VisualPlanError(f"{location}.sketch spec must use visual_treatment=reinterpret")
            if set(map(str, based_on)) != set(spec["based_on"]):
                raise VisualPlanError(f"{location}.based_on must match sketch spec provenance")
            normalized.update({
                "sketch_spec": spec_rel.as_posix(),
                "sketch_spec_path": spec_path,
                "figure_kind": spec["kind"],
                "spec": spec,
            })

        selected.append(normalized)

    illustration_ids = {
        row["derived_figure_id"]
        for row in selected
        if row.get("visual_medium") == "illustration" and row.get("derived_figure_id")
    }
    for index, candidate in enumerate(recognition_review):
        if candidate["decision"] != "illustration":
            continue
        location = f"physical_recognition_review.candidates[{index}]"
        try:
            normalized_id = derived_key(candidate["derived_figure_id"])
        except (ValueError, SystemExit) as exc:
            raise VisualPlanError(
                f"{location}.derived_figure_id is invalid: {candidate['derived_figure_id']}"
            ) from exc
        if normalized_id not in illustration_ids:
            raise VisualPlanError(
                f"{location}.derived_figure_id must match a selected visual_medium=illustration row"
            )
    return selected


def materialize_plan(course: Path, unit_value: str, plan_path: Path) -> dict[str, Any]:
    plan_path = plan_path.resolve()
    rows = inspect_plan(course, unit_value, plan_path)
    unit_id = _text(resolve_unit(course, unit_value).get("unit_id"))
    built: list[dict[str, Any]] = []
    unavailable: list[dict[str, str]] = []

    for row in rows:
        output: dict[str, Any] = {
            "concept_id": row["concept_id"],
            "visual_treatment": row["visual_treatment"],
            "visual_medium": row["visual_medium"],
            "source_figure_id": None,
        }
        if row["visual_medium"] == "illustration":
            try:
                result = generate_illustration(
                    course, unit_id, row["illustration"], concept_id=row["concept_id"]
                )
            except IllustrationUnavailable as exc:
                unavailable.append({"concept_id": row["concept_id"], "error": str(exc)})
                continue
            record = result["record"]
            output.update({
                "derived_figure_id": result["key"],
                "asset": record["asset"],
                "asset_sha256": record["asset_sha256"],
                "illustration_spec_sha256": record["illustration_generation"]["spec_sha256"],
                "model": record["illustration_generation"]["model"],
            })
        else:
            result = generate_and_register(course, unit_id, row["spec"])
            record = result["record"]
            output.update({
                "derived_figure_id": result["key"],
                "asset": record["asset"],
                "asset_sha256": record["asset_sha256"],
                "spec": record["generation"]["spec"],
                "spec_sha256": record["generation"]["spec_sha256"],
            })
        built.append(output)

    return {
        "version": 1,
        "visual_system": "hybrid-v1",
        "ok": not unavailable,
        "unit_id": unit_id,
        "plan_sha256": sha256(plan_path),
        "entries": built,
        "illustration_unavailable": unavailable,
    }


def artifact_usage_issues(
    course: Path,
    unit_value: str,
    plan_path: Path,
    used_figure_ids: set[str],
) -> tuple[list[str], int]:
    try:
        rows = inspect_plan(course, unit_value, plan_path)
    except VisualPlanError as exc:
        return [f"visual-plan-invalid:{exc}"], 0

    figures = load_registry(course).get("figures", {})
    issues: list[str] = []

    for figure_id in sorted(used_figure_ids):
        match = _registry_match(figures, figure_id)
        if match and match[1].get("origin") == "source":
            issues.append(f"summary-source-figure-used:{match[0]}")

    def check_derived(row: dict[str, Any]) -> None:
        concept_id = row["concept_id"]
        derived_id = row["derived_figure_id"]
        record = figures.get(derived_id)
        if not isinstance(record, dict) or record.get("origin") != "derived":
            issues.append(f"planned-derived-figure-not-registered:{concept_id}:{derived_id}")
            return
        if record.get("visual_treatment") != SUMMARY_TREATMENT:
            issues.append(f"planned-derived-treatment-mismatch:{concept_id}:{derived_id}")
        if row["visual_medium"] == "illustration":
            meta = record.get("illustration_generation")
            if record.get("kind") != "illustration":
                issues.append(f"planned-illustration-kind-mismatch:{concept_id}:{derived_id}")
            if not isinstance(meta, dict) or meta.get("method") != "generated-illustration":
                issues.append(f"planned-illustration-generator-missing:{concept_id}:{derived_id}")
        else:
            generation = record.get("generation")
            if not isinstance(generation, dict) or generation.get("method") != "deterministic-svg":
                issues.append(f"planned-derived-generator-missing:{concept_id}:{derived_id}")

    for row in rows:
        concept_id = row["concept_id"]
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

    return issues, len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize hybrid visuals selected by 02-plan.json")
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
            output = (Path.cwd() / output).resolve()
        _write_report(output, report)
    except (VisualPlanError, SketchSpecError, IllustrationError, ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    # Execute through the runtime wrapper so direct CLI use gets the same
    # scale-aware pencil/layout/crop behavior as the pipeline, without adding
    # another model pass or changing the semantic plan contract.
    runpy.run_module("scripts.visual_plan_hybrid_runtime", run_name="__main__")
