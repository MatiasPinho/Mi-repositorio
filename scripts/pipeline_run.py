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
from unit_identity import resolve_unit  # noqa: E402
from scripts.academic_eval import evaluate_review  # noqa: E402

STAGED = {"resumen", "guia", "repaso"}
REQUIRED_STAGES = ["02-plan.json", "03-draft.md", "04-humanized.md", "05-review.json"]
SCRIPT_EXTENSIONS = {".py", ".js", ".ts", ".sh", ".ps1", ".bat", ".cmd"}


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


def resolve_run(value: str) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    p = p.resolve()
    if not p.is_dir() or not (p / "manifest.json").exists():
        raise SystemExit(f"Invalid run directory: {value}")
    return p


def cmd_start(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    pipeline = args.pipeline
    scope = args.scope or ""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = course / ".study" / "runs" / f"{ts}-{pipeline}-{norm_slug(scope or 'all')}"
    candidate = base
    n = 2
    while candidate.exists():
        candidate = Path(str(base) + f"-{n}"
        )
        n += 1
    candidate.mkdir(parents=True)
    manifest = {
        "version": 1,
        "pipeline": pipeline,
        "course": course.relative_to(ROOT).as_posix(),
        "scope": scope,
        "executor": args.executor,
        "status": "running",
        "started_at": now(),
        "finished_at": None,
        "stages": {},
        "course_script_snapshot": course_script_snapshot(course),
    }
    save(candidate / "manifest.json", manifest)
    inp = {
        "pipeline": pipeline,
        "course": manifest["course"],
        "scope": scope,
        "unit_id": resolve_unit(course, scope).get("unit_id", ""),
        "academic_file": (course / "academico" / "academic.json").relative_to(ROOT).as_posix(),
        "concepts_file": (course / "conocimiento" / "concepts.json").relative_to(ROOT).as_posix(),
        "figures_file": (course / "conocimiento" / "figures.json").relative_to(ROOT).as_posix(),
        "academic_sha256": sha(course / "academico" / "academic.json"),
        "concepts_sha256": sha(course / "conocimiento" / "concepts.json"),
        "figures_sha256": sha(course / "conocimiento" / "figures.json"),
        "created_at": now(),
    }
    save(candidate / "01-input.json", inp)
    manifest["stages"]["01-input.json"] = "created"
    save(candidate / "manifest.json", manifest)
    print(json.dumps({"run_dir": candidate.relative_to(ROOT).as_posix(), "input": "01-input.json"}, ensure_ascii=False, indent=2))


def review_gate(path: Path) -> list[str]:
    """Apply the versioned deterministic academic evaluation policy."""
    return evaluate_review(load(path, {}))


def validate_run(run: Path) -> dict[str, Any]:
    manifest = load(run / "manifest.json", {})
    pipeline = manifest.get("pipeline")
    errors: list[str] = []
    if pipeline in STAGED:
        for name in REQUIRED_STAGES:
            if not (run / name).is_file():
                errors.append(f"missing-{name}")
        first_review = run / "05-review.json"
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
