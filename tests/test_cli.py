from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "study.py"
COURSE = ROOT / "materias" / "cli-unittest"


def cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="strict",
        input=input_text,
        capture_output=True,
        check=True,
        timeout=20,
    )


class StudyCliTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(COURSE, ignore_errors=True)

    def tearDown(self) -> None:
        shutil.rmtree(COURSE, ignore_errors=True)

    def test_course_add_list_and_name_resolution(self):
        created = cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        self.assertIn("Materia creada: CLI UnitTest", created.stdout)
        listed = cli("course", "list")
        self.assertIn("CLI UnitTest [cli-unittest]", listed.stdout)
        status = cli("status", "CLI UnitTest")
        self.assertIn("CLI UnitTest", status.stdout)
        self.assertIn("Repasos pendientes: 0", status.stdout)
        by_path = cli("status", "materias/cli-unittest")
        self.assertIn("CLI UnitTest", by_path.stdout)

    def test_material_scan_commit_and_change_detection(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        src = COURSE / "fuentes" / "unidad.txt"
        src.write_text("v1", encoding="utf-8")
        first = cli("materials", "scan", "cli-unittest")
        self.assertIn("Nuevos:      1", first.stdout)
        cli("materials", "scan", "cli-unittest", "--commit")
        src.write_text("v2", encoding="utf-8")
        changed = cli("materials", "scan", "CLI UnitTest", "--json")
        payload = json.loads(changed.stdout)
        self.assertEqual(payload["changed"], ["fuentes/unidad.txt"])
        self.assertNotIn("Materiales -", changed.stdout)


    def test_material_scan_json_is_pure_and_handles_unicode_filenames(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        src = COURSE / "fuentes" / "oficiales" / "Programación — lógica 🧠.txt"
        src.write_text("contenido", encoding="utf-8")
        cp = cli("materials", "scan", "cli-unittest", "--json")
        payload = json.loads(cp.stdout)
        self.assertIn("fuentes/oficiales/Programación — lógica 🧠.txt", payload["added"])
        self.assertEqual(cp.stderr, "")
        self.assertNotIn("NUEVOS", cp.stdout)

    def test_material_scan_json_commit_stays_single_document(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        (COURSE / "fuentes" / "fuente.txt").write_text("v1", encoding="utf-8")
        cp = cli("materials", "scan", "cli-unittest", "--commit", "--json")
        payload = json.loads(cp.stdout)
        self.assertEqual(payload["added"], ["fuentes/fuente.txt"])
        self.assertNotIn("Estado actual", cp.stdout)
        self.assertTrue((COURSE / ".study" / "materials-index.json").is_file())

    def test_due_assessments_and_validate(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        academic_path = COURSE / "academico" / "academic.json"
        academic = json.loads(academic_path.read_text(encoding="utf-8"))
        academic["units"] = [{"id": "U1", "name": "Unidad 1", "topics": ["Funciones"], "source": "Programa", "status": "confirmed"}]
        academic["assessments"] = [{
            "id": "parcial-1",
            "type": "parcial",
            "name": "Parcial 1",
            "date": "2099-09-22",
            "parent_assessment_id": "",
            "format": "",
            "status": "confirmed",
            "scope": [{"kind": "unit", "ref": "U1", "status": "confirmed", "evidence": "Programa"}],
            "source": "Programa",
            "result": {"status": "unknown", "grade": None, "notes": ""},
        }]
        academic_path.write_text(json.dumps(academic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "concept_graph.py"), "upsert", "--course", str(COURSE), "--concept", "Funciones", "--unit", "U1"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        cli("topics", "reconcile", "cli-unittest", "--unit", "U1", "--write")
        due = cli("due", "cli-unittest", "--assessment", "parcial-1", "--include-not-due")
        self.assertIn("Funciones", due.stdout)
        self.assertIn("assessment-confirmed:parcial-1", due.stdout)

        assessments = cli("assessments", "cli-unittest")
        self.assertIn("Parcial 1 [parcial-1]", assessments.stdout)
        self.assertIn("confirmado: U1", assessments.stdout)

        valid = cli("validate", "cli-unittest")
        self.assertIn("no tiene inconsistencias conocidas", valid.stdout)


    def test_status_auto_syncs_graph_and_validate_catches_structure(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        academic_path = COURSE / "academico" / "academic.json"
        academic = json.loads(academic_path.read_text(encoding="utf-8"))
        academic["units"] = [{"id": "U1", "name": "Unidad 1", "topics": ["Arrays"]}]
        academic_path.write_text(json.dumps(academic), encoding="utf-8")
        cli("units", "sync", "cli-unittest")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "concept_graph.py"), "upsert", "--course", str(COURSE), "--concept", "Arrays", "--unit", "U1"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        cli("topics", "reconcile", "cli-unittest", "--unit", "U1", "--write")
        status = cli("status", "cli-unittest")
        self.assertIn("Conceptos trackeados: 1", status.stdout)
        self.assertIn("Nunca evaluados: 1", status.stdout)

        (COURSE / "unidades" / "unidad-1" / "preguntas").rmdir()
        invalid = cli("validate", "cli-unittest")
        self.assertIn("falta carpeta de unidad: unidades/unidad-1/preguntas/", invalid.stdout)

    def test_artifacts_command_and_validate_report_untracked(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        academic_path = COURSE / "academico" / "academic.json"
        academic = json.loads(academic_path.read_text(encoding="utf-8"))
        academic["units"] = [{"id": "U1", "name": "Unidad 1"}]
        academic_path.write_text(json.dumps(academic), encoding="utf-8")
        cli("units", "sync", "cli-unittest")
        legacy = COURSE / "unidades" / "unidad-1" / "resumenes" / "unidad-1-resumen.md"
        legacy.write_text("legacy", encoding="utf-8")
        artifacts = cli("artifacts", "cli-unittest")
        self.assertIn("STALE", artifacts.stdout)
        self.assertIn("untracked-artifact", artifacts.stdout)
        invalid = cli("validate", "cli-unittest")
        self.assertIn("Artefactos derivados desactualizados/no registrados", invalid.stdout)


    def test_course_reset_preserves_sources_and_identity_but_clears_processed_content(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")

        source = COURSE / "fuentes" / "oficiales" / "unidad-1.txt"
        source.write_text("material original", encoding="utf-8")
        cli("materials", "scan", "cli-unittest", "--commit")

        academic_path = COURSE / "academico" / "academic.json"
        academic = json.loads(academic_path.read_text(encoding="utf-8"))
        academic["identity"].update({
            "institution": "UTN",
            "career": "Tecnicatura",
            "chair": "Catedra A",
            "commission": "Noche",
            "professors": ["Ada", "Alan"],
        })
        academic["units"] = [{"id": "U1", "name": "Unidad 1"}]
        academic["assessments"] = [{"id": "p1", "name": "Parcial 1"}]
        academic["rules"] = [{"id": "r1", "text": "regla"}]
        academic_path.write_text(json.dumps(academic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cli("units", "sync", "cli-unittest")
        unit = COURSE / "unidades" / "unidad-1"

        (unit / "notas" / "nota.md").write_text("nota vieja", encoding="utf-8")
        (unit / "preguntas" / "preguntas.md").write_text("preguntas", encoding="utf-8")
        (unit / "resumenes" / "u1-resumen.html").write_text("<html></html>", encoding="utf-8")
        (unit / "simulacros" / "simulacro.md").write_text("simulacro", encoding="utf-8")
        (unit / "assets" / "figures" / "vieja.png").write_bytes(b"png")
        (unit / ".study" / "runs" / "old.txt").write_text("old", encoding="utf-8")

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "concept_graph.py"), "upsert", "--course", str(COURSE), "--concept", "Arrays", "--unit", "U1"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "study_tracker.py"), "add", "--course", str(COURSE), "--concept", "Arrays", "--unit", "U1"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )

        reset = cli("course", "reset", "cli-unittest", "--yes")
        self.assertIn("Materia reseteada", reset.stdout)
        self.assertTrue(source.exists())
        self.assertEqual(source.read_text(encoding="utf-8"), "material original")
        self.assertTrue((COURSE / ".study" / "layout.json").exists())
        self.assertFalse((unit / "notas" / "nota.md").exists())
        self.assertFalse((unit / "preguntas" / "preguntas.md").exists())
        self.assertFalse((unit / "resumenes" / "u1-resumen.html").exists())
        self.assertFalse((unit / "simulacros" / "simulacro.md").exists())
        self.assertFalse((unit / "assets" / "figures" / "vieja.png").exists())

        reset_academic = json.loads(academic_path.read_text(encoding="utf-8"))
        self.assertEqual(reset_academic["identity"]["subject"], "CLI UnitTest")
        self.assertEqual(reset_academic["identity"]["institution"], "UTN")
        self.assertEqual(reset_academic["identity"]["professors"], ["Ada", "Alan"])
        self.assertEqual(reset_academic["units"], [{"id": "U1", "name": "Unidad 1"}])
        self.assertEqual(reset_academic["assessments"], [])
        self.assertEqual(reset_academic["rules"], [])

        concepts = json.loads((unit / "conocimiento" / "concepts.json").read_text(encoding="utf-8"))
        progress = json.loads((unit / "progreso" / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(concepts["concepts"], {})
        self.assertEqual(progress["concepts"], {})

        rescanned = cli("materials", "scan", "cli-unittest")
        self.assertIn("Nuevos:      1", rescanned.stdout)

    def test_course_reset_requires_exact_slug_confirmation(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        source = COURSE / "fuentes" / "source.txt"
        source.write_text("keep", encoding="utf-8")
        academic_path = COURSE / "academico" / "academic.json"
        academic = json.loads(academic_path.read_text(encoding="utf-8"))
        academic["units"] = [{"id": "U1", "name": "Unidad 1"}]
        academic_path.write_text(json.dumps(academic), encoding="utf-8")
        cli("units", "sync", "cli-unittest")
        generated = COURSE / "unidades" / "unidad-1" / "resumenes" / "old.html"
        generated.write_text("old", encoding="utf-8")

        cancelled = cli("course", "reset", "cli-unittest", input_text="NO\n")
        self.assertIn("Cancelado", cancelled.stdout)
        self.assertTrue(generated.exists())
        self.assertTrue(source.exists())

        confirmed = cli("course", "reset", "cli-unittest", input_text="cli-unittest\n")
        self.assertIn("Materia reseteada", confirmed.stdout)
        self.assertFalse(generated.exists())
        self.assertTrue(source.exists())

    def test_interactive_menu_can_open_and_exit(self):
        cp = cli(input_text="0\n")
        self.assertIn("University Study System", cp.stdout)
        self.assertIn("Crear materia", cp.stdout)
        self.assertIn("Resetear contenido de una materia", cp.stdout)

    def test_cli_transcript_inspection(self):
        cli("course", "add", "CLI UnitTest", "--slug", "cli-unittest")
        tdir = COURSE / "fuentes" / "transcripciones"
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "clase.vtt").write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nOjo con esto, es importante.\n", encoding="utf-8")
        inspected = cli("transcripts", "inspect", "cli-unittest")
        self.assertIn("transcripciones/clase.vtt", inspected.stdout)
        self.assertNotIn("transcripciones/README.md", inspected.stdout)
        self.assertIn("candidatos de enfasis: 1", inspected.stdout)
        scanned = cli("materials", "scan", "cli-unittest")
        self.assertIn("Transcripciones: 1", scanned.stdout)


if __name__ == "__main__":
    unittest.main()
