#!/usr/bin/env python3
"""Structured transport for Engine QA.

Complex arguments never travel through provider/shell argv. The caller writes a
UTF-8 JSON request under ``.study/engine-qa/requests/`` (or sends JSON on stdin)
and this process writes the UTF-8 response under ``responses/``. The transport
reuses the existing frozen-sandbox/live-checkout guards from engine_qa_safe.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import engine_qa  # noqa: E402
from scripts import engine_qa_safe as safe  # noqa: E402

PROTOCOL_VERSION = 2
REQUESTS_SUBDIR = "requests"
RESPONSES_SUBDIR = "responses"


class RpcError(RuntimeError):
    pass


def _as_dict(value: Any, name: str = "request") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RpcError(f"{name} must be a JSON object")
    return value


def _as_str(value: Any, name: str, *, default: str | None = None) -> str:
    if value is None and default is not None:
        return default
    if not isinstance(value, str):
        raise RpcError(f"{name} must be a string")
    return value


def _as_int(value: Any, name: str, *, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise RpcError(f"{name} must be an integer")
    return value


def _as_bool(value: Any, name: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise RpcError(f"{name} must be a boolean")
    return value


def _as_str_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RpcError(f"{name} must be an array of strings")
    return list(value)


def _protocol_path(raw: str, subdir: str, *, must_exist: bool = False) -> Path:
    candidate = Path(raw).resolve()
    base = (safe.qa_root() / subdir).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise RpcError(f"Protocol file must stay under {base}") from exc
    if must_exist and not candidate.is_file():
        raise RpcError(f"Protocol file does not exist: {candidate}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def read_request(request_file: str | None) -> dict[str, Any]:
    if request_file:
        path = _protocol_path(request_file, REQUESTS_SUBDIR, must_exist=True)
        raw = path.read_text(encoding="utf-8-sig")
    else:
        raw = sys.stdin.buffer.read().decode("utf-8-sig")
    if not raw.strip():
        raise RpcError("Empty Engine QA RPC request")
    return _as_dict(json.loads(raw), "request")


def write_response(response_file: str | None, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if response_file:
        path = _protocol_path(response_file, RESPONSES_SUBDIR)
        path.write_text(payload, encoding="utf-8", newline="\n")
    else:
        safe.emit_json(value)


def _setup_existing_run(qa_run: str) -> tuple[Path, Path]:
    os.environ["STUDY_ENGINE_QA_ROOT"] = str(safe.qa_root())
    run_dir = engine_qa.resolve_run(safe.qa_root(), qa_run)
    guard = safe.load_live_guard(run_dir)
    safe.verify_live_checkout(run_dir, guard)
    sandbox = Path(str(guard["sandbox_root"])).resolve()
    safe.patch_engine_module(sandbox)
    os.environ["STUDY_ENGINE_QA_COURSES_ROOT"] = str((sandbox / "materias").resolve())
    _ensure_metrics(run_dir)
    return run_dir, sandbox


def _ensure_metrics(run_dir: Path) -> dict[str, Any]:
    manifest = engine_qa.manifest_for(run_dir)
    changed = False
    valid = int(manifest.get("experiments", 0) or 0)
    defaults: dict[str, Any] = {
        "qa_protocol_version": PROTOCOL_VERSION,
        "transport_protocol": "json-request-file-v1",
        "valid_experiments": valid,
        "attempted_experiments": valid,
        "invalid_experiments": 0,
        "pending_experiment": None,
        "invalid_experiment_rows": [],
    }
    for key, value in defaults.items():
        if key not in manifest:
            manifest[key] = value
            changed = True
    if int(manifest.get("valid_experiments", valid) or 0) != valid:
        manifest["valid_experiments"] = valid
        changed = True
    if changed:
        engine_qa.save_manifest(run_dir, manifest)
    return manifest


def rpc_start(request: dict[str, Any]) -> dict[str, Any]:
    budget = _as_int(request.get("budget"), "budget", default=25)
    seed = _as_int(request.get("seed"), "seed", default=1)
    provider = _as_str(request.get("provider"), "provider", default="unknown")

    base = safe.sandbox_root_base()
    base.mkdir(parents=True, exist_ok=True)
    sandbox = base / f"engine-{uuid.uuid4().hex[:12]}"
    safe.copy_frozen_engine(sandbox)
    os.environ["STUDY_ENGINE_QA_ROOT"] = str(safe.qa_root())
    courses_root = (sandbox / "materias").resolve()
    os.environ["STUDY_ENGINE_QA_COURSES_ROOT"] = str(courses_root)
    safe.patch_engine_module(sandbox)

    try:
        result = safe.call_with_stdout_to_stderr(
            engine_qa.start_run,
            safe.qa_root(),
            courses_root,
            budget,
            seed,
            provider,
        )
    except Exception:
        shutil.rmtree(sandbox, ignore_errors=True)
        raise

    run_dir = Path(str(result["run_dir"])).resolve()
    try:
        safe.install_live_guard(run_dir, sandbox)
        manifest = engine_qa.manifest_for(run_dir)
        manifest.update(
            {
                "qa_protocol_version": PROTOCOL_VERSION,
                "transport_protocol": "json-request-file-v1",
                "valid_experiments": 0,
                "attempted_experiments": 0,
                "invalid_experiments": 0,
                "pending_experiment": None,
                "invalid_experiment_rows": [],
            }
        )
        engine_qa.save_manifest(run_dir, manifest)
        engine_qa.journal(
            run_dir,
            "rpc-transport",
            protocol_version=PROTOCOL_VERSION,
            transport="json-request-file-v1",
        )
    except Exception:
        manifest = engine_qa.manifest_for(run_dir)
        manifest.update({"blocked": True, "block_reason": "rpc-initialization-failed"})
        engine_qa.save_manifest(run_dir, manifest)
        raise

    return {
        **result,
        "transport_ok": True,
        "protocol_version": PROTOCOL_VERSION,
        "valid_experiments": 0,
        "invalid_experiments": 0,
        "attempted_experiments": 0,
    }


def rpc_info(run_dir: Path) -> dict[str, Any]:
    manifest = _ensure_metrics(run_dir)
    pending = manifest.get("pending_experiment")
    return {
        "ok": True,
        "transport_ok": True,
        "run_id": manifest.get("run_id"),
        "course_slug": manifest.get("course_slug"),
        "course_path": manifest.get("course_path"),
        "budget": int(manifest.get("budget", 0) or 0),
        "experiments": int(manifest.get("experiments", 0) or 0),
        "valid_experiments": int(manifest.get("experiments", 0) or 0),
        "attempted_experiments": int(manifest.get("attempted_experiments", 0) or 0),
        "invalid_experiments": int(manifest.get("invalid_experiments", 0) or 0),
        "pending_experiment": pending,
        "findings": int(manifest.get("findings", 0) or 0),
        "blocked": bool(manifest.get("blocked")),
        "coverage": list(manifest.get("coverage", [])),
        "run_dir": str(run_dir),
        "protocol_version": int(manifest.get("qa_protocol_version", PROTOCOL_VERSION) or PROTOCOL_VERSION),
    }


def rpc_hypothesis(run_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
    manifest = engine_qa.assert_not_blocked(run_dir)
    _ensure_metrics(run_dir)
    manifest = engine_qa.manifest_for(run_dir)
    if manifest.get("pending_experiment"):
        raise RpcError("Complete the pending experiment before starting another hypothesis")
    valid = int(manifest.get("experiments", 0) or 0)
    budget = int(manifest.get("budget", 0) or 0)
    if valid >= budget:
        raise RpcError(f"Valid experiment budget exhausted: {valid}/{budget}")
    attempted = int(manifest.get("attempted_experiments", 0) or 0) + 1
    max_attempts = min(500, budget * 2 + 25)
    if attempted > max_attempts:
        raise RpcError(f"Too many invalid/retried experiments: {attempted - 1}/{max_attempts}")
    invariant = _as_str(request.get("invariant"), "invariant")
    category = _as_str(request.get("category"), "category")
    text = _as_str(request.get("text"), "text")
    pending = {
        "attempt": attempted,
        "candidate_valid_number": valid + 1,
        "invariant": invariant,
        "category": category,
        "text": text,
    }
    manifest["attempted_experiments"] = attempted
    manifest["pending_experiment"] = pending
    engine_qa.save_manifest(run_dir, manifest)
    row = engine_qa.journal(
        run_dir,
        "hypothesis",
        attempt=attempted,
        experiment_candidate=valid + 1,
        invariant=invariant,
        category=category,
        text=text,
    )
    pending["hypothesis_step"] = row["step"]
    manifest = engine_qa.manifest_for(run_dir)
    manifest["pending_experiment"] = pending
    engine_qa.save_manifest(run_dir, manifest)
    return {
        "ok": True,
        "transport_ok": True,
        "attempt": attempted,
        "candidate_valid_number": valid + 1,
        "valid_experiments": valid,
        "invalid_experiments": int(manifest.get("invalid_experiments", 0) or 0),
        "remaining_valid": budget - valid,
        "step": row["step"],
    }


def rpc_experiment_result(run_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
    manifest = engine_qa.assert_not_blocked(run_dir)
    _ensure_metrics(run_dir)
    manifest = engine_qa.manifest_for(run_dir)
    pending = manifest.get("pending_experiment")
    if not isinstance(pending, dict):
        raise RpcError("No pending experiment to complete")
    status = _as_str(request.get("status"), "status")
    if status not in {"valid", "invalid"}:
        raise RpcError("status must be valid or invalid")
    reason = _as_str(request.get("reason"), "reason", default="")
    notes = _as_str(request.get("notes"), "notes", default="")
    if status == "invalid" and not reason.strip():
        raise RpcError("invalid experiments require a reason")
    current_steps = int(manifest.get("step_count", 0) or 0)
    hypothesis_step = int(pending.get("hypothesis_step", 0) or 0)
    if current_steps <= hypothesis_step:
        raise RpcError("Record at least one operation/check after the hypothesis before completing it")

    valid = int(manifest.get("experiments", 0) or 0)
    invalid = int(manifest.get("invalid_experiments", 0) or 0)
    coverage = list(manifest.get("coverage", []))
    if status == "valid":
        valid += 1
        manifest["experiments"] = valid
        manifest["valid_experiments"] = valid
        category = str(pending.get("category", "")).strip()
        if category and category not in coverage:
            coverage.append(category)
        manifest["coverage"] = coverage
    else:
        invalid += 1
        manifest["invalid_experiments"] = invalid
        rows = list(manifest.get("invalid_experiment_rows", []))
        rows.append(
            {
                "attempt": pending.get("attempt"),
                "invariant": pending.get("invariant"),
                "category": pending.get("category"),
                "reason": reason,
            }
        )
        manifest["invalid_experiment_rows"] = rows[-100:]
    manifest["pending_experiment"] = None
    engine_qa.save_manifest(run_dir, manifest)
    row = engine_qa.journal(
        run_dir,
        "experiment-result",
        attempt=pending.get("attempt"),
        experiment=(valid if status == "valid" else None),
        status=status,
        reason=reason or None,
        notes=notes or None,
        invariant=pending.get("invariant"),
        category=pending.get("category"),
    )
    budget = int(manifest.get("budget", 0) or 0)
    return {
        "ok": True,
        "transport_ok": True,
        "status": status,
        "attempt": pending.get("attempt"),
        "valid_experiments": valid,
        "invalid_experiments": invalid,
        "attempted_experiments": int(manifest.get("attempted_experiments", 0) or 0),
        "remaining_valid": max(0, budget - valid),
        "step": row["step"],
    }


def _prepare_exec_args(run_dir: Path, sandbox: Path, script: str, args: list[str]) -> list[str]:
    if script not in engine_qa.ALLOWED_SCRIPTS:
        raise engine_qa.QaError(f"Script no permitido: {script}")
    course = engine_qa.course_for(run_dir).resolve()
    allowed_roots = (sandbox.resolve(), run_dir.resolve(), safe.REAL_REPORTS_ROOT.resolve())
    expanded = [safe._expand_safe_token(token, course, run_dir, sandbox) for token in args]
    for idx, token in enumerate(expanded):
        value = token.split("=", 1)[1] if token.startswith("--") and "=" in token else token
        safe._validate_path_value(value, allowed_roots)
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


def rpc_exec(run_dir: Path, sandbox: Path, request: dict[str, Any]) -> dict[str, Any]:
    script = _as_str(request.get("script"), "script")
    args = _as_str_list(request.get("args"), "args")
    timeout = _as_int(request.get("timeout"), "timeout", default=45)
    expect_raw = request.get("expect_code", 0)
    if expect_raw is None:
        expect_code: int | None = None
    else:
        expect_code = _as_int(expect_raw, "expect_code")
    try:
        expanded = _prepare_exec_args(run_dir, sandbox, script, args)
    except (engine_qa.QaError, OSError, ValueError) as exc:
        row = engine_qa.journal(
            run_dir,
            "rpc-exec-rejected",
            script=script,
            request_args=args,
            engine_invoked=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        return {
            "ok": False,
            "transport_ok": True,
            "engine_invoked": False,
            "rejected": True,
            "script": script,
            "request_args": args,
            "error": f"{type(exc).__name__}: {exc}",
            "step": row["step"],
        }
    try:
        result = engine_qa.exec_engine(run_dir, script, expanded, expect_code, timeout)
    except subprocess.TimeoutExpired as exc:
        row = engine_qa.journal(
            run_dir,
            "rpc-exec-timeout",
            script=script,
            request_args=args,
            expanded_args=expanded,
            engine_invoked=True,
            timeout=timeout,
        )
        return {
            "ok": False,
            "transport_ok": True,
            "engine_invoked": True,
            "timed_out": True,
            "script": script,
            "request_args": args,
            "expanded_args": expanded,
            "error": f"TimeoutExpired: {exc}",
            "step": row["step"],
        }
    except (engine_qa.QaError, OSError, ValueError) as exc:
        row = engine_qa.journal(
            run_dir,
            "rpc-exec-rejected",
            script=script,
            request_args=args,
            expanded_args=expanded,
            engine_invoked=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        return {
            "ok": False,
            "transport_ok": True,
            "engine_invoked": False,
            "rejected": True,
            "script": script,
            "request_args": args,
            "expanded_args": expanded,
            "error": f"{type(exc).__name__}: {exc}",
            "step": row["step"],
        }
    result.update(
        {
            "transport_ok": True,
            "engine_invoked": True,
            "request_args": args,
        }
    )
    engine_qa.journal(
        run_dir,
        "rpc-exec",
        script=script,
        request_args=args,
        expanded_args=result.get("expanded_args", expanded),
        returncode=result.get("returncode"),
        ok=result.get("ok"),
        engine_invoked=True,
    )
    return result


def _augment_finish(run_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    manifest = _ensure_metrics(run_dir)
    valid = int(manifest.get("experiments", 0) or 0)
    attempted = int(manifest.get("attempted_experiments", valid) or 0)
    invalid = int(manifest.get("invalid_experiments", 0) or 0)
    extras = {
        "valid_experiments": valid,
        "attempted_experiments": attempted,
        "invalid_experiments": invalid,
        "transport_protocol": "json-request-file-v1",
        "protocol_version": PROTOCOL_VERSION,
    }
    result.update(extras)

    report_path = run_dir / "report.json"
    report = engine_qa.read_json(report_path, {}) or {}
    report.update(extras)
    engine_qa.write_json(report_path, report)

    md_path = run_dir / "report.md"
    if md_path.is_file():
        lines = md_path.read_text(encoding="utf-8").splitlines()
        enriched: list[str] = []
        inserted = False
        for line in lines:
            if line.startswith("- Experimentos:"):
                enriched.append(f"- Experimentos válidos: **{valid}/{report.get('budget', manifest.get('budget'))}**")
                enriched.append(f"- Intentos totales: **{attempted}**")
                enriched.append(f"- Inválidos por arnés/transporte: **{invalid}**")
                inserted = True
            else:
                enriched.append(line)
        if not inserted:
            enriched += [
                "",
                f"- Experimentos válidos: **{valid}/{manifest.get('budget')}**",
                f"- Intentos totales: **{attempted}**",
                f"- Inválidos por arnés/transporte: **{invalid}**",
            ]
        md_path.write_text("\n".join(enriched) + "\n", encoding="utf-8", newline="\n")

    history_path = run_dir.parent.parent / "history.json"
    history = engine_qa.read_json(history_path, {"version": 1, "runs": []}) or {"version": 1, "runs": []}
    for row in reversed(history.get("runs", [])):
        if row.get("run_id") == manifest.get("run_id"):
            row.update(extras)
            break
    engine_qa.write_json(history_path, history)

    exported = result.get("exported")
    if exported:
        destination = Path(str(exported))
        shutil.copy2(report_path, destination / "report.json")
        if md_path.is_file():
            shutil.copy2(md_path, destination / "report.md")
        replay_path = destination / "replay.json"
        replay = engine_qa.read_json(replay_path, {}) or {}
        replay.update(extras)
        engine_qa.write_json(replay_path, replay)
    return result


def rpc_finish(run_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
    manifest = _ensure_metrics(run_dir)
    if manifest.get("pending_experiment"):
        raise RpcError("Cannot finish with a pending experiment; mark it valid or invalid first")
    valid = int(manifest.get("experiments", 0) or 0)
    budget = int(manifest.get("budget", 0) or 0)
    allow_partial = _as_bool(request.get("allow_partial"), "allow_partial", default=False)
    if not manifest.get("blocked") and not allow_partial and valid < budget:
        raise RpcError(f"Campaign incomplete: {valid}/{budget} valid experiments. Invalid attempts do not consume budget.")
    export = _as_bool(request.get("export"), "export", default=True)
    result = engine_qa.finish_run(run_dir, export)
    return _augment_finish(run_dir, result)


def rpc_history() -> dict[str, Any]:
    result = engine_qa.history(safe.qa_root())
    for row in result.get("runs", []):
        valid = int(row.get("valid_experiments", row.get("experiments", 0)) or 0)
        row.setdefault("valid_experiments", valid)
        row.setdefault("attempted_experiments", valid)
        row.setdefault("invalid_experiments", 0)
    result.update({"ok": True, "transport_ok": True, "protocol_version": PROTOCOL_VERSION})
    return result


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    version = request.get("version", PROTOCOL_VERSION)
    if version not in {1, PROTOCOL_VERSION}:
        raise RpcError(f"Unsupported Engine QA RPC version: {version}")
    command = _as_str(request.get("command"), "command")
    if command == "start":
        return rpc_start(request)
    if command == "history":
        return rpc_history()

    qa_run = _as_str(request.get("qa_run"), "qa_run", default="latest")
    run_dir, sandbox = _setup_existing_run(qa_run)
    if command == "info":
        return rpc_info(run_dir)
    if command == "hypothesis":
        return rpc_hypothesis(run_dir, request)
    if command == "experiment-result":
        return rpc_experiment_result(run_dir, request)
    if command == "exec":
        return rpc_exec(run_dir, sandbox, request)
    if command == "mutate":
        result = engine_qa.mutate_course(
            run_dir,
            _as_str(request.get("op"), "op"),
            _as_str(request.get("path"), "path"),
            _as_str(request.get("text"), "text", default=""),
            _as_str(request.get("dest"), "dest", default=""),
            _as_str(request.get("old"), "old", default=""),
            _as_str(request.get("new"), "new", default=""),
        )
        result.update({"transport_ok": True, "engine_invoked": False})
        return result
    if command == "checkpoint":
        result = engine_qa.checkpoint(run_dir, _as_str(request.get("label"), "label"))
        result.update({"transport_ok": True, "engine_invoked": False})
        return result
    if command == "check":
        result = engine_qa.check_invariants(run_dir)
        result.update({"transport_ok": True, "engine_invoked": False})
        return result
    if command == "finding":
        if not _as_bool(request.get("confirmed"), "confirmed", default=False):
            raise RpcError("finding requires confirmed=true")
        result = engine_qa.record_finding(
            run_dir,
            _as_str(request.get("title"), "title"),
            _as_str(request.get("severity"), "severity"),
            _as_str(request.get("invariant"), "invariant"),
            _as_str(request.get("expected"), "expected"),
            _as_str(request.get("actual"), "actual"),
            _as_str(request.get("notes"), "notes", default=""),
            True,
        )
        result.update({"transport_ok": True, "engine_invoked": False})
        return result
    if command == "finish":
        return rpc_finish(run_dir, request)
    raise RpcError(f"Unknown Engine QA RPC command: {command}")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Structured Engine QA request/response transport")
    ap.add_argument("--request-file", help="UTF-8 JSON request under <qa-root>/requests/")
    ap.add_argument("--response-file", help="UTF-8 JSON response under <qa-root>/responses/")
    return ap


def main() -> int:
    args = parser().parse_args()
    response_target = args.response_file
    try:
        request = read_request(args.request_file)
        request_id = request.get("request_id")
        result = dispatch(request)
        result.setdefault("transport_ok", True)
        result.setdefault("protocol_version", PROTOCOL_VERSION)
        if request_id is not None:
            result["request_id"] = request_id
        write_response(response_target, result)
        # Process exit code reports transport health only. Engine/test outcomes are
        # carried by result.ok so expected rejection cases do not break shell loops.
        return 0
    except (RpcError, engine_qa.QaError, OSError, ValueError, json.JSONDecodeError) as exc:
        failure = {
            "ok": False,
            "transport_ok": False,
            "engine_invoked": False,
            "protocol_version": PROTOCOL_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
        }
        try:
            write_response(response_target, failure)
        except Exception:
            safe.emit_json(failure)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
