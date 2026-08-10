#!/usr/bin/env python3
"""Verify that the complete local study environment is ready.

The normal installation lives in the repository-local `.venv` so unrelated global
Python packages cannot break the study system. This preflight also launches Playwright
Chromium once: importing the Python package is not enough because the browser binary is
a separate installation.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VENV = (ROOT / ".venv").resolve()


def _package_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def _python_status() -> dict[str, Any]:
    version = platform.python_version()
    return {
        "ready": sys.version_info >= (3, 10),
        "version": version,
        "required": ">=3.10",
    }


def _venv_status() -> dict[str, Any]:
    try:
        actual = Path(sys.prefix).resolve()
    except OSError:
        actual = Path(sys.prefix)
    ready = actual == EXPECTED_VENV
    return {
        "ready": ready,
        "version": str(actual),
        "required": str(EXPECTED_VENV),
        "reason": None if ready else "not-running-from-project-.venv",
    }


def _mcp_status() -> dict[str, Any]:
    version = _package_version("mcp")
    major = -1
    if version:
        try:
            major = int(version.split(".", 1)[0])
        except ValueError:
            pass
    return {
        "ready": version is not None and major == 1,
        "version": version or "missing",
        "required": ">=1.28,<2",
    }


def _simple_package(distribution: str, required: str) -> dict[str, Any]:
    version = _package_version(distribution)
    return {
        "ready": version is not None,
        "version": version or "missing",
        "required": required,
    }


def _chromium_status(playwright_ready: bool) -> dict[str, Any]:
    if not playwright_ready:
        return {
            "ready": False,
            "version": "unavailable",
            "reason": "playwright-python-missing",
        }
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            version = browser.version
            browser.close()
        return {"ready": True, "version": version}
    except Exception as exc:  # Playwright wraps missing browser/OS dependency errors.
        return {
            "ready": False,
            "version": "missing-or-unlaunchable",
            "reason": str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__,
        }


def capabilities() -> dict[str, Any]:
    python = _python_status()
    venv = _venv_status()
    mcp = _mcp_status()
    pymupdf = _simple_package("PyMuPDF", ">=1.24,<2")
    pillow = _simple_package("Pillow", ">=10")
    playwright = _simple_package("playwright", ">=1.45")
    chromium = _chromium_status(bool(playwright["ready"]))

    checks = {
        "python": python,
        "venv": venv,
        "mcp": mcp,
        "pymupdf": pymupdf,
        "pillow": pillow,
        "playwright": playwright,
        "chromium": chromium,
    }
    ready = all(bool(item.get("ready")) for item in checks.values())
    return {
        "ready": ready,
        "visual_audit": {
            "ready": bool(venv["ready"]) and all(
                bool(checks[name]["ready"])
                for name in ("pymupdf", "pillow", "playwright", "chromium")
            )
        },
        "checks": checks,
        "install": {
            "create_venv": f"{sys.executable} -m venv .venv",
            "python_packages": "python scripts/venv_exec.py -m pip install -r requirements.txt",
            "chromium": "python scripts/venv_exec.py -m playwright install chromium",
            "windows": "INSTALAR-STUDY.bat",
        },
    }


def _print_human(report: dict[str, Any]) -> None:
    print("University Study System - environment check")
    print()
    labels = {
        "python": "Python",
        "venv": "Project venv",
        "mcp": "MCP",
        "pymupdf": "PyMuPDF",
        "pillow": "Pillow",
        "playwright": "Playwright",
        "chromium": "Chromium",
    }
    for key, label in labels.items():
        item = report["checks"][key]
        state = "READY" if item.get("ready") else "MISSING"
        detail = item.get("version", "")
        print(f"{label:<12} {state:<7} {detail}")
        if not item.get("ready") and item.get("reason"):
            print(f"             {item['reason']}")
    visual = "READY" if report["visual_audit"]["ready"] else "MISSING"
    overall = "READY" if report["ready"] else "INCOMPLETE"
    print(f"{'Visual audit':<12} {visual}")
    print()
    print(f"Environment: {overall}")
    if not report["ready"]:
        print("Install/repair with INSTALAR-STUDY.bat on Windows.")
        print("Manual setup: create .venv, then install requirements and Chromium inside it.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify the complete University Study environment")
    sub = ap.add_subparsers(dest="command")
    check = sub.add_parser("check", help="Check project venv, packages and Playwright Chromium")
    check.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.command not in {None, "check"}:
        ap.error("unsupported command")

    report = capabilities()
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
