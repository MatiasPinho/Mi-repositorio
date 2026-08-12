from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_EXEC = ROOT / "scripts" / "venv_exec.py"
ENTRY_ARG = "scripts/engine_qa_rpc_entry.py"


class EngineQaRpcEntryTests(unittest.TestCase):
    def make_env(self, td: str) -> tuple[dict[str, str], Path]:
        qa_root = Path(td) / "qa-state"
        env = os.environ.copy()
        env["PYTHONUTF8"] = "0"
        env["PYTHONIOENCODING"] = "cp1252"
        env["STUDY_ENGINE_QA_ROOT"] = str(qa_root)
        env["STUDY_ENGINE_QA_SANDBOX_ROOT"] = str(Path(td) / "sandboxes")
        return env, qa_root

    def invoke(self, env: dict[str, str], qa_root: Path, request: dict, name: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        req = qa_root / "requests" / f"{name}.json"
        res = qa_root / "responses" / f"{name}.json"
        req.parent.mkdir(parents=True, exist_ok=True)
        res.parent.mkdir(parents=True, exist_ok=True)
        req.write_text(json.dumps(request, ensure_ascii=False) + "\n", encoding="utf-8")
        cp = subprocess.run(
            [sys.executable, str(VENV_EXEC), ENTRY_ARG, "--request-file", str(req), "--response-file", str(res)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=45,
        )
        self.assertTrue(res.is_file(), cp.stdout + cp.stderr)
        return cp, json.loads(res.read_text(encoding="utf-8"))

    def test_workflow_rejection_is_not_transport_failure(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root = self.make_env(td)
            cp, started = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "start", "budget": 2, "seed": 77, "provider": "entry test"},
                "start",
            )
            self.assertEqual(cp.returncode, 0, started)
            self.assertTrue(started["transport_ok"])

            # Finishing a fresh 0/2 campaign is a normal workflow rejection.
            cp, rejected = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "finish", "qa_run": "latest", "export": False},
                "finish-too-early",
            )
            self.assertEqual(cp.returncode, 0, rejected)
            self.assertTrue(rejected["transport_ok"], rejected)
            self.assertFalse(rejected["ok"], rejected)
            self.assertIn("Campaign incomplete", rejected["error"])

    def test_invalid_json_is_transport_failure(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root = self.make_env(td)
            req = qa_root / "requests" / "broken.json"
            res = qa_root / "responses" / "broken.json"
            req.parent.mkdir(parents=True, exist_ok=True)
            res.parent.mkdir(parents=True, exist_ok=True)
            req.write_text('{"version":2,"command":', encoding="utf-8")
            cp = subprocess.run(
                [sys.executable, str(VENV_EXEC), ENTRY_ARG, "--request-file", str(req), "--response-file", str(res)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 2)
            payload = json.loads(res.read_text(encoding="utf-8"))
            self.assertFalse(payload["transport_ok"])
            self.assertFalse(payload["engine_invoked"])


if __name__ == "__main__":
    unittest.main()
