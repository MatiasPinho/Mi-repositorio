#!/usr/bin/env python3
"""Generate the local OpenCode MCP config for the current operating system.

The project venv lives in a different path on Windows and POSIX, so this file
keeps `opencode.json` machine-local while preserving any existing OpenCode
settings already present in that JSON file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "opencode.json"


def venv_python_command() -> str:
    if os.name == "nt":
        return ".venv/Scripts/python.exe"
    return "./.venv/bin/python"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"No se pudo actualizar {CONFIG_PATH.name}: JSON invalido ({exc})."
        ) from exc

    if not isinstance(data, dict):
        raise SystemExit(f"{CONFIG_PATH.name} debe contener un objeto JSON.")
    return data


def main() -> int:
    data = load_config()
    data.setdefault("$schema", "https://opencode.ai/config.json")

    mcp = data.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        print("ERROR: la clave 'mcp' de opencode.json debe ser un objeto.", file=sys.stderr)
        return 2

    mcp["university-study"] = {
        "type": "local",
        "command": [venv_python_command(), "study.py", "mcp", "serve"],
        "cwd": ".",
        "enabled": True,
        "environment": {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        },
        "timeout": 10000,
    }

    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OpenCode MCP configurado en {CONFIG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
