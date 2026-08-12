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
RPC_ARG = "scripts/engine_qa_rpc.py"


class EngineQaRpcTests(unittest.TestCase):
    def make_env(self, td: str) -> tuple[dict[str, str], Path, Path]:
        qa_root = Path(td) / "qa-state"
        sandbox_root = Path(td) / "sandboxes"
        env = os.environ.copy()
        # Deliberately hostile console defaults: request/response files must keep
        # the transport independent from PowerShell/codepage behavior.
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
        index = len(list(requests.glob("*.json"))) + len(list(responses.glob("*.json"))) + 1
        req = requests / f"req-{index:03d}.json"
        res = responses / f"res-{index:03d}.json"
        req.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cp = subprocess.run(
            [
                sys.executable,
                str(VENV_EXEC),
                RPC_ARG,
                "--request-file",
                str(req),
                "--response-file",
                str(res),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=45,
        )
        self.assertTrue(res.is_file(), f"RPC response missing; exit={cp.returncode} stdout={cp.stdout!r} stderr={cp.stderr!r}")
        payload = json.loads(res.read_text(encoding="utf-8"))
        return cp, payload

    def start(self, env: dict[str, str], qa_root: Path, budget: int) -> dict:
        cp, payload = self.invoke(
            env,
            qa_root,
            {
                "version": 2,
                "command": "start",
                "budget": budget,
                "seed": 26081299,
                "provider": "test provider with space",
            },
        )
        self.assertEqual(cp.returncode, 0, payload)
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(payload["transport_ok"], payload)
        return payload

    def hypothesis(self, env: dict[str, str], qa_root: Path, invariant: str, category: str) -> dict:
        cp, payload = self.invoke(
            env,
            qa_root,
            {
                "version": 2,
                "command": "hypothesis",
                "qa_run": "latest",
                "invariant": invariant,
                "category": category,
                "text": f"probe {invariant}",
            },
        )
        self.assertEqual(cp.returncode, 0, payload)
        self.assertTrue(payload["ok"], payload)
        return payload

    def complete(self, env: dict[str, str], qa_root: Path, status: str, reason: str = "") -> dict:
        request = {
            "version": 2,
            "command": "experiment-result",
            "qa_run": "latest",
            "status": status,
        }
        if reason:
            request["reason"] = reason
        cp, payload = self.invoke(env, qa_root, request)
        self.assertEqual(cp.returncode, 0, payload)
        self.assertTrue(payload["ok"], payload)
        return payload

    def test_rpc_preserves_spaces_unicode_json_and_inner_run_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root, _sandbox_root = self.make_env(td)
            self.start(env, qa_root, budget=3)

            self.hypothesis(env, qa_root, "assessment-name-token", "transport-spaces")
            cp, scoped = self.invoke(
                env,
                qa_root,
                {
                    "version": 2,
                    "command": "exec",
                    "qa_run": "latest",
                    "script": "academic_context.py",
                    "args": ["scope", "--course", "@course", "--assessment", "Parcial 1"],
                    "expect_code": 0,
                },
            )
            self.assertEqual(cp.returncode, 0, scoped)
            self.assertTrue(scoped["transport_ok"], scoped)
            self.assertTrue(scoped["engine_invoked"], scoped)
            self.assertTrue(scoped["ok"], scoped)
            self.assertEqual(scoped["request_args"][-1], "Parcial 1")
            academic_output = json.loads(scoped["stdout"])
            self.assertEqual(academic_output["assessment"]["name"], "Parcial 1")
            self.complete(env, qa_root, "valid")

            self.hypothesis(env, qa_root, "json-token", "transport-json-unicode")
            json_token = '{"name":"Parcial 1","unicode":"漢","nested":{"quote":"a b"}}'
            cp, quoted = self.invoke(
                env,
                qa_root,
                {
                    "version": 2,
                    "command": "exec",
                    "qa_run": "latest",
                    "script": "academic_context.py",
                    "args": ["show", "--course", "@course", "--probe", json_token],
                    "expect_code": 2,
                },
            )
            self.assertEqual(cp.returncode, 0, quoted)
            self.assertTrue(quoted["engine_invoked"], quoted)
            self.assertTrue(quoted["ok"], quoted)
            self.assertEqual(quoted["request_args"][-1], json_token)
            self.assertEqual(quoted["expanded_args"][-1], json_token)
            self.complete(env, qa_root, "valid")

            self.hypothesis(env, qa_root, "inner-run-token", "transport-inner-run")
            inner_run = "pipeline run con espacio 漢"
            cp, run_probe = self.invoke(
                env,
                qa_root,
                {
                    "version": 2,
                    "command": "exec",
                    "qa_run": "latest",
                    "script": "pipeline_run.py",
                    "args": ["status", "--run", inner_run],
                    "expect_code": 1,
                },
            )
            self.assertEqual(cp.returncode, 0, run_probe)
            self.assertTrue(run_probe["engine_invoked"], run_probe)
            self.assertTrue(run_probe["ok"], run_probe)
            self.assertEqual(run_probe["request_args"], ["status", "--run", inner_run])
            self.assertEqual(run_probe["expanded_args"], ["status", "--run", inner_run])
            self.complete(env, qa_root, "valid")

            _cp, info = self.invoke(env, qa_root, {"version": 2, "command": "info", "qa_run": "latest"})
            self.assertEqual(info["valid_experiments"], 3)
            self.assertEqual(info["attempted_experiments"], 3)
            self.assertEqual(info["invalid_experiments"], 0)
            self.assertIsNone(info["pending_experiment"])

            cp, finished = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "finish", "qa_run": "latest", "export": False},
            )
            self.assertEqual(cp.returncode, 0, finished)
            self.assertTrue(finished["ok"], finished)
            self.assertEqual(finished["valid_experiments"], 3)
            self.assertEqual(finished["attempted_experiments"], 3)
            self.assertEqual(finished["invalid_experiments"], 0)

    def test_invalid_attempt_does_not_consume_budget(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root, _sandbox_root = self.make_env(td)
            self.start(env, qa_root, budget=2)

            self.hypothesis(env, qa_root, "transport-rejection", "harness-invalid")
            live_study = ROOT / "study.py"
            cp, rejected = self.invoke(
                env,
                qa_root,
                {
                    "version": 2,
                    "command": "exec",
                    "qa_run": "latest",
                    "script": "render_study.py",
                    "args": [f"--out={live_study.resolve()}"],
                    "expect_code": 0,
                },
            )
            self.assertEqual(cp.returncode, 0, rejected)
            self.assertTrue(rejected["transport_ok"], rejected)
            self.assertFalse(rejected["engine_invoked"], rejected)
            self.assertFalse(rejected["ok"], rejected)
            invalid = self.complete(env, qa_root, "invalid", "guard rejected invocation before intended engine test")
            self.assertEqual(invalid["valid_experiments"], 0)
            self.assertEqual(invalid["invalid_experiments"], 1)
            self.assertEqual(invalid["remaining_valid"], 2)

            for idx in (1, 2):
                self.hypothesis(env, qa_root, f"valid-{idx}", "valid-engine-probe")
                cp, probe = self.invoke(
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
                self.assertEqual(cp.returncode, 0, probe)
                self.assertTrue(probe["engine_invoked"], probe)
                self.assertTrue(probe["ok"], probe)
                self.complete(env, qa_root, "valid")

            _cp, info = self.invoke(env, qa_root, {"version": 2, "command": "info", "qa_run": "latest"})
            self.assertEqual(info["valid_experiments"], 2)
            self.assertEqual(info["attempted_experiments"], 3)
            self.assertEqual(info["invalid_experiments"], 1)

            cp, finished = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "finish", "qa_run": "latest", "export": False},
            )
            self.assertEqual(cp.returncode, 0, finished)
            self.assertTrue(finished["ok"], finished)
            self.assertEqual(finished["valid_experiments"], 2)
            self.assertEqual(finished["attempted_experiments"], 3)
            self.assertEqual(finished["invalid_experiments"], 1)
            report = json.loads(Path(finished["report"]).read_text(encoding="utf-8")) if str(finished["report"]).endswith(".json") else None
            # report points to Markdown in the legacy harness; the canonical JSON
            # lives alongside it and must expose the same V2 counters.
            report_json = json.loads((Path(finished["report"]).parent / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report_json["valid_experiments"], 2)
            self.assertEqual(report_json["attempted_experiments"], 3)
            self.assertEqual(report_json["invalid_experiments"], 1)

    def test_rpc_request_and_response_files_must_stay_under_qa_root(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root, _sandbox_root = self.make_env(td)
            outside = Path(td) / "outside.json"
            outside.write_text('{"version":2,"command":"history"}\n', encoding="utf-8")
            response = qa_root / "responses" / "result.json"
            response.parent.mkdir(parents=True, exist_ok=True)
            cp = subprocess.run(
                [
                    sys.executable,
                    str(VENV_EXEC),
                    RPC_ARG,
                    "--request-file",
                    str(outside),
                    "--response-file",
                    str(response),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=30,
            )
            self.assertEqual(cp.returncode, 2)
            self.assertTrue(response.is_file())
            payload = json.loads(response.read_text(encoding="utf-8"))
            self.assertFalse(payload["transport_ok"])
            self.assertIn("Protocol file must stay under", payload["error"])


if __name__ == "__main__":
    unittest.main()
