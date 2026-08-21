#!/usr/bin/env python3
"""Sticky engine-integrity guard for commands executed inside a study run.

The normal finish check proves the engine is unchanged *at finish time*. This
guard closes the transient-edit loophole: every project command launched through
``scripts/venv_exec.py`` first compares the live engine with the snapshot stored
when the run started. If drift is observed, a run-local violation marker is
written before the target command can execute. Reverting the engine afterwards
does not clear that marker.

This is an integrity invariant, not a security boundary against an executor that
intentionally replaces the guard itself or bypasses the documented command path.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
VIOLATION_FILE = "00-engine-violation.json"

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


class EngineGuardError(RuntimeError):
    pass


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def engine_snapshot() -> dict[str, str]:
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
            digest = _sha(path)
            if digest:
                rows[rel.as_posix()] = digest
    for rel_text in ENGINE_PROTECTED_FILES:
        path = ROOT / rel_text
        digest = _sha(path)
        if digest:
            rows[Path(rel_text).as_posix()] = digest
    return dict(sorted(rows.items()))


def snapshot_issues(before: object, after: dict[str, str] | None = None) -> list[str]:
    if not isinstance(before, dict):
        return ["missing-engine-snapshot"]
    current = after or engine_snapshot()
    before_keys = set(map(str, before))
    after_keys = set(current)
    issues: list[str] = []
    for rel in sorted(after_keys - before_keys):
        issues.append(f"engine-added:{rel}")
    for rel in sorted(before_keys - after_keys):
        issues.append(f"engine-removed:{rel}")
    for rel in sorted(before_keys & after_keys):
        if str(before.get(rel) or "") != str(current.get(rel) or ""):
            issues.append(f"engine-modified:{rel}")
    return issues


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _run_ancestor(path: Path) -> Path | None:
    resolved = path.resolve(strict=False)
    start = resolved if resolved.is_dir() else resolved.parent
    for candidate in (start, *start.parents):
        manifest = candidate / "manifest.json"
        if not manifest.is_file():
            continue
        parts = candidate.parts
        try:
            study_idx = parts.index(".study")
        except ValueError:
            continue
        if study_idx + 1 < len(parts) and parts[study_idx + 1] == "runs":
            return candidate
    return None


def discover_runs(argv: Iterable[str]) -> list[Path]:
    runs: dict[str, Path] = {}
    for raw in argv:
        token = str(raw).strip()
        if not token:
            continue
        if token.startswith("--") and "=" in token:
            token = token.split("=", 1)[1].strip()
        elif token.startswith("-"):
            continue
        if not token:
            continue
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        run = _run_ancestor(candidate)
        if run is not None:
            runs[str(run.resolve())] = run.resolve()
    return list(runs.values())


def guard_run(run: Path, *, command: list[str] | None = None) -> None:
    run = run.resolve()
    marker = run / VIOLATION_FILE
    if marker.is_file():
        prior = _load_json(marker)
        raise EngineGuardError(
            "run already invalidated by engine mutation: "
            + ", ".join(map(str, prior.get("issues", [])))
        )

    manifest = _load_json(run / "manifest.json")
    if not manifest or manifest.get("status") != "running":
        return
    issues = snapshot_issues(manifest.get("engine_snapshot"))
    if not issues:
        return

    payload = {
        "version": 1,
        "invalid": True,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "issues": issues,
        "command": list(command or []),
    }
    _atomic_json(marker, payload)
    raise EngineGuardError("engine mutation detected: " + ", ".join(issues))


def guard_argv(argv: Iterable[str]) -> None:
    command = list(argv)
    for run in discover_runs(command):
        guard_run(run, command=command)
