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


def _expected_check_ok(request: dict[str, Any], mode: str) -> bool:
    if "expected_check_ok" not in request:
        return True
    value = request.get("expected_check_ok")
    if mode != "state":
        raise EvidenceError("expected_check_ok is only valid with evidence_mode=state")
    if not isinstance(value, bool):
        raise EvidenceError("expected_check_ok must be a JSON boolean")
    return value


def validate_hypothesis_request(request: dict[str, Any]) -> str:
    """Validate evidence intent and any required replacement link."""
    mode = _mode(request.get("evidence_mode"))
    _expected_check_ok(request, mode)
    replacement = quality.validate_hypothesis_replacement(request)
    if replacement is not None:
        request["_quality_replacement"] = replacement
    return mode


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
    if mode == "state":
        pending["expected_check_ok"] = _expected_check_ok(request, mode)
        result["expected_check_ok"] = pending["expected_check_ok"]
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


def _qualifying_steps(
    mode: str,
    rows: list[dict[str, Any]],
    *,
    expected_check_ok: bool = True,
) -> list[int]:
    steps: list[int] = []
    for row in rows:
        kind = str(row.get("kind", ""))
        qualifies = False
        if mode == "engine":
            qualifies = (
                kind == "rpc-exec"
                and row.get("engine_invoked") is True
                and row.get("ok") is True
            )
        elif mode == "guard":
            qualifies = kind == "rpc-exec-rejected" and row.get("engine_invoked") is False
        elif mode == "state":
            check_rows = [candidate for candidate in rows if str(candidate.get("kind", "")) == "check"]
            if check_rows:
                qualifies = kind == "check" and row.get("ok") is expected_check_ok
            else:
                qualifies = kind in {"mutation", "checkpoint"}
        if qualifies:
            steps.append(int(row.get("step", 0) or 0))
    return steps


def require_valid_evidence(request: dict[str, Any]) -> dict[str, Any] | None:
    """Reject VALID classification when the declared experiment was not exercised."""
    status = str(request.get("status", "")).strip().lower()
    if status != "valid":
        if status == "invalid":
            quality.enrich_invalid_row_before_dispatch(request)
        return None
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    pending = manifest.get("pending_experiment")
    if not isinstance(pending, dict):
        raise EvidenceError("No pending experiment to validate")
    mode = _mode(pending.get("evidence_mode"))
    hypothesis_step = int(pending.get("hypothesis_step", 0) or 0)
    rows = _journal_since(run_dir, hypothesis_step)
    expected_check_ok = bool(pending.get("expected_check_ok", True))
    steps = _qualifying_steps(mode, rows, expected_check_ok=expected_check_ok)
    if not steps:
        descriptions = {
            "engine": "an engine invocation that matched its declared expectation (rpc-exec with engine_invoked=true and ok=true)",
            "guard": "a guard rejection (rpc-exec-rejected with engine_invoked=false)",
            "state": f"a state operation whose check outcome matches expected_check_ok={str(expected_check_ok).lower()}",
        }
        raise EvidenceError(
            f"Cannot mark experiment VALID: evidence_mode={mode} requires {descriptions[mode]} after the hypothesis"
        )
    result = {"evidence_mode": mode, "evidence_steps": steps}
    if mode == "state":
        result["expected_check_ok"] = expected_check_ok
    signature = quality.require_unique_valid_evidence(request, result)
    if signature is not None:
        request["_quality_signature"] = signature
    return result


def _install_audit_quality_patches() -> None:
    """Patch RPC hooks once so audit guarantees apply without changing argv transport."""
    quality.install_runtime_patches()
    if getattr(rpc, "_audit_quality_patched", False):
        return

    original_hypothesis = rpc.rpc_hypothesis
    original_result = rpc.rpc_experiment_result
    original_finish = rpc.rpc_finish

    def hypothesis(run_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
        result = original_hypothesis(run_dir, request)
        replacement = request.get("_quality_replacement")
        if isinstance(replacement, dict):
            quality.after_hypothesis(request, result, replacement)
        return result

    def experiment_result(run_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
        result = original_result(run_dir, request)
        quality.repair_invalid_row_after_dispatch(request, result)
        signature = request.get("_quality_signature")
        quality.after_experiment_result(request, result, signature if isinstance(signature, dict) else None)
        return result

    def finish(run_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
        result = original_finish(run_dir, request)
        quality.enrich_finish_result(request, result)
        return result

    rpc.rpc_hypothesis = hypothesis
    rpc.rpc_experiment_result = experiment_result
    rpc.rpc_finish = finish
    rpc._audit_quality_patched = True


# Imported at the end intentionally: the helper references this module but does
# not use it during import, so the circular module object is already defined.
from scripts import engine_qa_audit_quality as quality  # noqa: E402
from scripts import engine_qa_rpc as rpc  # noqa: E402

_install_audit_quality_patches()
