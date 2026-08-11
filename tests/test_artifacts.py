import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "artifact_state.py"


class ArtifactStateTests(unittest.TestCase):
    def make_course(self, td: str) -> Path:
        c = Path(td) / "course"
        (c / "academico").mkdir(parents=True)
        (c / "conocimiento").mkdir()
        (c / "resumenes").mkdir()
        (c / "preguntas").mkdir()
        (c / "simulacros").mkdir()
        (c / "academico" / "academic.json").write_text(json.dumps({"version": 1, "assessments": []}), encoding="utf-8")
        (c / "conocimiento" / "concepts.json").write_text(json.dumps({
            "version": 2,
            "concepts": {
                "variables": {"id": "variables", "name": "Variables", "unit": "Unidad 1", "summary": "x"},
                "loops": {"id": "loops", "name": "Loops", "unit": "Unidad 2", "summary": "y"},
            },
        }), encoding="utf-8")
        (c / "conocimiento" / "figures.json").write_text(json.dumps({"version": 1, "figures": {}}), encoding="utf-8")
        return c

    def run_cli(self, *args: str):
        cp = subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=True)
        return json.loads(cp.stdout)

    def test_mark_then_current(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            f = c / "resumenes" / "unidad-1-resumen.md"
            f.write_text("ok", encoding="utf-8")
            marked = self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md", "--type", "summary", "--scope", "Unidad 1")
            self.assertFalse(marked["stale"])
            rows = self.run_cli("status", "--course", str(c))
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]["stale"])

    def test_academic_change_marks_stale(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            f = c / "resumenes" / "unidad-1-resumen.md"
            f.write_text("ok", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md", "--type", "summary", "--scope", "Unidad 1")
            (c / "academico" / "academic.json").write_text(json.dumps({"version": 1, "assessments": [{"id": "p1"}]}), encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c))
            self.assertTrue(rows[0]["stale"])
            self.assertIn("academic-context-changed", rows[0]["reasons"])

    def test_same_unit_knowledge_change_marks_stale(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            f = c / "resumenes" / "unidad-1-resumen.md"
            f.write_text("ok", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md", "--type", "summary", "--scope", "Unidad 1")
            data = json.loads((c / "conocimiento" / "concepts.json").read_text(encoding="utf-8"))
            data["concepts"]["variables"]["summary"] = "changed"
            (c / "conocimiento" / "concepts.json").write_text(json.dumps(data), encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c))
            self.assertTrue(rows[0]["stale"])
            self.assertIn("knowledge-changed", rows[0]["reasons"])

    def test_observed_topic_change_marks_stale(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            topics_path = c / "conocimiento" / "topics.json"
            topics = {
                "version": 1,
                "unit_id": "unidad-1",
                "topics": {
                    "variables": {
                        "id": "variables",
                        "unit_id": "unidad-1",
                        "name": "Variables",
                        "aliases": [],
                        "concept_ids": ["variables"],
                        "declared_matches": [],
                        "evidence": [],
                    }
                },
                "unassigned_concept_ids": [],
            }
            topics_path.write_text(json.dumps(topics), encoding="utf-8")
            artifact = c / "resumenes" / "unidad-1-resumen.md"
            artifact.write_text("ok", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md", "--type", "summary", "--scope", "Unidad 1")
            topics["topics"]["variables"]["name"] = "Variables y asignación"
            topics_path.write_text(json.dumps(topics), encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c))
            self.assertTrue(rows[0]["stale"])
            self.assertIn("topic-knowledge-changed", rows[0]["reasons"])

    def test_other_unit_knowledge_change_does_not_stale_unit_scope(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            f = c / "resumenes" / "unidad-1-resumen.md"
            f.write_text("ok", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md", "--type", "summary", "--scope", "Unidad 1")
            data = json.loads((c / "conocimiento" / "concepts.json").read_text(encoding="utf-8"))
            data["concepts"]["loops"]["summary"] = "changed"
            (c / "conocimiento" / "concepts.json").write_text(json.dumps(data), encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c))
            self.assertFalse(rows[0]["stale"])

    def test_dependency_change_marks_unit_artifact_stale(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            data = json.loads((c / "conocimiento" / "concepts.json").read_text(encoding="utf-8"))
            data["concepts"]["loops"]["prerequisites"] = ["Variables"]
            (c / "conocimiento" / "concepts.json").write_text(json.dumps(data), encoding="utf-8")
            f = c / "resumenes" / "unidad-2-resumen.md"
            f.write_text("ok", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-2-resumen.md", "--type", "summary", "--scope", "Unidad 2")
            data["concepts"]["variables"]["summary"] = "dependency changed"
            (c / "conocimiento" / "concepts.json").write_text(json.dumps(data), encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c))
            self.assertTrue(rows[0]["stale"])
            self.assertIn("knowledge-changed", rows[0]["reasons"])

    def test_untracked_generated_file_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            (c / "resumenes" / "legacy.md").write_text("old", encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c))
            self.assertTrue(rows[0]["stale"])
            self.assertIn("untracked-artifact", rows[0]["reasons"])


    def test_new_marks_use_contract_version_9(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            artifact = c / "resumenes" / "unidad-1-resumen.md"
            artifact.write_text("new", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md", "--type", "summary", "--scope", "Unidad 1")
            manifest = json.loads((c / ".study" / "artifacts.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifacts"]["resumenes/unidad-1-resumen.md"]["artifact_contract_version"], 9)
            self.assertIn("topics_sha256", manifest["artifacts"]["resumenes/unidad-1-resumen.md"])
            self.assertIn("design_sha256", manifest["artifacts"]["resumenes/unidad-1-resumen.md"])

    def test_non_visual_artifact_does_not_depend_on_design_system(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            artifact = c / "preguntas" / "unidad-1.md"
            artifact.write_text("q", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "preguntas/unidad-1.md", "--type", "questions", "--scope", "Unidad 1")
            manifest = json.loads((c / ".study" / "artifacts.json").read_text(encoding="utf-8"))
            self.assertNotIn("design_sha256", manifest["artifacts"]["preguntas/unidad-1.md"])


    def test_same_unit_figure_change_marks_stale(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            f = c / "resumenes" / "unidad-1-resumen.html"
            f.write_text("<html>ok</html>", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.html", "--type", "summary", "--scope", "Unidad 1")
            figures = {"version": 1, "figures": {"f1": {"id": "f1", "unit": "Unidad 1", "description": "diagram"}}}
            (c / "conocimiento" / "figures.json").write_text(json.dumps(figures), encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c), "--file", "resumenes/unidad-1-resumen.html")
            self.assertTrue(rows[0]["stale"])
            self.assertIn("visual-knowledge-changed", rows[0]["reasons"])

    def test_visual_artifact_stales_when_design_system_changes(self):
        theme = ROOT / "assets" / "study-theme.css"
        original = theme.read_bytes()
        try:
            with tempfile.TemporaryDirectory() as td:
                c = self.make_course(td)
                artifact = c / "resumenes" / "unidad-1-resumen.html"
                artifact.write_text("<html>ok</html>", encoding="utf-8")
                self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.html", "--type", "summary", "--scope", "Unidad 1")
                theme.write_bytes(original + b"\n/* temporary-test-change */\n")
                rows = self.run_cli("status", "--course", str(c), "--file", "resumenes/unidad-1-resumen.html")
                self.assertTrue(rows[0]["stale"])
                self.assertIn("design-system-changed", rows[0]["reasons"])
        finally:
            theme.write_bytes(original)

    def test_old_contract_version_marks_stale(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make_course(td)
            artifact = c / "resumenes" / "unidad-1-resumen.md"
            artifact.write_text("old", encoding="utf-8")
            self.run_cli("mark", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md", "--type", "summary", "--scope", "Unidad 1")
            manifest_path = c / ".study" / "artifacts.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["artifacts"]["resumenes/unidad-1-resumen.md"]["artifact_contract_version"] = 2
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            rows = self.run_cli("status", "--course", str(c), "--file", "resumenes/unidad-1-resumen.md")
            self.assertTrue(rows[0]["stale"])
            self.assertIn("artifact-contract-changed", rows[0]["reasons"])


if __name__ == "__main__":
    unittest.main()
