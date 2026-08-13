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

    def hypothesis(
        self,
        env: dict[str, str],
        qa_root: Path,
        mode: str = "engine",
        *,
        invariant: str | None = None,
        category: str | None = None,
        text: str | None = None,
        replaces_attempt: int | None = None,
        replacement_kind: str | None = None,
    ) -> dict:
        request = {
            "version": 2,
            "command": "hypothesis",
            "qa_run": "latest",
            "invariant": invariant or f"evidence-{mode}",
            "category": category or f"evidence-{mode}",
            "text": text or f"exercise {mode} evidence",
            "evidence_mode": mode,
        }
        if replaces_attempt is not None:
            request["replaces_attempt"] = replaces_attempt
        if replacement_kind is not None:
            request["replacement_kind"] = replacement_kind
        cp, payload = self.invoke(env, qa_root, request)
        self.assertEqual(cp.returncode, 0, payload)
        if payload.get("ok"):
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

            self.assertTrue(self.hypothesis(env, qa_root, "engine")["ok"])
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
            invalid_attempt = int(invalid["attempt"])
            self.assertEqual(invalid["replacement_required"]["attempt"], invalid_attempt)

            guard_hyp = self.hypothesis(
                env,
                qa_root,
                "guard",
                invariant="guard-after-invalid",
                category="guard-after-invalid",
                text="distinct guard probe replaces invalid engine attempt",
                replaces_attempt=invalid_attempt,
                replacement_kind="distinct",
            )
            self.assertTrue(guard_hyp["ok"], guard_hyp)
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

            self.assertTrue(self.hypothesis(env, qa_root, "state")["ok"])
            cp, state_check = self.invoke(env, qa_root, {"version": 2, "command": "check", "qa_run": "latest"})
            self.assertEqual(cp.returncode, 0, state_check)
            self.assertTrue(state_check["ok"], state_check)
            state_done = self.complete(env, qa_root, "valid")
            self.assertTrue(state_done["ok"], state_done)
            self.assertEqual(state_done["valid_experiments"], 2)

            self.assertTrue(self.hypothesis(env, qa_root, "engine", invariant="engine-final", category="engine-final")["ok"])
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
            self.assertTrue(finished["journal_complete"])
            self.assertEqual(finished["invalid_rows"][0]["attempt"], invalid_attempt)

    def test_duplicate_evidence_on_same_state_is_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root, _sandbox_root = self.make_env(td)
            self.start(env, qa_root, budget=2)

            self.assertTrue(self.hypothesis(env, qa_root, "engine", invariant="first", category="first")["ok"])
            cp, first = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "exec", "qa_run": "latest", "script": "academic_context.py", "args": ["show", "--course", "@course"], "expect_code": 0},
            )
            self.assertEqual(cp.returncode, 0, first)
            self.assertTrue(first["ok"], first)
            self.assertTrue(self.complete(env, qa_root, "valid")["ok"])

            self.assertTrue(self.hypothesis(env, qa_root, "engine", invariant="duplicate", category="duplicate")["ok"])
            cp, duplicate = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "exec", "qa_run": "latest", "script": "academic_context.py", "args": ["show", "--course", "@course"], "expect_code": 0},
            )
            self.assertEqual(cp.returncode, 0, duplicate)
            self.assertTrue(duplicate["ok"], duplicate)
            rejected = self.complete(env, qa_root, "valid")
            self.assertFalse(rejected["ok"], rejected)
            self.assertIn("identical mechanical evidence", rejected["error"])
            invalid = self.complete(env, qa_root, "invalid", "duplicate evidence rejected")
            self.assertTrue(invalid["ok"], invalid)
            attempt = int(invalid["attempt"])

            unlinked = self.hypothesis(env, qa_root, "engine", invariant="unlinked", category="unlinked")
            self.assertFalse(unlinked["ok"], unlinked)
            self.assertIn("replaces_attempt", unlinked["error"])

            replacement = self.hypothesis(
                env,
                qa_root,
                "engine",
                invariant="replacement",
                category="replacement",
                text="different validation replaces duplicate evidence",
                replaces_attempt=attempt,
                replacement_kind="distinct",
            )
            self.assertTrue(replacement["ok"], replacement)
            cp, validate = self.invoke(
                env,
                qa_root,
                {"version": 2, "command": "exec", "qa_run": "latest", "script": "academic_context.py", "args": ["validate", "--course", "@course"], "expect_code": 0},
            )
            self.assertEqual(cp.returncode, 0, validate)
            self.assertTrue(validate["ok"], validate)
            done = self.complete(env, qa_root, "valid")
            self.assertTrue(done["ok"], done)
            self.assertEqual(done["valid_experiments"], 2)
            self.assertEqual(done["attempted_experiments"], 3)
            self.assertEqual(done["invalid_experiments"], 1)


if __name__ == "__main__":
    unittest.main()
