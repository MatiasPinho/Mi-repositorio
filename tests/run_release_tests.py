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
MODULES = ["tests.test_actions", "tests.test_pipeline", "tests.test_artifacts", "tests.test_system", "tests.test_cli", "tests.test_unit_layout", "tests.test_visual", "tests.test_infrastructure", "tests.test_mcp", "tests.test_academic_eval", "tests.test_stressed_materials", "tests.test_pdf_stress", "tests.test_semantic_claims", "tests.test_claim_candidates", "tests.test_setup", "tests.test_publish"]


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
        except subprocess.TimeoutExpired:
            print("  TIMEOUT", flush=True)
            failed.append(test_id)
            continue
        if cp.returncode != 0:
            print(cp.stdout, end="")
            print(cp.stderr, end="")
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
