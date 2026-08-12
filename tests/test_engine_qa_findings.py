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

sys.path.insert(0, str(ROOT))
from scripts.academic_context import validate_data  # noqa: E402
from scripts.course_layout import sync_units  # noqa: E402
from scripts.figure_assets import registry_issues  # noqa: E402


def run_safe(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EngineQaFindingRegressions(unittest.TestCase):
    def test_scope_rows_require_canonical_kind(self):
        base = {
            "units": [{"id": "unidad-1", "name": "Unidad 1", "topics": ["Algoritmos"]}],
            "assessments": [
                {
                    "id": "parcial-1",
                    "type": "parcial",
                    "name": "Parcial 1",
                    "scope": [
                        {
                            "kind": "unit",
                            "ref": "unidad-1",
                            "status": "confirmed",
                            "evidence": ["qa:programa"],
                        }
                    ],
                }
            ],
            "rules": [],
        }
        valid = validate_data(base)
        self.assertTrue(valid["valid"], valid)

        malformed = json.loads(json.dumps(base))
        row = malformed["assessments"][0]["scope"][0]
        row["type"] = row.pop("kind")
        result = validate_data(malformed)
        self.assertFalse(result["valid"])
        messages = [issue["message"] for issue in result["issues"]]
        self.assertIn("invalid scope kind: <missing>", messages)

    def test_safe_wrapper_uses_canonical_fixture_and_utf8_under_cp1252(self):
        with tempfile.TemporaryDirectory() as td:
            qa_root = Path(td) / "qa-state"
            sandbox_root = Path(td) / "sandboxes"
            env = os.environ.copy()
            env["PYTHONUTF8"] = "0"
            env["PYTHONIOENCODING"] = "cp1252"
            env["STUDY_ENGINE_QA_ROOT"] = str(qa_root)
            env["STUDY_ENGINE_QA_SANDBOX_ROOT"] = str(sandbox_root)

            started = run_safe(env, "start", "--budget", "2", "--seed", "31", "--provider", "test")
            self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
            start_data = json.loads(started.stdout)
            course = Path(start_data["course"])
            academic = json.loads((course / "academico" / "academic.json").read_text(encoding="utf-8"))
            scope = academic["assessments"][0]["scope"]
            self.assertTrue(scope)
            self.assertTrue(all(row.get("kind") == "unit" for row in scope), scope)
            self.assertTrue(all("type" not in row for row in scope), scope)

            moved = run_safe(
                env,
                "mutate",
                "--op",
                "move",
                "--path",
                "unidades/unidad-3/fuentes/oficiales/funciones.txt",
                "--dest",
                "unidades/unidad-3/fuentes/oficiales/funciones-漢.txt",
            )
            self.assertEqual(moved.returncode, 0, moved.stdout + moved.stderr)
            self.assertTrue(json.loads(moved.stdout)["ok"])

            scanned = run_safe(
                env,
                "exec",
                "--script",
                "sync_materials.py",
                "--",
                "--course",
                "@course",
                "--unit",
                "unidad-3",
            )
            self.assertEqual(scanned.returncode, 0, scanned.stdout + scanned.stderr)
            payload = json.loads(scanned.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertIn("funciones-漢.txt", payload["stdout"])

    def test_derived_asset_hash_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td) / "qa-figure-integrity"
            (course / "academico").mkdir(parents=True)
            academic = {
                "version": 1,
                "identity": {"subject": "QA Figure Integrity"},
                "units": [{"id": "unidad-1", "name": "Unidad 1", "topics": ["Algoritmos"]}],
                "assessments": [],
                "rules": [],
                "claims": [],
                "claim_candidates": [],
                "official_status": {},
            }
            (course / "academico" / "academic.json").write_text(
                json.dumps(academic, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (course / "fuentes").mkdir(parents=True)
            (course / "contexto.md").write_text("# QA\n", encoding="utf-8")
            sync_units(course)

            asset = course / "unidades" / "unidad-1" / "assets" / "figures" / "qa.svg"
            asset.write_text("<svg><text>original</text></svg>\n", encoding="utf-8")
            data = {
                "version": 2,
                "figures": {
                    "derived:qa": {
                        "id": "derived:qa",
                        "unit_id": "unidad-1",
                        "origin": "derived",
                        "based_on": ["concept:algoritmo"],
                        "asset": "assets/figures/qa.svg",
                        "asset_sha256": sha256(asset),
                    }
                },
            }
            self.assertEqual(registry_issues(course, data), [])

            asset.write_text("<svg><text>mutated</text></svg>\n", encoding="utf-8")
            issues = registry_issues(course, data)
            self.assertIn("asset-changed", [issue.get("reason") for issue in issues])


if __name__ == "__main__":
    unittest.main()
