#!/usr/bin/env python3
"""Deterministic portable run/handoff manager for semantic study pipelines."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import resolve_course  # noqa: E402
if __package__:
    from .course_layout import (  # noqa: E402
        LayoutError,
        has_unit_layout,
        registry_path,
        run_root,
        unit_root,
    )
    from .unit_identity import resolve_unit  # noqa: E402
else:
    from course_layout import (  # noqa: E402
        LayoutError,
        has_unit_layout,
        registry_path,
        run_root,
        unit_root,
    )
    from unit_identity import resolve_unit  # noqa: E402
from scripts.academic_eval import evaluate_review  # noqa: E402

STAGED = {"resumen", "guia", "repaso"}
SUMMARY_STAGED = {"resumen", "guia"}
REQUIRED_STAGES = ["02-plan.json", "03-draft.md", "04-humanized.md", "05-review.json"]
SCRIPT_EXTENSIONS = {".py", ".js", ".ts", ".sh", ".ps1", ".bat", ".cmd"}
ENGINE_PROTECTED_DIRS = (
    "scripts",
    "pipelines",
    "rules",
    "config",
    "contracts",
    "core",
    "design",
    "study_mcp",
    "tests",
)
ENGINE_PROTECTED_FILES = (
    "study.py",
    "unit_identity.py",
    "requirements.txt",
    "requirements-mcp.txt",
    "requirements-visual.txt",
    "requirements-design.txt",
    ".mcp.json",
    ".codex/config.toml",
    "INSTALAR-STUDY.bat",
    "INICIAR-STUDY.bat",
)
CANONICAL_INPUTS = (
    ("academic", "academic_file", "academic_sha256"),
    ("concepts", "concepts_file", "concepts_sha256"),
    ("topics", "topics_file", "topics_sha256"),
    ("figures", "figures_file", "figures_sha256"),
)


def norm_slug(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:48] or "scope"


def sha(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def course_script_snapshot(course: Path) -> list[str]:
    """Track persistent helper scripts so semantic runs cannot leave ad-hoc repair tools behind."""
    rows: list[str] = []
    excluded_roots = {"fuentes", ".study", "assets"}
    for path in course.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCRIPT_EXTENSIONS:
            continue
        rel = path.relative_to(course)
        if rel.parts and rel.parts[0] in excluded_roots:
            continue
        rows.append(rel.as_posix())
    return sorted(rows)


def engine_snapshot() -> dict[str, str]:
    """Hash the checked-in engine surface that a study run must never mutate."""
    rows: dict[str, str] = {}
    for dirname in ENGINE_PROTECTED_DIRS:
        root = ROOT / dirname
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if "__pycache__" in rel.parts or path.suffix.lower() in {".pyc", ".pyo"}:
                continue
            digest = sha(path)
            if digest:
                rows[rel.as_posix()] = digest
    for rel_text in ENGINE_PROTECTED_FILES:
        path = ROOT / rel_text
        digest = sha(path)
        if digest:
            rows[Path(rel_text).as_posix()] = digest
    return dict(sorted(rows.items()))


def _validate_engine_snapshot(manifest: dict[str, Any], errors: list[str]) -> None:
    before = manifest.get("engine_snapshot")
    if not isinstance(before, dict):
        errors.append("missing-engine-snapshot")
        return
    after = engine_snapshot()
    before_keys = set(before)
    after_keys = set(after)
    for rel in sorted(after_keys - before_keys):
        errors.append(f"engine-added:{rel}")
    for rel in sorted(before_keys - after_keys):
        errors.append(f"engine-removed:{rel}")
    for rel in sorted(before_keys & after_keys):
        if before.get(rel) != after.get(rel):
            errors.append(f"engine-modified:{rel}")


def resolve_run(value: str) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    p = p.resolve()
    if not p.is_dir() or not (p / "manifest.json").exists():
        raise SystemExit(f"Invalid run directory: {value}")
    return p


def _resolve_repo_path(value: Any) -> Path:
    p = Path(str(value))
    if not p.is_absolute():
        p = ROOT / p
    return p.resolve()


def _validate_canonical_snapshot(run: Path, errors: list[str]) -> None:
    """Reject input drift, except append-only derived figures declared by the visual plan."""
    try:
        inp = load(run / "01-input.json", {})
    except (json.JSONDecodeError, OSError):
        errors.append("canonical-input-invalid-json")
        return
    if not isinstance(inp, dict):
        errors.append("canonical-input-invalid")
        return
    for label, file_key, hash_key in CANONICAL_INPUTS:
        raw_path = str(inp.get(file_key, "")).strip()
        if not raw_path:
            errors.append(f"canonical-input-path-missing:{label}")
            continue
        expected = inp.get(hash_key)
        actual = sha(_resolve_repo_path(raw_path))
        if expected != actual:
            if label == "figures":
                _validate_planned_figure_changes(run, _resolve_repo_path(raw_path), errors)
            else:
                errors.append(f"canonical-changed:{label}")


def _plan_visuals(run: Path) -> list[dict[str, Any]]:
    plan = load(run / "02-plan.json", {})
    raw = plan.get("visuals", []) if isinstance(plan, dict) else []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [item for item in raw.values() if isinstance(item, dict)]
    return []


def _planned_derived_treatments(run: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for item in _plan_visuals(run):
        treatment = str(item.get("visual_treatment", "")).strip()
        if treatment not in {"reinterpret", "preserve+derived_sketch"}:
            continue
        figure_id = str(item.get("derived_figure_id", "")).strip()
        if figure_id and not figure_id.startswith("derived:"):
            figure_id = f"derived:{figure_id}"
        if figure_id:
            rows[figure_id] = treatment
    return rows


def _validate_visual_build_report(run: Path, errors: list[str]) -> dict[str, Any] | None:
    path = run / "02-visual-build.json"
    if not path.is_file():
        errors.append("missing-02-visual-build.json")
        return None
    try:
        report = load(path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("visual-build-invalid-json")
        return None
    if not isinstance(report, dict) or report.get("ok") is not True:
        errors.append("visual-build-failed")
        return None
    plan_path = run / "02-plan.json"
    if not plan_path.is_file() or report.get("plan_sha256") != sha(plan_path):
        errors.append("visual-build-plan-mismatch")
    entries = report.get("entries")
    if not isinstance(entries, list):
        errors.append("visual-build-entries-missing")
        return report
    reported = {
        str(item.get("derived_figure_id", "")).strip(): str(item.get("visual_treatment", "")).strip()
        for item in entries
        if isinstance(item, dict) and item.get("derived_figure_id")
    }
    planned = _planned_derived_treatments(run)
    if reported != planned:
        errors.append("visual-build-derived-set-mismatch")
    return report


def _validate_planned_figure_changes(run: Path, current_path: Path, errors: list[str]) -> None:
    snapshot_path = run / "01-figures.json"
    if not snapshot_path.is_file():
        errors.append("canonical-changed:figures")
        errors.append("missing-01-figures.json")
        return
    run_input = load(run / "01-input.json", {})
    expected_snapshot = run_input.get("figures_sha256") if isinstance(run_input, dict) else None
    if sha(snapshot_path) != expected_snapshot:
        errors.append("figure-snapshot-hash-mismatch")
    try:
        before = load(snapshot_path, {})
        after = load(current_path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("figure-snapshot-invalid-json")
        return
    if not isinstance(before, dict) or not isinstance(after, dict):
        errors.append("figure-snapshot-invalid")
        return
    before_rows = before.get("figures", {})
    after_rows = after.get("figures", {})
    if not isinstance(before_rows, dict) or not isinstance(after_rows, dict):
        errors.append("figure-snapshot-rows-invalid")
        return

    before_meta = {key: value for key, value in before.items() if key not in {"version", "figures"}}
    after_meta = {key: value for key, value in after.items() if key not in {"version", "figures"}}
    if before_meta != after_meta:
        errors.append("canonical-changed:figures-metadata")
    try:
        if int(after.get("version", 1) or 1) < int(before.get("version", 1) or 1):
            errors.append("canonical-changed:figures-version-regressed")
    except (TypeError, ValueError):
        errors.append("canonical-changed:figures-version-invalid")

    removed = set(before_rows) - set(after_rows)
    if removed:
        errors.extend(f"canonical-figure-removed:{key}" for key in sorted(removed))
    for key in sorted(set(before_rows) & set(after_rows)):
        if before_rows[key] != after_rows[key]:
            errors.append(f"canonical-figure-modified:{key}")

    planned = _planned_derived_treatments(run)
    for key in sorted(set(after_rows) - set(before_rows)):
        row = after_rows[key]
        if key not in planned:
            errors.append(f"unplanned-derived-figure:{key}")
            continue
        if not isinstance(row, dict) or row.get("origin") != "derived":
            errors.append(f"planned-figure-origin-invalid:{key}")
        elif row.get("visual_treatment") != planned[key]:
            errors.append(f"planned-figure-treatment-mismatch:{key}")


def cmd_start(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    pipeline = args.pipeline
    scope = args.scope or ""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = run_root(course, pipeline, scope, ts)
    if not (scope and has_unit_layout(course)):
        base = Path(str(base) + f"-{norm_slug(scope or 'all')}")
    candidate = base
    n = 2
    while candidate.exists():
        candidate = Path(str(base) + f"-{n}")
        n += 1
    candidate.mkdir(parents=True)
    manifest = {
        "version": 2,
        "pipeline": pipeline,
        "course": course.relative_to(ROOT).as_posix(),
        "scope": scope,
        "executor": args.executor,
        "status": "running",
        "started_at": now(),
        "finished_at": None,
        "stages": {},
        "course_script_snapshot": course_script_snapshot(course),
        "engine_snapshot": engine_snapshot(),
    }
    save(candidate / "manifest.json", manifest)
    unit_id = resolve_unit(course, scope).get("unit_id", "")
    concepts_path = registry_path(course, "concepts", unit_id) if unit_id and has_unit_layout(course) else registry_path(course, "concepts")
    topics_path = registry_path(course, "topics", unit_id) if unit_id and has_unit_layout(course) else registry_path(course, "topics")
    figures_path = registry_path(course, "figures", unit_id) if unit_id and has_unit_layout(course) else registry_path(course, "figures")
    inp = {
        "pipeline": pipeline,
        "course": manifest["course"],
        "scope": scope,
        "unit_id": unit_id,
        "academic_file": (course / "academico" / "academic.json").relative_to(ROOT).as_posix(),
        "concepts_file": concepts_path.relative_to(ROOT).as_posix(),
        "topics_file": topics_path.relative_to(ROOT).as_posix(),
        "figures_file": figures_path.relative_to(ROOT).as_posix(),
        "academic_sha256": sha(course / "academico" / "academic.json"),
        "concepts_sha256": sha(concepts_path),
        "topics_sha256": sha(topics_path),
        "figures_sha256": sha(figures_path),
        "created_at": now(),
    }
    save(candidate / "01-input.json", inp)
    figures_snapshot = candidate / "01-figures.json"
    if figures_path.is_file():
        figures_snapshot.write_bytes(figures_path.read_bytes())
    else:
        save(figures_snapshot, {"version": 2, "figures": {}})
    manifest["stages"]["01-input.json"] = "created"
    manifest["stages"]["01-figures.json"] = "created"
    save(candidate / "manifest.json", manifest)
    print(json.dumps({"run_dir": candidate.relative_to(ROOT).as_posix(), "input": "01-input.json"}, ensure_ascii=False, indent=2))


def review_gate(path: Path) -> list[str]:
    """Apply the versioned deterministic academic evaluation policy."""
    return evaluate_review(load(path, {}))


def _accepted_markdown(run: Path) -> Path:
    first = run / "05-review.json"
    if first.is_file() and not review_gate(first):
        return run / "06-final.md"
    return run / "08-final.md"


def _validate_visual_audit(run: Path, errors: list[str]) -> None:
    audit_dir = run / "visual-audit"
    report_path = audit_dir / "audit.json"
    if not report_path.is_file():
        errors.append("missing-visual-audit.json")
        return
    try:
        report = load(report_path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("visual-audit-invalid-json")
        return
    if not isinstance(report, dict) or report.get("ok") is not True:
        errors.append("visual-audit-failed")
    if report.get("engine") != "chromium-set-content":
        errors.append("visual-audit-wrong-engine")
    for name in ("desktop.png", "mobile.png"):
        shot = audit_dir / name
        if not shot.is_file() or shot.stat().st_size <= 0:
            errors.append(f"missing-visual-screenshot:{name}")


def _validate_publication(run: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    report_path = run / "11-publication.json"
    if not report_path.is_file():
        errors.append("missing-11-publication.json")
        return
    try:
        report = load(report_path, {})
    except (json.JSONDecodeError, OSError):
        errors.append("publication-invalid-json")
        return
    if not isinstance(report, dict) or report.get("ok") is not True:
        errors.append("publication-failed")
        return
    rows = report.get("files")
    if not isinstance(rows, list):
        errors.append("publication-files-missing")
        return
    by_role = {row.get("role"): row for row in rows if isinstance(row, dict) and row.get("role")}
    if set(by_role) != {"markdown", "html"}:
        errors.append("publication-roles-invalid")
        return

    course_rel = manifest.get("course", "")
    course = (ROOT / str(course_rel)).resolve() if course_rel else None
    if not course or not course.is_dir():
        errors.append("publication-course-invalid")
        return
    unit_layout = has_unit_layout(course)
    if unit_layout:
        run_input = load(run / "01-input.json", {})
        unit_id = str(run_input.get("unit_id", "")).strip() if isinstance(run_input, dict) else ""
        if not unit_id:
            errors.append("publication-unit-missing")
            return
        try:
            publish_root = (unit_root(course, unit_id) / "resumenes").resolve()
        except LayoutError:
            errors.append(f"publication-unit-invalid:{unit_id}")
            return
    else:
        publish_root = (course / "resumenes").resolve()
    expected_sources = {
        "markdown": _accepted_markdown(run).resolve(),
        "html": (run / "09-rendered.html").resolve(),
    }
    version = int(report.get("version", 1) or 1)

    for role, expected_source in expected_sources.items():
        row = by_role[role]
        source = _resolve_repo_path(row.get("source", ""))
        destination = _resolve_repo_path(row.get("destination", ""))
        if source != expected_source:
            errors.append(f"publication-source-invalid:{role}")
        try:
            destination.relative_to(publish_root)
        except ValueError:
            boundary = "unit" if unit_layout else "course"
            errors.append(f"publication-destination-outside-{boundary}:{role}")
        if not source.is_file() or not destination.is_file():
            errors.append(f"publication-file-missing:{role}")
            continue
        source_hash = sha(source)
        destination_hash = sha(destination)
        if version >= 3:
            published_hash = row.get("published_sha256")
            if row.get("source_sha256") != source_hash:
                errors.append(f"publication-source-mutated:{role}")
            if published_hash != destination_hash or row.get("destination_sha256") != destination_hash:
                errors.append(f"publication-hash-mismatch:{role}")
            if row.get("source_bytes") != source.stat().st_size:
                errors.append(f"publication-source-size-mismatch:{role}")
            if row.get("bytes") != destination.stat().st_size:
                errors.append(f"publication-size-mismatch:{role}")
            transform = row.get("transform")
            if transform not in {"identity", "rebase-local-image-refs-v1"}:
                errors.append(f"publication-transform-invalid:{role}")
            if transform == "identity" and source_hash != destination_hash:
                errors.append(f"publication-identity-mismatch:{role}")
        else:
            if (
                source_hash != destination_hash
                or row.get("source_sha256") != source_hash
                or row.get("destination_sha256") != destination_hash
            ):
                errors.append(f"publication-hash-mismatch:{role}")
            if row.get("bytes") != source.stat().st_size or destination.stat().st_size != source.stat().st_size:
                errors.append(f"publication-size-mismatch:{role}")


def validate_run(run: Path) -> dict[str, Any]:
    manifest = load(run / "manifest.json", {})
    pipeline = manifest.get("pipeline")
    errors: list[str] = []
    if pipeline in STAGED:
        for name in REQUIRED_STAGES:
            if not (run / name).is_file():
                errors.append(f"missing-{name}")
        first_review = run / "05-review.json"
        if pipeline in SUMMARY_STAGED:
            _validate_visual_build_report(run, errors)
        if first_review.is_file():
            first_issues = review_gate(first_review)
            if not first_issues:
                final = run / "06-final.md"
                if not final.is_file():
                    errors.append("missing-06-final.md")
                elif not final.read_text(encoding="utf-8").strip():
                    errors.append("final-empty")
            else:
                repair = run / "06-repair.md"
                second = run / "07-review.json"
                final = run / "08-final.md"
                for needed in (repair, second, final):
                    if not needed.is_file():
                        errors.append(f"missing-{needed.name}")
                if second.is_file():
                    errors.extend(f"second-{x}" for x in review_gate(second))
                if final.is_file() and not final.read_text(encoding="utf-8").strip():
                    errors.append("final-empty")
        rendered = run / "09-rendered.html"
        if not rendered.is_file():
            errors.append("missing-09-rendered.html")
        elif not rendered.read_text(encoding="utf-8").strip():
            errors.append("rendered-empty")
        integrity = run / "10-integrity.json"
        if not integrity.is_file():
            errors.append("missing-10-integrity.json")
        else:
            payload = load(integrity, {})
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                errors.append("integrity-gate-failed")

        _validate_canonical_snapshot(run, errors)
        _validate_visual_audit(run, errors)
        _validate_publication(run, manifest, errors)
        _validate_engine_snapshot(manifest, errors)

        course_rel = manifest.get("course", "")
        course = (ROOT / str(course_rel)).resolve() if course_rel else None
        if course and course.is_dir():
            before = set(manifest.get("course_script_snapshot", []))
            after = set(course_script_snapshot(course))
            for rel in sorted(after - before):
                errors.append(f"unexpected-course-script:{rel}")
    return {"ok": not errors, "pipeline": pipeline, "errors": errors}


def cmd_validate(args: argparse.Namespace) -> None:
    run = resolve_run(args.run)
    result = validate_run(run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


def cmd_status(args: argparse.Namespace) -> None:
    run = resolve_run(args.run)
    manifest = load(run / "manifest.json", {})
    existing = sorted(p.name for p in run.iterdir() if p.is_file())
    result = validate_run(run)
    print(json.dumps({"manifest": manifest, "files": existing, "validation": result}, ensure_ascii=False, indent=2))


def cmd_finish(args: argparse.Namespace) -> None:
    run = resolve_run(args.run)
    result = validate_run(run)
    if not result["ok"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    manifest = load(run / "manifest.json", {})
    manifest["status"] = "finished"
    manifest["finished_at"] = now()
    manifest["stages"] = {p.name: "present" for p in sorted(run.iterdir()) if p.is_file() and p.name != "manifest.json"}
    manifest["stages"]["visual-audit/audit.json"] = "present"
    manifest["stages"]["visual-audit/desktop.png"] = "present"
    manifest["stages"]["visual-audit/mobile.png"] = "present"
    manifest["stages"]["11-publication.json"] = "present"
    save(run / "manifest.json", manifest)
    print(json.dumps({"ok": True, "run": run.relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Portable study-pipeline run manager")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--course", required=True)
    p.add_argument("--pipeline", required=True, choices=["resumen", "guia", "repaso", "procesar", "aprender", "estudiar", "preguntas", "simulacro", "explicar", "auditar", "estado"])
    p.add_argument("--scope", default="")
    p.add_argument("--executor", choices=["portable", "claude", "codex"], default="portable")
    p.set_defaults(func=cmd_start)
    for name, func in (("validate", cmd_validate), ("status", cmd_status), ("finish", cmd_finish)):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        p.set_defaults(func=func)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
