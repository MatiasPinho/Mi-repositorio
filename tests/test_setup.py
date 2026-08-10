from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "setup_env.py"
RENDER = ROOT / "scripts" / "render_study.py"
AUDIT = ROOT / "scripts" / "visual_audit.py"
VENV_EXEC = ROOT / "scripts" / "venv_exec.py"


class CompleteSetupTests(unittest.TestCase):
    def test_root_requirements_aggregates_all_capability_groups(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("-r requirements-mcp.txt", req)
        self.assertIn("-r requirements-visual.txt", req)
        self.assertIn("-r requirements-design.txt", req)

    def test_windows_installer_uses_isolated_project_venv(self):
        installer = (ROOT / "INSTALAR-STUDY.bat").read_text(encoding="utf-8")
        launcher = (ROOT / "INICIAR-STUDY.bat").read_text(encoding="utf-8")
        self.assertIn("-m venv .venv", installer)
        self.assertIn(".venv\\Scripts\\python.exe", installer)
        self.assertIn('"%VENV_PYTHON%" -m pip install -r requirements.txt', installer)
        self.assertIn('"%VENV_PYTHON%" -m playwright install chromium', installer)
        self.assertIn('"%VENV_PYTHON%" -m pip check', installer)
        self.assertIn('"%VENV_PYTHON%" scripts\\setup_env.py check', installer)
        self.assertIn(".venv\\Scripts\\python.exe", launcher)
        self.assertIn('"%VENV_PYTHON%" scripts\\setup_env.py check', launcher)
        self.assertIn('"%VENV_PYTHON%" study.py', launcher)
        self.assertIn("INSTALAR-STUDY.bat", launcher)

    def test_agent_mcp_configs_route_through_project_venv_shim(self):
        self.assertTrue(VENV_EXEC.is_file())
        mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        args = mcp["mcpServers"]["university-study"]["args"]
        self.assertEqual(args[:2], ["scripts/venv_exec.py", "study.py"])
        codex = (ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('args = ["scripts/venv_exec.py", "study.py", "mcp", "serve"]', codex)

    def test_complete_environment_preflight_is_ready(self):
        cp = subprocess.run(
            [sys.executable, str(SETUP), "check", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=25,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        payload = json.loads(cp.stdout)
        self.assertTrue(payload["ready"])
        self.assertTrue(payload["visual_audit"]["ready"])
        for name in ("python", "venv", "mcp", "pymupdf", "pillow", "playwright", "chromium"):
            self.assertTrue(payload["checks"][name]["ready"], name)

    def test_visual_audit_launches_browser_on_rendered_html(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            md = td / "smoke.md"
            html = td / "smoke.html"
            out = td / "audit"
            md.write_text(
                "# Unidad de prueba\n\nTexto suficiente para comprobar el renderer.\n\n"
                "> [!RECALL] Comprobación\n> Explicá la idea principal.\n",
                encoding="utf-8",
            )
            render = subprocess.run(
                [
                    sys.executable,
                    str(RENDER),
                    str(md),
                    str(html),
                    "--kind",
                    "summary",
                    "--course",
                    "Smoke Test",
                    "--scope",
                    "Unidad 1",
                    "--check",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)

            audit = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT),
                    str(html),
                    "--out",
                    str(out),
                    "--viewports",
                    "desktop,mobile",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=35,
            )
            self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
            report_path = out / "audit.json"
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["ok"])
            self.assertEqual(report["engine"], "chromium-set-content")
            self.assertEqual(report["selected_viewports"], ["desktop", "mobile"])
            for name in ("desktop", "mobile"):
                self.assertTrue((out / f"{name}.png").is_file(), name)


if __name__ == "__main__":
    unittest.main()
