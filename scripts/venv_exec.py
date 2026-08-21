#!/usr/bin/env python3
"""Re-exec a command with the project's isolated .venv Python.

This shim intentionally depends only on the standard library so it can be launched by
whatever base `python`/`py` the host exposes. All project commands that need installed
packages can then run inside `.venv` without requiring the user's global Python package
set to be clean or compatible.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def main() -> int:
    target = venv_python()
    if not target.is_file():
        print(
            "Carpeta environment is missing. Run INSTALAR-STUDY.bat on Windows "
            "or `bash INSTALAR-STUDY.sh` on Linux.",
            file=sys.stderr,
        )
        return 2
    if len(sys.argv) < 2:
        print("Usage: python scripts/venv_exec.py <python-args...>", file=sys.stderr)
        return 2

    # Every documented study-pipeline command passes through this shim. Guard
    # the run before launching the target so a temporary edit to any protected
    # engine file becomes a sticky run failure even if the edit is reverted
    # before `pipeline_run.py finish`.
    try:
        from run_engine_guard import EngineGuardError, guard_argv
        guard_argv(sys.argv[1:])
    except EngineGuardError as exc:
        print(f"Carpeta run blocked: {exc}", file=sys.stderr)
        return 3

    os.environ["VIRTUAL_ENV"] = str(target.parent.parent)
    path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(target.parent) + (os.pathsep + path if path else "")
    os.execv(str(target), [str(target), *sys.argv[1:]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
