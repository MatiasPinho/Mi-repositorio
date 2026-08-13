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


class EngineQaRpcPolicyTests(unittest.TestCase):
    def make_env(self, td: str) -> tuple[dict[str, str], Path, Path]:
        qa_root = Path(td) / "qa-state"
        sandbox_root = Path(td) / "sandboxes"
        env = os.environ.copy()
        env["PYTHONUTF8"] = "0"
        env["PYTHONIOENCODING"] = "cp1252"
        env["STUDY_ENGINE_QA_ROOT"] = str(qa_root)
        env["STUDY_ENGINE_QA_SANDBOX_ROOT"] = str(sandbox_root)
        return env, qa_root, sandbox_root

    def invoke(self, env: dict[str, str], qa_root: Path, request: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
        requests = qa_root / "requests"
        responses = qa_root / "responses"
        requests.mkdir(parents=True, exist_ok=True)
        responses.mkdir(parents=True, exist_ok=True)
        idx = len(list(requests.glob("*.json"))) + len(list(responses.glob("*.json"))) + 1
        req = requests / f"req-{idx:03d}.json"
        res = responses / f"res-{idx:03d}.json"
        req.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cp = subprocess.run(
            [sys.executable, str(VENV_EXEC), ENTRY_ARG, "--request-file", str(req), "--response-file", str(res)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=45,
        )
        self.assertTrue(res.is_file(), cp.stdout + cp.stderr)
        return cp, json.loads(res.read_text(encoding="utf-8"))

    def start(self, env: dict[str, str], qa_root: Path, budget: int = 3) -> dict:
        cp, payload = self.invoke(
            env,
            qa_root,
            {"version": 2, "command": "start", "budget": budget, "seed": 26081301, "provider": "policy-test"},
        )
        self.assertEqual(cp.returncode, 0, payload)
        self.assertTrue(payload["ok"], payload)
        return payload

    def hypothesis(self, env: dict[str, str], qa_root: Path, mode: str = "engine") -> dict:
        cp, payload = self.invoke(
            env,
            qa_root,
            {
                "version": 2,
                "command": "hypothesis",
                "qa_run": "latest",
                "invariant": f"evidence-{mode}",
                "category": f"evidence-{mode}",
                "text": f"exercise {mode} evidence",
                "evidence_mode": mode,
            },
        )
        self.assertEqual(cp.returncode, 0, payload)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["evidence_mode"], mode)
        return payload

    def complete(self, env: dict[str, str], qa_root: Path, status: str, reason: str = "") -> dict:
        request = {"version": 2, "command": "experiment-result", "qa_run": "latest", "status": status}
        if reason:
            request["reason"] = reason
        cp, payload = self.invoke(env, qa_root, request)
        self.assertEqual(cp.returncode, 0, payload)
        return payload

    def test_invalid_response_path_is_rejected_before_start_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root, sandbox_root = self.make_env(td)
            requests = qa_root / "requests"
            requests.mkdir(parents=True, exist_ok=True)
            req = requests / "start.json"
            req.write_text(
                json.dumps({"version": 2, "command": "start", "budget": 1, "seed": 9, "provider": "test"}),
                encoding="utf-8",
            )
            outside = Path(td) / "outside-response.json"
            cp = subprocess.run(
                [sys.executable, str(VENV_EXEC), ENTRY_ARG, "--request-file", str(req), "--response-file", str(outside)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
            self.assertFalse(outside.exists())
            self.assertFalse((qa_root / "latest.json").exists(), "start must not dispatch when response path is invalid")
            self.assertFalse(sandbox_root.exists(), "sandbox must not be created before response path validation")

    def test_valid_requires_evidence_matching_declared_mode(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root, _sandbox_root = self.make_env(td)
            self.start(env, qa_root, budget=3)

            # ENGINE: a generic check is real work, but it is not evidence that an
            # intended engine invocation reached the engine.
            self.hypothesis(env, qa_root, "engine")
            cp, checked = self.invoke(env, qa_root, {"version": 2, "command": "check", "qa_run": "latest"})
            self.assertEqual(cp.returncode, 0, checked)
            rejected_valid = self.complete(env, qa_root, "valid")
            self.assertFalse(rejected_valid["ok"], rejected_valid)
            self.assertTrue(rejected_valid["transport_ok"], rejected_valid)
            self.assertIn("evidence_mode=engine", rejected_valid["error"])
            invalid = self.complete(env, qa_root, "invalid", "intended engine invocation never happened")
            self.assertTrue(invalid["ok"], invalid)
            self.assertEqual(invalid["valid_experiments"], 0)
            self.assertEqual(invalid["invalid_experiments"], 1)

            # GUARD: a pre-engine rejection is exactly the expected evidence.
            self.hypothesis(env, qa_root, "guard")
            cp, guard = self.invoke(
                env,
                qa_root,
                {
                    "version": 2,
                    "command": "exec",
                    "qa_run": "latest",
                    "script": "render_study.py",
                    "args": [f"--out={(ROOT / 'study.py').resolve()}"],
                    "expect_code": 0,
                },
            )
            self.assertEqual(cp.returncode, 0, guard)
            self.assertFalse(guard["engine_invoked"], guard)
            self.assertTrue(guard["rejected"], guard)
            guard_done = self.complete(env, qa_root, "valid")
            self.assertTrue(guard_done["ok"], guard_done)
            self.assertEqual(guard_done["valid_experiments"], 1)

            # STATE: invariant/checker experiments can be valid without spawning a
            # target engine script, but they must produce state/check evidence.
            self.hypothesis(env, qa_root, "state")
            cp, state_check = self.invoke(env, qa_root, {"version": 2, "command": "check", "qa_run": "latest"})
            self.assertEqual(cp.returncode, 0, state_check)
            self.assertTrue(state_check["ok"], state_check)
            state_done = self.complete(env, qa_root, "valid")
            self.assertTrue(state_done["ok"], state_done)
            self.assertEqual(state_done["valid_experiments"], 2)

            # ENGINE: actual invocation satisfies the default/declared contract.
            self.hypothesis(env, qa_root, "engine")
            cp, engine = self.invoke(
                env,
                qa_root,
                {
                    "version": 2,
                    "command": "exec",
                    "qa_run": "latest",
                    "script": "academic_context.py",
                    "args": ["show", "--course", "@course"],
                    "expect_code": 0,
                },
            )
            self.assertEqual(cp.returncode, 0, engine)
            self.assertTrue(engine["engine_invoked"], engine)
            engine_done = self.complete(env, qa_root, "valid")
            self.assertTrue(engine_done["ok"], engine_done)
            self.assertEqual(engine_done["valid_experiments"], 3)
            self.assertEqual(engine_done["attempted_experiments"], 4)
            self.assertEqual(engine_done["invalid_experiments"], 1)

            cp, finished = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "finish", "qa_run": "latest", "export": False},
            )
            self.assertEqual(cp.returncode, 0, finished)
            self.assertTrue(finished["ok"], finished)
            self.assertEqual(finished["valid_experiments"], 3)
            self.assertEqual(finished["attempted_experiments"], 4)
            self.assertEqual(finished["invalid_experiments"], 1)


if __name__ == "__main__":
    unittest.main()
