from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import engine_qa


class EngineQaTests(unittest.TestCase):
    def start(self, td: str, *, budget: int = 3, seed: int = 7):
        qa_root = Path(td) / "qa-state"
        courses_root = Path(td) / "courses"
        result = engine_qa.start_run(qa_root, courses_root, budget, seed, "test")
        run_dir = Path(result["run_dir"])
        course = Path(result["course"])
        return qa_root, courses_root, run_dir, course

    def test_start_creates_isolated_v4_course_and_clean_invariants(self):
        with tempfile.TemporaryDirectory() as td:
            qa_root, _courses, run_dir, course = self.start(td)
            self.assertTrue(course.name.startswith("qa-engine-"))
            self.assertTrue((course / "academico" / "academic.json").is_file())
            self.assertTrue((course / "unidades" / "unidad-1" / "conocimiento" / "concepts.json").is_file())
            self.assertTrue((course / "unidades" / "unidad-1" / "fuentes" / "transcripciones" / "clase-1.srt").is_file())
            latest = json.loads((qa_root / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(latest["run_dir"]), run_dir.resolve())
            report = engine_qa.check_invariants(run_dir)
            self.assertTrue(report["ok"], report["issues"])

    def test_budget_is_explicit_and_cannot_be_exceeded(self):
        with tempfile.TemporaryDirectory() as td:
            _qa, _courses, run_dir, _course = self.start(td, budget=1)
            first = engine_qa.record_hypothesis(run_dir, "idempotencia", "idempotent", "ingest")
            self.assertEqual(first["remaining"], 0)
            with self.assertRaises(engine_qa.QaError):
                engine_qa.record_hypothesis(run_dir, "otra", "other", "topics")

    def test_mutations_are_confined_to_synthetic_course_and_journaled(self):
        with tempfile.TemporaryDirectory() as td:
            _qa, _courses, run_dir, course = self.start(td)
            result = engine_qa.mutate_course(
                run_dir,
                "append",
                "unidades/unidad-1/fuentes/oficiales/fundamentos.txt",
                "\nCaso adversarial.\n",
            )
            self.assertTrue(result["ok"])
            self.assertIn("unidades/unidad-1/fuentes/oficiales/fundamentos.txt", result["workspace_diff"]["changed"])
            self.assertIn("Caso adversarial", (course / "unidades/unidad-1/fuentes/oficiales/fundamentos.txt").read_text(encoding="utf-8"))
            with self.assertRaises(engine_qa.QaError):
                engine_qa.mutate_course(run_dir, "write", "../escape.txt", "no")
            journal = (run_dir / "journal.jsonl").read_text(encoding="utf-8")
            self.assertIn('"kind": "mutation"', journal)

    def test_checker_detects_corrupt_json_and_cross_topic_reference(self):
        with tempfile.TemporaryDirectory() as td:
            _qa, _courses, run_dir, course = self.start(td)
            concepts = {
                "version": 2,
                "concepts": {"c1": {"id": "c1", "name": "Concepto", "unit_id": "unidad-1"}},
            }
            topics = {
                "version": 1,
                "unit_id": "unidad-1",
                "topics": {"t1": {"id": "t1", "name": "Tema", "concept_ids": ["missing"]}},
                "unassigned_concept_ids": ["c1"],
            }
            (course / "unidades/unidad-1/conocimiento/concepts.json").write_text(json.dumps(concepts), encoding="utf-8")
            (course / "unidades/unidad-1/conocimiento/topics.json").write_text(json.dumps(topics), encoding="utf-8")
            report = engine_qa.check_invariants(run_dir)
            ids = {row["invariant"] for row in report["issues"]}
            self.assertIn("topic-concept-exists", ids)
            (course / "unidades/unidad-2/conocimiento/topics.json").write_text("{broken", encoding="utf-8")
            report = engine_qa.check_invariants(run_dir)
            ids = {row["invariant"] for row in report["issues"]}
            self.assertIn("course-json-valid", ids)

    def test_exec_uses_allowlist_and_rejects_other_course(self):
        with tempfile.TemporaryDirectory() as td:
            _qa, _courses, run_dir, _course = self.start(td)
            with self.assertRaises(engine_qa.QaError):
                engine_qa.validate_exec_args(run_dir, "not-a-tool.py", [])
            with self.assertRaises(engine_qa.QaError):
                engine_qa.validate_exec_args(run_dir, "topic_catalog.py", ["validate", "--course", str(Path(td) / "other"), "--unit", "unidad-1"])
            result = engine_qa.exec_engine(
                run_dir,
                "transcript_tools.py",
                ["inspect", "--course", "@course", "--unit", "unidad-1"],
                0,
                20,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["returncode"], 0)
            self.assertTrue(result["engine_unchanged"])

    def test_confirmed_finding_and_finish_create_persistent_history(self):
        with tempfile.TemporaryDirectory() as td:
            qa_root, _courses, run_dir, _course = self.start(td)
            engine_qa.record_hypothesis(run_dir, "probar una propiedad", "qa-test", "contracts")
            with self.assertRaises(engine_qa.QaError):
                engine_qa.record_finding(run_dir, "sospecha", "high", "qa-test", "A", "B", "", False)
            finding = engine_qa.record_finding(run_dir, "fallo confirmado", "high", "qa-test", "A", "B", "mínimo", True)
            self.assertEqual(finding["id"], "QA-001")
            result = engine_qa.finish_run(run_dir, export=False)
            self.assertTrue((run_dir / "report.md").is_file())
            self.assertEqual(result["findings"], 1)
            history = engine_qa.history(qa_root)
            self.assertEqual(history["runs"][-1]["findings"], 1)
            self.assertEqual(history["finding_counts"]["qa-test"], 1)

    def test_internal_skill_is_portable_but_not_public_action(self):
        root = Path(__file__).resolve().parents[1]
        actions = json.loads((root / "config/actions.json").read_text(encoding="utf-8"))
        self.assertNotIn("engine-qa", actions)
        source = (root / "skills-src/engine-qa/SKILL.md").read_bytes()
        self.assertEqual((root / ".claude/skills/engine-qa/SKILL.md").read_bytes(), source)
        self.assertEqual((root / ".agents/skills/engine-qa/SKILL.md").read_bytes(), source)
        self.assertIn("no forma parte de las nueve acciones públicas", source.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
