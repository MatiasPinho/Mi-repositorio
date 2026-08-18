#!/usr/bin/env python3
"""Deterministic fingerprint for the visual pedagogy/review policy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

VISUAL_POLICY_FILES = (
    "rules/visual/figures.md",
    "rules/evaluation/visual-rubric.md",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_policy() -> dict[str, str]:
    """Return the exact rule hashes that define figure design/review semantics."""
    return {rel: sha256_file(ROOT / rel) for rel in VISUAL_POLICY_FILES}


def fingerprint(policy: dict[str, str] | None = None) -> str:
    """Hash a canonical policy map so run evidence can bind the active rubric."""
    payload: dict[str, Any] = {
        "version": 1,
        "files": dict(sorted((policy or current_policy()).items())),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def current_fingerprint() -> str:
    return fingerprint(current_policy())
