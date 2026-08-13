from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(script: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        check=check,
        timeout=30,
    )


class EngineQaRun100FindingRegressions(unittest.TestCase):
    def make_tracker_course(self, td: str) -> Path:
        course = Path(td) / "course"
        for sub in ["fuentes", "conocimiento", "progreso", "academico"]:
            (course / sub).mkdir(parents=True, exist_ok=True)
        (course / "conocimiento" / "concepts.json").write_text(
            '{"version":2,"concepts":{}}\n', encoding="utf-8"
        )
        (course / "progreso" / "progress.json").write_text(
            '{"version":2,"concepts":{}}\n', encoding="utf-8"
        )
        academic = {
            "version": 1,
            "identity": {},
            "units": [
                {"id": "U1", "name": "Unidad 1", "topics": ["Algoritmos"]},
                {"id": "U2", "name": "Unidad 2", "topics": ["Condicionales"]},
                {"id": "U3", "name": "Unidad 3", "topics": ["Funciones"]},
            ],
            "assessments": [
                {
                    "id": "parcial-1",
                    "type": "parcial",
                    "name": "Parcial 1",
                    "status": "scheduled",
                    "scope": [
                        {"kind": "unit", "ref": "U1", "status": "confirmed", "evidence": "programa"},
                        {"kind": "unit", "ref": "U2", "status": "likely", "evidence": "clase"},
                    ],
                }
            ],
            "rules": [],
            "official_status": {},
        }
        (course / "academico" / "academic.json").write_text(
            json.dumps(academic, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return course

    def test_registered_assessment_due_excludes_out_of_scope_concepts_by_id_and_name(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_tracker_course(td)
            for name, unit in (("Algoritmo", "U1"), ("Condicional", "U2"), ("Funcion", "U3")):
                run("concept_graph.py", "upsert", "--course", str(course), "--concept", name, "--unit", unit)
                run("study_tracker.py", "add", "--course", str(course), "--concept", name, "--unit", unit)

            # Reproduce the finding's stronger case: the concept has explicit
            # assessment evidence saying it is excluded, and is generally due.
            run(
                "concept_graph.py",
                "relevance",
                "--course",
                str(course),
                "--concept",
                "Funcion",
                "--assessment",
                "parcial-1",
                "--status",
                "excluded",
                "--evidence",
                "temario",
            )

            for assessment in ("parcial-1", "Parcial 1"):
                cp = run(
                    "study_tracker.py",
                    "due",
                    "--course",
                    str(course),
                    "--on",
                    "2030-01-01",
                    "--assessment",
                    assessment,
                    "--include-not-due",
                )
                rows = json.loads(cp.stdout)
                names = {row["name"] for row in rows}
                self.assertEqual(names, {"Algoritmo", "Condicional"}, rows)
                relevance = {row["name"]: row["assessment_relevance"] for row in rows}
                self.assertEqual(relevance["Algoritmo"], "confirmed")
                self.assertEqual(relevance["Condicional"], "likely")
                self.assertNotIn("Funcion", names)

    def test_unchanged_figure_scan_write_preserves_registry_bytes(self):
        try:
            import pymupdf
        except Exception as exc:  # pragma: no cover - optional visual dependency
            self.skipTest(f"PyMuPDF unavailable: {exc}")

        with tempfile.TemporaryDirectory() as td:
            course = Path(td) / "course"
            source_dir = course / "fuentes" / "oficiales"
            source_dir.mkdir(parents=True)
            pdf = source_dir / "apunte.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 72), "ENGINE QA figure scan idempotence")
            doc.save(pdf)
            doc.close()

            first = run("figure_assets.py", "scan", "--course", str(course), "--write")
            payload1 = json.loads(first.stdout)
            registry = course / ".study" / "figure-pages.json"
            self.assertTrue(registry.is_file())
            bytes1 = registry.read_bytes()

            second = run("figure_assets.py", "scan", "--course", str(course), "--write")
            payload2 = json.loads(second.stdout)
            bytes2 = registry.read_bytes()

            self.assertEqual(bytes2, bytes1)
            self.assertEqual(payload2, payload1)
            self.assertEqual(payload2["files"][0]["sha256"], payload1["files"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
