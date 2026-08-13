#!/usr/bin/env python3
"""Evidence policy for canonical Engine QA RPC campaigns.

The transport keeps experiment counting honest by requiring a VALID result to
have mechanical evidence matching the hypothesis mode. This policy is applied
by ``engine_qa_rpc_entry.py`` before ``experiment-result`` reaches the legacy
harness counters.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import engine_qa
from scripts import engine_qa_safe as safe

EVIDENCE_MODES = {"engine", "guard", "state"}


class EvidenceError(RuntimeError):
    pass


def _mode(value: Any) -> str:
    mode = "engine" if value is None else str(value).strip().lower()
    if mode not in EVIDENCE_MODES:
        raise EvidenceError(f"evidence_mode must be one of {sorted(EVIDENCE_MODES)}")
    return mode


def validate_hypothesis_request(request: dict[str, Any]) -> str:
    """Validate and normalize the evidence mode before creating a hypothesis."""
    return _mode(request.get("evidence_mode"))


def _resolve_run(request: dict[str, Any]) -> Path:
    qa_run = str(request.get("qa_run") or "latest")
    return engine_qa.resolve_run(safe.qa_root(), qa_run)


def annotate_pending_hypothesis(request: dict[str, Any], result: dict[str, Any]) -> None:
    """Persist evidence intent alongside the pending experiment."""
    if not result.get("ok"):
        return
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    pending = manifest.get("pending_experiment")
    if not isinstance(pending, dict):
        raise EvidenceError("hypothesis completed without a pending experiment")
    mode = _mode(request.get("evidence_mode"))
    pending["evidence_mode"] = mode
    manifest["pending_experiment"] = pending
    engine_qa.save_manifest(run_dir, manifest)
    result["evidence_mode"] = mode


def _journal_since(run_dir: Path, step: int) -> list[dict[str, Any]]:
    path = run_dir / "journal.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and int(row.get("step", 0) or 0) > step:
            rows.append(row)
    return rows


def _qualifying_steps(mode: str, rows: list[dict[str, Any]]) -> list[int]:
    steps: list[int] = []
    for row in rows:
        kind = str(row.get("kind", ""))
        qualifies = False
        if mode == "engine":
            qualifies = kind in {"rpc-exec", "rpc-exec-timeout"} and row.get("engine_invoked") is True
        elif mode == "guard":
            qualifies = kind == "rpc-exec-rejected" and row.get("engine_invoked") is False
        elif mode == "state":
            qualifies = kind in {"mutation", "check", "checkpoint"}
        if qualifies:
            steps.append(int(row.get("step", 0) or 0))
    return steps


def require_valid_evidence(request: dict[str, Any]) -> dict[str, Any] | None:
    """Reject VALID classification when the declared experiment was not exercised."""
    if str(request.get("status", "")).strip().lower() != "valid":
        return None
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    pending = manifest.get("pending_experiment")
    if not isinstance(pending, dict):
        raise EvidenceError("No pending experiment to validate")
    mode = _mode(pending.get("evidence_mode"))
    hypothesis_step = int(pending.get("hypothesis_step", 0) or 0)
    rows = _journal_since(run_dir, hypothesis_step)
    steps = _qualifying_steps(mode, rows)
    if not steps:
        descriptions = {
            "engine": "an engine invocation (rpc-exec/rpc-exec-timeout with engine_invoked=true)",
            "guard": "a guard rejection (rpc-exec-rejected with engine_invoked=false)",
            "state": "a state operation (mutation/check/checkpoint)",
        }
        raise EvidenceError(
            f"Cannot mark experiment VALID: evidence_mode={mode} requires {descriptions[mode]} after the hypothesis"
        )
    return {"evidence_mode": mode, "evidence_steps": steps}
