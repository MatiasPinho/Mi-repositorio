#!/usr/bin/env python3
"""Safety wrapper for Engine QA.

Runs the adversarial harness against a frozen copy of the engine rather than
against the user's live checkout. Reports are still exported to the real repo.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

REAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REAL_ROOT))

from scripts import engine_qa  # noqa: E402

REAL_REPORTS_ROOT = REAL_ROOT / "qa" / "reports"
DEFAULT_REAL_QA_ROOT = REAL_ROOT / ".study" / "engine-qa"
SANDBOX_SUBDIR = "sandboxes"
GUARD_VERSION = 1

# Drift in any of these live-checkout paths invalidates an active QA run.
# The actual engine process executes a frozen copy, but this second guard also
# prevents the agent from silently changing the source checkout while testing.
LIVE_GUARD_PATHS = (
    "study.py",
    "core",
    "rules",
    "pipelines",
    "contracts",
    "vendor",
    "scripts",
    "study_mcp",
    "config",
    "actions",
    "assets",
    "design",
    "skills-src",
    ".claude/skills",
    ".agents/skills",
    "tests",
    "docs",
    ".github",
    "requirements.txt",
    "requirements-mcp.txt",
    "requirements-visual.txt",
    "requirements-design.txt",
    "INSTALAR-STUDY.bat",
    ".gitignore",
)


def qa_root() -> Path:
    return Path(os.environ.get("STUDY_ENGINE_QA_ROOT", DEFAULT_REAL_QA_ROOT)).resolve()


def sandbox_root_base() -> Path:
    override = os.environ.get("STUDY_ENGINE_QA_SANDBOX_ROOT")
    return Path(override).resolve() if override else (qa_root() / SANDBOX_SUBDIR).resolve()


def _sha(path: Path) -> str:
    return engine_qa.sha256_file(path)


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def live_fingerprint() -> dict[str, str]:
    rows: dict[str, str] = {}
    for rel in LIVE_GUARD_PATHS:
        target = REAL_ROOT / rel
        if target.is_file():
            rows[rel] = _sha(target)
        elif target.is_dir():
            for file in sorted(p for p in target.rglob("*") if p.is_file()):
                if "__pycache__" in file.parts or file.suffix in {".pyc", ".pyo"}:
                    continue
                rows[_relative(REAL_ROOT, file)] = _sha(file)
    return rows


def fingerprint_diff(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(k for k in set(before) & set(after) if before[k] != after[k]),
    }


def fingerprint_digest(rows: dict[str, str]) -> str:
    return engine_qa.fingerprint_digest(rows)


def copy_frozen_engine(destination: Path) -> None:
    if destination.exists():
        raise engine_qa.QaError(f"Sandbox ya existe: {destination}")
    destination.mkdir(parents=True)
    for rel in engine_qa.PROTECTED_PATHS:
        src = REAL_ROOT / rel
        dst = destination / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        elif src.is_dir():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
    # Some scripts discover root-level dependency/config files opportunistically.
    for name in (
        "requirements.txt",
        "requirements-mcp.txt",
        "requirements-visual.txt",
        "requirements-design.txt",
        ".gitignore",
    ):
        src = REAL_ROOT / name
        if src.is_file():
            shutil.copy2(src, destination / name)


def patch_engine_module(sandbox: Path) -> None:
    engine_qa.ROOT = sandbox
    engine_qa.SCRIPTS = sandbox / "scripts"
    # Reports are the only intentional write back to the live checkout.
    engine_qa.REPORTS_ROOT = REAL_REPORTS_ROOT


def _run_value(argv: list[str]) -> str:
    for idx, token in enumerate(argv):
        if token == "--run" and idx + 1 < len(argv):
            return argv[idx + 1]
        if token.startswith("--run="):
            return token.split("=", 1)[1]
    return "latest"


def resolve_live_run(argv: list[str]) -> Path:
    return engine_qa.resolve_run(qa_root(), _run_value(argv))


def guard_path(run_dir: Path) -> Path:
    return run_dir / "live-guard.json"


def install_live_guard(run_dir: Path, sandbox: Path) -> None:
    rows = live_fingerprint()
    digest = fingerprint_digest(rows)
    engine_qa.write_json(
        guard_path(run_dir),
        {
            "version": GUARD_VERSION,
            "sandbox_root": str(sandbox.resolve()),
            "live_engine_sha256": digest,
            "live_engine_files": rows,
        },
    )
    manifest = engine_qa.manifest_for(run_dir)
    manifest["sandbox_root"] = str(sandbox.resolve())
    manifest["live_engine_sha256"] = digest
    manifest["safety_wrapper_version"] = GUARD_VERSION
    engine_qa.save_manifest(run_dir, manifest)
    engine_qa.journal(
        run_dir,
        "safety-wrapper",
        sandbox_root=str(sandbox.resolve()),
        live_engine_sha256=digest,
        version=GUARD_VERSION,
    )


def load_live_guard(run_dir: Path) -> dict[str, Any]:
    data = engine_qa.read_json(guard_path(run_dir), {}) or {}
    if int(data.get("version", 0) or 0) != GUARD_VERSION:
        raise engine_qa.QaError("Falta el guard de seguridad del Engine QA run.")
    sandbox = Path(str(data.get("sandbox_root", ""))).resolve()
    base = sandbox_root_base()
    try:
        sandbox.relative_to(base)
    except ValueError as exc:
        raise engine_qa.QaError("El sandbox declarado queda fuera del QA sandbox root.") from exc
    if not (sandbox / "scripts" / "engine_qa.py").is_file():
        raise engine_qa.QaError("Sandbox Engine QA inexistente o incompleto.")
    return data


def verify_live_checkout(run_dir: Path, guard: dict[str, Any]) -> None:
    before = guard.get("live_engine_files", {})
    now = live_fingerprint()
    diff = fingerprint_diff(before, now)
    if any(diff.values()):
        manifest = engine_qa.manifest_for(run_dir)
        manifest.update(
            {
                "blocked": True,
                "block_reason": "live-checkout-mutated-during-qa",
                "live_checkout_diff": diff,
            }
        )
        engine_qa.save_manifest(run_dir, manifest)
        engine_qa.journal(
            run_dir,
            "fatal",
            reason="live-checkout-mutated-during-qa",
            diff=diff,
        )
        raise engine_qa.QaError("El checkout real cambió desde el inicio del QA run.")


def _contains_parent_segment(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return ".." in [part for part in normalized.split("/") if part]


def _expand_safe_token(token: str, course: Path, run_dir: Path, sandbox: Path) -> str:
    aliases = {
        "@course": str(course),
        "@run": str(run_dir),
        "@root": str(sandbox),
        "@slug": course.name,
    }
    if token in aliases:
        return aliases[token]
    for prefix, base in (
        ("@course/", course),
        ("@run/", run_dir),
        ("@root/", sandbox),
    ):
        if token.startswith(prefix):
            relative = token[len(prefix) :]
            if _contains_parent_segment(relative):
                raise engine_qa.QaError("Path traversal rechazado en argumento de exec.")
            return str((base / relative).resolve())
    if token.startswith("--") and "=" in token:
        option, value = token.split("=", 1)
        expanded = _expand_safe_token(value, course, run_dir, sandbox)
        return f"{option}={expanded}"
    return token


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate_path_value(value: str, allowed_roots: tuple[Path, ...]) -> None:
    if _contains_parent_segment(value):
        raise engine_qa.QaError(f"Path traversal rechazado: {value}")
    candidate = Path(value)
    if candidate.is_absolute() and not any(_inside(candidate, root) for root in allowed_roots):
        raise engine_qa.QaError(f"Ruta absoluta fuera del sandbox QA: {value}")


def validate_exec_tokens(run_dir: Path, argv: list[str], sandbox: Path) -> list[str]:
    if "exec" not in argv:
        return argv
    course = engine_qa.course_for(run_dir).resolve()
    allowed_roots = (sandbox.resolve(), run_dir.resolve(), REAL_REPORTS_ROOT.resolve())
    rewritten = [_expand_safe_token(token, course, run_dir, sandbox) for token in argv]

    script = ""
    for idx, token in enumerate(rewritten):
        if token == "--script" and idx + 1 < len(rewritten):
            script = rewritten[idx + 1]
        elif token.startswith("--script="):
            script = token.split("=", 1)[1]

    for idx, token in enumerate(rewritten):
        value = token.split("=", 1)[1] if token.startswith("--") and "=" in token else token
        _validate_path_value(value, allowed_roots)

        if token.startswith("--course="):
            supplied = Path(token.split("=", 1)[1]).resolve()
            if supplied != course:
                raise engine_qa.QaError("--course debe apuntar a la materia QA del run.")
        if token == "--course" and idx + 1 < len(rewritten):
            supplied = Path(rewritten[idx + 1]).resolve()
            if supplied != course:
                raise engine_qa.QaError("--course debe apuntar a la materia QA del run.")

    if script == "study.py":
        marker = rewritten.index("--script") + 2 if "--script" in rewritten else 0
        tail = rewritten[marker:]
        if str(course) not in tail and course.name not in tail:
            raise engine_qa.QaError("study.py debe recibir exactamente @course o @slug del run.")

    return rewritten


def _replace_argv(rewritten: list[str]) -> None:
    sys.argv[:] = [sys.argv[0], *rewritten]


def start_safely(argv: list[str]) -> int:
    parsed = engine_qa.parser().parse_args(argv)
    if parsed.command != "start":
        raise engine_qa.QaError("start_safely sólo admite el comando start.")

    base = sandbox_root_base()
    base.mkdir(parents=True, exist_ok=True)
    sandbox = base / f"engine-{uuid.uuid4().hex[:12]}"
    copy_frozen_engine(sandbox)
    os.environ["STUDY_ENGINE_QA_ROOT"] = str(qa_root())
    courses_root = (sandbox / "materias").resolve()
    os.environ["STUDY_ENGINE_QA_COURSES_ROOT"] = str(courses_root)
    patch_engine_module(sandbox)

    try:
        result = engine_qa.start_run(
            qa_root(),
            courses_root,
            parsed.budget,
            parsed.seed,
            parsed.provider,
        )
    except Exception:
        shutil.rmtree(sandbox, ignore_errors=True)
        raise

    run_dir = Path(str(result["run_dir"])).resolve()
    try:
        install_live_guard(run_dir, sandbox)
    except Exception:
        manifest = engine_qa.manifest_for(run_dir)
        manifest.update(
            {
                "blocked": True,
                "block_reason": "safety-wrapper-initialization-failed",
            }
        )
        engine_qa.save_manifest(run_dir, manifest)
        raise

    # The wrapper owns the success output so a caller never sees a successful
    # start before the frozen sandbox and live-checkout guard are both ready.
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def continue_safely(argv: list[str]) -> int:
    os.environ["STUDY_ENGINE_QA_ROOT"] = str(qa_root())
    run_dir = resolve_live_run(argv)
    guard = load_live_guard(run_dir)
    verify_live_checkout(run_dir, guard)
    sandbox = Path(str(guard["sandbox_root"])).resolve()
    patch_engine_module(sandbox)
    os.environ["STUDY_ENGINE_QA_COURSES_ROOT"] = str((sandbox / "materias").resolve())
    rewritten = validate_exec_tokens(run_dir, argv, sandbox)
    _replace_argv(rewritten)
    return engine_qa.main()


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        return engine_qa.main()
    if argv[0] == "history":
        os.environ["STUDY_ENGINE_QA_ROOT"] = str(qa_root())
        return engine_qa.main()
    try:
        if argv[0] == "start":
            return start_safely(argv)
        return continue_safely(argv)
    except (engine_qa.QaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
