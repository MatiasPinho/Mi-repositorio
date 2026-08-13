#!/usr/bin/env python3
"""Canonical Engine QA RPC process entrypoint.

Exit codes describe transport health only:
- 0: request parsed and a structured response was produced;
- 2: request/response transport itself failed.

Workflow/engine rejections are returned as ``transport_ok=true, ok=false`` so an
agent can classify the experiment instead of mistaking them for shell failures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import engine_qa  # noqa: E402
from scripts import engine_qa_rpc as rpc  # noqa: E402
from scripts import engine_qa_rpc_policy as policy  # noqa: E402
from scripts import engine_qa_safe as safe  # noqa: E402


def transport_failure(response_target: str | None, exc: BaseException) -> int:
    payload: dict[str, Any] = {
        "ok": False,
        "transport_ok": False,
        "engine_invoked": False,
        "protocol_version": rpc.PROTOCOL_VERSION,
        "error": f"{type(exc).__name__}: {exc}",
    }
    try:
        rpc.write_response(response_target, payload)
    except Exception:
        safe.emit_json(payload)
    return 2


def main() -> int:
    args = rpc.parser().parse_args()
    response_target = args.response_file

    # Phase 0: validate where the response may be written before dispatching any
    # stateful command. A bad response path must not execute/mutate the QA run.
    try:
        if response_target:
            rpc._protocol_path(response_target, rpc.RESPONSES_SUBDIR)
    except (rpc.RpcError, OSError, ValueError) as exc:
        return transport_failure(None, exc)

    # Phase 1: protocol input. Failures here are genuine transport failures.
    try:
        request = rpc.read_request(args.request_file)
    except (rpc.RpcError, OSError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        return transport_failure(response_target, exc)

    request_id = request.get("request_id")

    # Phase 2: workflow dispatch. Rejections are valid structured responses, not
    # broken transport. This includes incomplete campaigns, bad QA operations,
    # guard rejections, evidence-policy rejections and unresolved run ids.
    try:
        command = str(request.get("command", ""))
        if command == "hypothesis":
            policy.validate_hypothesis_request(request)
        if command == "experiment-result":
            policy.require_valid_evidence(request)

        result = rpc.dispatch(request)

        if command == "hypothesis":
            policy.annotate_pending_hypothesis(request, result)
    except (
        rpc.RpcError,
        policy.EvidenceError,
        engine_qa.QaError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        result = {
            "ok": False,
            "transport_ok": True,
            "engine_invoked": False,
            "protocol_version": rpc.PROTOCOL_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
        }

    result.setdefault("transport_ok", True)
    result.setdefault("protocol_version", rpc.PROTOCOL_VERSION)
    if request_id is not None:
        result["request_id"] = request_id

    # Phase 3: protocol output. Failure to persist the response is a transport
    # failure even if the workflow itself was valid.
    try:
        rpc.write_response(response_target, result)
    except (rpc.RpcError, OSError, ValueError, UnicodeError) as exc:
        return transport_failure(None, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
