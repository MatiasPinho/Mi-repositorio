#!/usr/bin/env python3
"""Audit-quality hardening for canonical Engine QA RPC campaigns.

This module does not execute QA by itself. The canonical process entrypoint
installs its runtime compatibility patches and calls the hooks around hypothesis,
experiment-result and finish operations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts import engine_qa
from scripts import engine_qa_rpc as rpc
from scripts import engine_qa_rpc_policy as policy
from scripts import engine_qa_safe as safe

REPLAY_TEXT_LIMIT = 1200
REPLACEMENT_KINDS = {"retry", "distinct"}
_PATCHED = False


class AuditQualityError(RuntimeError):
    pass


def _resolve_run(request: dict[str, Any]) -> Path:
    return engine_qa.resolve_run(safe.qa_root(), str(request.get("qa_run") or "latest"))


def _all_journal(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "journal.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _compact_text(value: str) -> tuple[str, dict[str, Any]]:
    meta = {
        "chars": len(value),
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "truncated": len(value) > REPLAY_TEXT_LIMIT,
    }
    if len(value) <= REPLAY_TEXT_LIMIT:
        return value, meta
    half = REPLAY_TEXT_LIMIT // 2
    return value[:half] + "\n...[replay compacted]...\n" + value[-half:], meta


def compact_journal(run_dir: Path) -> list[dict[str, Any]]:
    """Return the complete journal while bounding large stdout/stderr payloads."""
    compact: list[dict[str, Any]] = []
    for source in _all_journal(run_dir):
        row = dict(source)
        for field in ("stdout", "stderr"):
            value = row.get(field)
            if isinstance(value, str):
                excerpt, meta = _compact_text(value)
                row[field] = excerpt
                row[f"{field}_meta"] = meta
        compact.append(row)
    return compact


def category_counts(rows: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    valid: dict[str, int] = {}
    attempted: dict[str, int] = {}
    for row in rows:
        if row.get("kind") != "experiment-result":
            continue
        category = str(row.get("category") or "unknown")
        attempted[category] = attempted.get(category, 0) + 1
        if row.get("status") == "valid":
            valid[category] = valid.get(category, 0) + 1
    return dict(sorted(valid.items())), dict(sorted(attempted.items()))


def _render_study_validate_exec_args(run_dir: Path, script: str, args: list[str]) -> tuple[Path, list[str]]:
    """Legacy exec validator variant where render_study --course is display text."""
    if script not in engine_qa.ALLOWED_SCRIPTS:
        raise engine_qa.QaError(f"Script no permitido: {script}")
    target = engine_qa.ROOT / script if script == "study.py" else engine_qa.SCRIPTS / script
    if not target.is_file():
        raise engine_qa.QaError(f"Script inexistente: {target}")
    expanded = [engine_qa.expand_arg(v, run_dir) for v in args]
    course = engine_qa.course_for(run_dir).resolve()
    if script == "study.py" and course.name not in " ".join(expanded) and str(course) not in expanded:
        raise engine_qa.QaError("study.py sólo puede apuntar a la materia QA del run.")
    if script != "render_study.py":
        for idx, value in enumerate(expanded):
            if value == "--course" and idx + 1 < len(expanded) and Path(expanded[idx + 1]).resolve() != course:
                raise engine_qa.QaError("--course debe apuntar a la materia QA del run.")
    return target, expanded


def _render_study_prepare_exec_args(run_dir: Path, sandbox: Path, script: str, args: list[str]) -> list[str]:
    if script not in engine_qa.ALLOWED_SCRIPTS:
        raise engine_qa.QaError(f"Script no permitido: {script}")
    course = engine_qa.course_for(run_dir).resolve()
    allowed_roots = (sandbox.resolve(), run_dir.resolve(), safe.REAL_REPORTS_ROOT.resolve())
    expanded = [safe._expand_safe_token(token, course, run_dir, sandbox) for token in args]
    for idx, token in enumerate(expanded):
        value = token.split("=", 1)[1] if token.startswith("--") and "=" in token else token
        safe._validate_path_value(value, allowed_roots)
        if script != "render_study.py":
            if token.startswith("--course="):
                supplied = Path(token.split("=", 1)[1]).resolve()
                if supplied != course:
                    raise engine_qa.QaError("--course debe apuntar a la materia QA del run.")
            if token == "--course" and idx + 1 < len(expanded):
                supplied = Path(expanded[idx + 1]).resolve()
                if supplied != course:
                    raise engine_qa.QaError("--course debe apuntar a la materia QA del run.")
    if script == "study.py" and str(course) not in expanded and course.name not in expanded:
        raise engine_qa.QaError("study.py debe recibir exactamente @course o @slug del run.")
    return expanded


def install_runtime_patches() -> None:
    """Install the render_study course-label compatibility patch once per process."""
    global _PATCHED
    if _PATCHED:
        return
    original_legacy = engine_qa.validate_exec_args
    original_rpc = rpc._prepare_exec_args

    def legacy(run_dir: Path, script: str, args: list[str]) -> tuple[Path, list[str]]:
        if script == "render_study.py":
            return _render_study_validate_exec_args(run_dir, script, args)
        return original_legacy(run_dir, script, args)

    def structured(run_dir: Path, sandbox: Path, script: str, args: list[str]) -> list[str]:
        if script == "render_study.py":
            return _render_study_prepare_exec_args(run_dir, sandbox, script, args)
        return original_rpc(run_dir, sandbox, script, args)

    engine_qa.validate_exec_args = legacy
    rpc._prepare_exec_args = structured
    _PATCHED = True


def validate_hypothesis_replacement(request: dict[str, Any]) -> dict[str, Any] | None:
    """Require the next hypothesis to explicitly account for the last INVALID attempt."""
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    required = manifest.get("replacement_required")
    replacement_fields_present = "replaces_attempt" in request or "replacement_kind" in request
    if not isinstance(required, dict):
        if replacement_fields_present:
            raise AuditQualityError("replacement fields supplied but no INVALID attempt is awaiting replacement")
        return None

    replaces = request.get("replaces_attempt")
    if isinstance(replaces, bool) or not isinstance(replaces, int):
        raise AuditQualityError("next hypothesis must declare integer replaces_attempt after an INVALID attempt")
    expected_attempt = int(required.get("attempt", 0) or 0)
    if replaces != expected_attempt:
        raise AuditQualityError(f"replaces_attempt must reference INVALID attempt {expected_attempt}")
    kind = str(request.get("replacement_kind") or "").strip().lower()
    if kind not in REPLACEMENT_KINDS:
        raise AuditQualityError(f"replacement_kind must be one of {sorted(REPLACEMENT_KINDS)}")

    invariant = str(request.get("invariant") or "")
    category = str(request.get("category") or "")
    text = str(request.get("text") or "")
    if kind == "retry":
        if invariant != str(required.get("invariant") or "") or category != str(required.get("category") or ""):
            raise AuditQualityError("replacement_kind=retry must keep the INVALID invariant and category")
    else:
        same = (
            invariant == str(required.get("invariant") or "")
            and category == str(required.get("category") or "")
            and text == str(required.get("text") or "")
        )
        if same:
            raise AuditQualityError("replacement_kind=distinct must describe a genuinely different hypothesis")
    return {"replaces_attempt": replaces, "replacement_kind": kind, "invalid": dict(required)}


def after_hypothesis(request: dict[str, Any], result: dict[str, Any], replacement: dict[str, Any] | None) -> None:
    if not replacement or not result.get("ok"):
        return
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    pending = manifest.get("pending_experiment")
    if not isinstance(pending, dict):
        raise AuditQualityError("replacement hypothesis completed without pending experiment")
    pending["replaces_attempt"] = replacement["replaces_attempt"]
    pending["replacement_kind"] = replacement["replacement_kind"]
    manifest["pending_experiment"] = pending
    manifest["replacement_required"] = None
    engine_qa.save_manifest(run_dir, manifest)
    engine_qa.journal(
        run_dir,
        "replacement-link",
        replaces_attempt=replacement["replaces_attempt"],
        replacement_attempt=pending.get("attempt"),
        replacement_kind=replacement["replacement_kind"],
        invariant=pending.get("invariant"),
        category=pending.get("category"),
    )


def _row_by_step(rows: list[dict[str, Any]], step: int) -> dict[str, Any] | None:
    for row in rows:
        if int(row.get("step", 0) or 0) == step:
            return row
    return None


def require_unique_valid_evidence(request: dict[str, Any], evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    """Reject reuse of the same mechanical evidence on the same workspace state."""
    if str(request.get("status") or "").strip().lower() != "valid" or not evidence:
        return None
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    pending = manifest.get("pending_experiment")
    if not isinstance(pending, dict):
        raise AuditQualityError("No pending experiment while checking evidence uniqueness")
    rows = _all_journal(run_dir)
    evidence_rows = []
    for step in evidence.get("evidence_steps", []):
        row = _row_by_step(rows, int(step))
        if row is not None:
            evidence_rows.append(
                {
                    key: row.get(key)
                    for key in (
                        "kind", "script", "request_args", "expanded_args", "returncode", "ok",
                        "engine_invoked", "op", "path", "dest", "label", "issues", "invariants_checked"
                    )
                    if key in row
                }
            )
    course = engine_qa.course_for(run_dir)
    workspace = engine_qa.workspace_snapshot(course)["digest"]
    payload = {
        "mode": evidence.get("evidence_mode"),
        "workspace": workspace,
        "evidence": evidence_rows,
    }
    signature = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    used = list(manifest.get("valid_evidence_signatures", []))
    prior = next((row for row in used if isinstance(row, dict) and row.get("signature") == signature), None)
    if prior:
        raise AuditQualityError(
            "Cannot mark experiment VALID: identical mechanical evidence was already counted "
            f"on the same workspace state by attempt {prior.get('attempt')}"
        )
    return {
        "signature": signature,
        "attempt": pending.get("attempt"),
        "invariant": pending.get("invariant"),
        "category": pending.get("category"),
        "evidence_mode": evidence.get("evidence_mode"),
        "workspace_sha256": workspace,
        "evidence_steps": list(evidence.get("evidence_steps", [])),
    }


def after_experiment_result(request: dict[str, Any], result: dict[str, Any], signature_row: dict[str, Any] | None) -> None:
    if not result.get("ok"):
        return
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    status = str(request.get("status") or "").strip().lower()
    if status == "valid" and signature_row:
        rows = list(manifest.get("valid_evidence_signatures", []))
        rows.append(signature_row)
        manifest["valid_evidence_signatures"] = rows[-500:]
    elif status == "invalid":
        invalid_rows = list(manifest.get("invalid_experiment_rows", []))
        latest = invalid_rows[-1] if invalid_rows else {}
        manifest["replacement_required"] = {
            "attempt": result.get("attempt"),
            "invariant": latest.get("invariant"),
            "category": latest.get("category"),
            "text": latest.get("text", ""),
            "reason": latest.get("reason"),
        }
        result["replacement_required"] = dict(manifest["replacement_required"])
    engine_qa.save_manifest(run_dir, manifest)


def enrich_invalid_row_before_dispatch(request: dict[str, Any]) -> None:
    """Preserve the original hypothesis text in INVALID audit rows."""
    if str(request.get("status") or "").strip().lower() != "invalid":
        return
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    pending = manifest.get("pending_experiment")
    if isinstance(pending, dict):
        manifest["invalid_pending_text"] = str(pending.get("text") or "")
        engine_qa.save_manifest(run_dir, manifest)


def repair_invalid_row_after_dispatch(request: dict[str, Any], result: dict[str, Any]) -> None:
    if str(request.get("status") or "").strip().lower() != "invalid" or not result.get("ok"):
        return
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    text = str(manifest.pop("invalid_pending_text", ""))
    rows = list(manifest.get("invalid_experiment_rows", []))
    if rows and isinstance(rows[-1], dict):
        rows[-1]["text"] = text
        manifest["invalid_experiment_rows"] = rows
    engine_qa.save_manifest(run_dir, manifest)


def enrich_finish_result(request: dict[str, Any], result: dict[str, Any]) -> None:
    if not result.get("ok") and not result.get("report"):
        return
    run_dir = _resolve_run(request)
    manifest = engine_qa.manifest_for(run_dir)
    journal = compact_journal(run_dir)
    valid_by_category, attempted_by_category = category_counts(journal)
    invalid_rows = list(manifest.get("invalid_experiment_rows", []))
    replacements = [row for row in journal if row.get("kind") == "replacement-link"]
    signatures = list(manifest.get("valid_evidence_signatures", []))
    extras = {
        "valid_by_category": valid_by_category,
        "attempted_by_category": attempted_by_category,
        "invalid_rows": invalid_rows,
        "replacement_rows": replacements,
        "unique_evidence_signatures": len(signatures),
        "journal_steps_exported": len(journal),
        "journal_complete": True,
    }
    result.update(extras)

    report_path = run_dir / "report.json"
    report = engine_qa.read_json(report_path, {}) or {}
    report.update(extras)
    engine_qa.write_json(report_path, report)

    md_path = run_dir / "report.md"
    if md_path.is_file():
        lines = md_path.read_text(encoding="utf-8").rstrip().splitlines()
        lines += ["", "## Calidad de auditoría", ""]
        lines += [f"- Journal completo exportado: **sí** ({len(journal)} pasos)."]
        lines += [f"- Evidencias mecánicas únicas contabilizadas: **{len(signatures)}**."]
        lines += [f"- Intentos INVALID preservados: **{len(invalid_rows)}**."]
        lines += ["", "### Válidos por categoría"]
        lines += [f"- `{key}`: **{value}**" for key, value in valid_by_category.items()] or ["- sin categorías válidas"]
        if invalid_rows:
            lines += ["", "### Intentos INVALID"]
            lines += [
                f"- intento {row.get('attempt')}: `{row.get('category')}` / `{row.get('invariant')}` — {row.get('reason')}"
                for row in invalid_rows
            ]
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    exported = result.get("exported")
    if exported:
        destination = Path(str(exported))
        replay = {
            "version": 2,
            "run_id": manifest.get("run_id"),
            "seed": manifest.get("seed"),
            "course_slug": manifest.get("course_slug"),
            "journal": journal,
            **extras,
            "transport_protocol": manifest.get("transport_protocol"),
            "protocol_version": manifest.get("qa_protocol_version"),
            "note": "Complete compact replay. stdout/stderr are bounded with hashes and character counts.",
        }
        engine_qa.write_json(destination / "replay.json", replay)
        engine_qa.write_json(destination / "report.json", report)
        if md_path.is_file():
            (destination / "report.md").write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
