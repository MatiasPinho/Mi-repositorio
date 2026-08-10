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


class CompleteSetupTests(unittest.TestCase):
    def test_root_requirements_aggregates_all_capability_groups(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("-r requirements-mcp.txt", req)
        self.assertIn("-r requirements-visual.txt", req)
        self.assertIn("-r requirements-design.txt", req)

    def test_windows_installer_and_launcher_share_environment_preflight(self):
        installer = (ROOT / "INSTALAR-STUDY.bat").read_text(encoding="utf-8")
        launcher = (ROOT / "INICIAR-STUDY.bat").read_text(encoding="utf-8")
        self.assertIn("pip install -r requirements.txt", installer)
        self.assertIn("playwright install chromium", installer)
        self.assertIn("scripts\\setup_env.py check", installer)
        self.assertIn("scripts\\setup_env.py check", launcher)
        self.assertIn("INSTALAR-STUDY.bat", launcher)

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
        for name in ("python", "mcp", "pymupdf", "pillow", "playwright", "chromium"):
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
                [sys.executable, str(AUDIT), str(html), "--out", str(out)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=40,
            )
            self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
            report = json.loads(audit.stdout)
            self.assertTrue(report["ok"])
            self.assertEqual(report["engine"], "chromium-set-content")
            for name in ("desktop", "tablet", "mobile", "print"):
                self.assertTrue((out / f"{name}.png").is_file(), name)


if __name__ == "__main__":
    unittest.main()
