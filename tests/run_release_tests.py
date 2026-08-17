#!/usr/bin/env python3
"""Run release tests in fresh Python processes to avoid cross-test subprocess leakage."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULES = ["tests.test_actions", "tests.test_v4_action_contracts", "tests.test_pipeline", "tests.test_run_contracts", "tests.test_artifacts", "tests.test_system", "tests.test_cli", "tests.test_material_index_idempotence", "tests.test_unit_layout", "tests.test_topics", "tests.test_visual", "tests.test_notebook_reader", "tests.test_sketch_figures", "tests.test_scene_v2", "tests.test_visual_v2_regressions", "tests.test_summary_runtime_v2", "tests.test_mixed_visual_reuse_v2", "tests.test_infrastructure", "tests.test_mcp", "tests.test_academic_eval", "tests.test_stressed_materials", "tests.test_pdf_stress", "tests.test_semantic_claims", "tests.test_claim_candidates", "tests.test_quiz", "tests.test_quiz_review", "tests.test_engine_qa", "tests.test_engine_qa_safety", "tests.test_engine_qa_findings", "tests.test_engine_qa_run_100_findings", "tests.test_engine_qa_v6_findings", "tests.test_engine_qa_rpc", "tests.test_engine_qa_rpc_entry", "tests.test_engine_qa_rpc_policy", "tests.test_engine_qa_valid_evidence", "tests.test_setup", "tests.test_publish"]


def test_ids() -> list[str]:
    loader = unittest.TestLoader()
    result: list[str] = []
    for module_name in MODULES:
        suite = loader.loadTestsFromName(module_name)
        stack = [suite]
        while stack:
            node = stack.pop()
            if isinstance(node, unittest.TestSuite):
                stack.extend(reversed(list(node)))
            else:
                result.append(node.id())
    return result


def utf8_test_env() -> dict[str, str]:
    """Keep nested Python/CLI subprocesses deterministic across Windows and Linux."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _gha_escape(value: str) -> str:
    """Escape GitHub Actions workflow-command payloads without changing local output."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _annotate_failure(test_id: str, detail: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    compact = detail.strip()[-5000:] or "test process exited non-zero without output"
    print(
        f"::error title=Release test failed: {_gha_escape(test_id)}::{_gha_escape(compact)}",
        flush=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1, help="1-based first test")
    ap.add_argument("--end", type=int, help="1-based last test, inclusive")
    args = ap.parse_args()
    all_ids = test_ids()
    start = max(1, args.start)
    end = min(len(all_ids), args.end or len(all_ids))
    selected = all_ids[start - 1:end]
    failed: list[str] = []
    skipped: list[str] = []
    test_env = utf8_test_env()
    for absolute_idx, test_id in enumerate(selected, start):
        print(f"[{absolute_idx}/{len(all_ids)}] {test_id}", flush=True)
        try:
            cp = subprocess.run(
                [sys.executable, "-m", "unittest", test_id, "-q"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="strict",
                env=test_env,
                timeout=45,
            )
        except subprocess.TimeoutExpired as exc:
            print("  TIMEOUT", flush=True)
            _annotate_failure(test_id, f"Timed out after {exc.timeout} seconds")
            failed.append(test_id)
            continue
        if cp.returncode != 0:
            print(cp.stdout, end="")
            print(cp.stderr, end="")
            _annotate_failure(test_id, (cp.stdout or "") + (cp.stderr or ""))
            failed.append(test_id)
        else:
            combined = (cp.stdout or "") + (cp.stderr or "")
            if "skipped=1" in combined:
                print("  SKIP", flush=True)
                skipped.append(test_id)
            else:
                print("  OK", flush=True)
    passed = len(selected) - len(failed) - len(skipped)
    print(f"\nPassed in batch: {passed}/{len(selected)}")
    if skipped:
        print(f"Skipped: {len(skipped)}")
        for item in skipped:
            print(f"  - {item}")
    if failed:
        print("Failed:")
        for item in failed:
            print(f"  - {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
