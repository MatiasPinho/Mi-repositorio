from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_EXEC = ROOT / "scripts" / "venv_exec.py"
SAFE_ARG = "scripts/engine_qa_safe.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_safe(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the exact command shape documented for Claude/Codex."""
    return subprocess.run(
        [sys.executable, str(VENV_EXEC), SAFE_ARG, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        env=env,
        timeout=30,
    )


class EngineQaSafetyTests(unittest.TestCase):
    def make_env(self, td: str) -> tuple[dict[str, str], Path, Path]:
        qa_root = Path(td) / "qa-state"
        sandbox_root = Path(td) / "sandboxes"
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["STUDY_ENGINE_QA_ROOT"] = str(qa_root)
        env["STUDY_ENGINE_QA_SANDBOX_ROOT"] = str(sandbox_root)
        return env, qa_root, sandbox_root

    def start(self, env: dict[str, str]) -> dict:
        cp = run_safe(env, "start", "--budget", "2", "--seed", "17", "--provider", "test")
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertTrue(cp.stdout.strip(), f"safe start produced no stdout; stderr={cp.stderr!r}")
        try:
            value = json.loads(cp.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                "safe start stdout was not JSON: "
                f"len={len(cp.stdout)} prefix={cp.stdout[:160]!r} stderr={cp.stderr[:300]!r}; {exc}"
            )
        self.assertIsInstance(value, dict)
        return value

    def test_direct_entrypoint_runs_frozen_engine_outside_live_materias(self):
        with tempfile.TemporaryDirectory() as td:
            env, qa_root, sandbox_root = self.make_env(td)
            data = self.start(env)
            course = Path(data["course"]).resolve()
            run_dir = Path(data["run_dir"]).resolve()
            self.assertTrue(course.name.startswith("qa-engine-"))
            self.assertTrue(course.is_relative_to(sandbox_root.resolve()))
            self.assertFalse(course.is_relative_to((ROOT / "materias").resolve()))
            self.assertTrue((course / "academico" / "academic.json").is_file())
            guard = json.loads((run_dir / "live-guard.json").read_text(encoding="utf-8"))
            sandbox = Path(guard["sandbox_root"]).resolve()
            self.assertTrue(sandbox.is_relative_to(sandbox_root.resolve()))
            self.assertTrue((sandbox / "study.py").is_file())
            self.assertTrue((sandbox / "scripts" / "engine_qa.py").is_file())
            latest = json.loads((qa_root / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(latest["run_dir"]).resolve(), run_dir)

            info = run_safe(env, "info")
            self.assertEqual(info.returncode, 0, info.stdout + info.stderr)
            self.assertEqual(json.loads(info.stdout)["course_path"], str(course))

    def test_exec_rejects_escape_paths_before_live_checkout_can_change(self):
        with tempfile.TemporaryDirectory() as td:
            env, _qa_root, _sandbox_root = self.make_env(td)
            self.start(env)
            live_study = ROOT / "study.py"
            before = sha256(live_study)

            good = run_safe(
                env,
                "exec",
                "--script",
                "transcript_tools.py",
                "--",
                "inspect",
                "--course",
                "@course",
                "--unit",
                "unidad-1",
            )
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            self.assertTrue(json.loads(good.stdout)["engine_unchanged"])

            outside = run_safe(
                env,
                "exec",
                "--script",
                "render_study.py",
                "--",
                f"--out={live_study.resolve()}",
            )
            self.assertNotEqual(outside.returncode, 0)
            self.assertIn("fuera del sandbox QA", outside.stdout)

            traversal = run_safe(
                env,
                "exec",
                "--script",
                "render_study.py",
                "--",
                "--out=../study.py",
            )
            self.assertNotEqual(traversal.returncode, 0)
            self.assertIn("Path traversal", traversal.stdout)
            self.assertEqual(sha256(live_study), before)

    def test_internal_skill_uses_safe_entrypoint_for_commands(self):
        source = (ROOT / "skills-src" / "engine-qa" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("scripts/engine_qa_safe.py start", source)
        self.assertIn("scripts/engine_qa_safe.py finish --export", source)
        self.assertIn("Nunca invoques `scripts/engine_qa.py` directamente", source)
        self.assertIn("worktree temporal", source)


if __name__ == "__main__":
    unittest.main()
