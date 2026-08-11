from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from scripts.pipeline_run import engine_snapshot, sha
from scripts.publish_quiz import publish_quiz
from scripts.quiz_artifact import check_command, render_command, validate_quiz_document
from scripts.quiz_browser_check import run_check as run_browser_check
from scripts.quiz_run import validate_quiz_run


def valid_quiz() -> dict:
    return {
        "version": 1,
        "unit_id": "unidad-1",
        "title": "Quiz de Unidad 1",
        "questions": [
            {
                "id": "q-1",
                "topic_id": "variables",
                "concept_ids": ["variable"],
                "difficulty": "basic",
                "prompt": "¿Qué representa una variable?",
                "options": [
                    {"id": "a", "text": "Un dato identificado por un nombre", "feedback": "Correcto: permite referenciar un valor mediante un identificador."},
                    {"id": "b", "text": "Una estructura de repetición", "feedback": "No: una estructura de repetición controla iteraciones."},
                    {"id": "c", "text": "Una salida por pantalla", "feedback": "No: mostrar un dato es una operación, no una variable."},
                    {"id": "d", "text": "Un comentario del programa", "feedback": "No: los comentarios no almacenan el estado del algoritmo."},
                ],
                "correct_option_id": "a",
            },
            {
                "id": "q-2",
                "topic_id": "operadores",
                "concept_ids": ["precedencia"],
                "difficulty": "intermediate",
                "prompt": "¿Qué valor se obtiene?",
                "code": "resultado = 2 + 3 * 4",
                "options": [
                    {"id": "a", "text": "20", "feedback": "No: eso evaluaría la suma antes que la multiplicación."},
                    {"id": "b", "text": "14", "feedback": "Correcto: la multiplicación tiene prioridad sobre la suma."},
                    {"id": "c", "text": "24", "feedback": "No: ese valor no sigue la expresión indicada."},
                    {"id": "d", "text": "9", "feedback": "No: se omite parte de la operación."},
                ],
                "correct_option_id": "b",
            },
        ],
    }


def make_course(root: Path) -> Path:
    course = root / "course"
    unit = course / "unidades" / "unidad-1"
    (course / "academico").mkdir(parents=True)
    (unit / "conocimiento").mkdir(parents=True)
    (course / "academico" / "academic.json").write_text(
        json.dumps({"units": [{"id": "U1", "name": "Unidad 1", "topics": []}]}),
        encoding="utf-8",
    )
    (unit / "conocimiento" / "concepts.json").write_text(
        json.dumps(
            {
                "version": 2,
                "concepts": {
                    "variable": {"id": "variable", "name": "Variable"},
                    "precedencia": {"id": "precedencia", "name": "Precedencia"},
                    "suelto": {"id": "suelto", "name": "Concepto sin tema"},
                },
            }
        ),
        encoding="utf-8",
    )
    (unit / "conocimiento" / "topics.json").write_text(
        json.dumps(
            {
                "version": 1,
                "unit_id": "unidad-1",
                "topics": {
                    "variables": {"id": "variables", "name": "Variables", "concept_ids": ["variable"]},
                    "operadores": {"id": "operadores", "name": "Operadores", "concept_ids": ["precedencia"]},
                },
                "unassigned_concept_ids": ["suelto"],
            }
        ),
        encoding="utf-8",
    )
    (unit / "conocimiento" / "figures.json").write_text(
        json.dumps({"version": 2, "figures": {}}),
        encoding="utf-8",
    )
    return course


class BrowserQuizTests(unittest.TestCase):
    def test_valid_quiz_renders_self_contained_practice_and_exam_modes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            course = make_course(root)
            source = root / "quiz.json"
            html = root / "quiz.html"
            source.write_text(json.dumps(valid_quiz(), ensure_ascii=False, indent=2), encoding="utf-8")

            rendered = render_command(course, "unidad-1", source, html)
            checked = check_command(course, "unidad-1", source, html)

            self.assertTrue(rendered["ok"], rendered)
            self.assertTrue(checked["ok"], checked)
            text = html.read_text(encoding="utf-8")
            self.assertIn('data-start-mode="practice"', text)
            self.assertIn('data-start-mode="exam"', text)
            self.assertIn('id="topic-results"', text)
            self.assertIn('class="question-code"', text)
            self.assertNotIn("<script src=", text.lower())
            self.assertNotIn('<link rel="stylesheet"', text.lower())
            self.assertIn("no actualiza <code>progress.json</code>", text)

    def test_real_chromium_exercises_practice_and_exam_interactions(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            course = make_course(root)
            source = root / "quiz.json"
            html = root / "quiz.html"
            out_dir = root / "interaction-audit"
            source.write_text(json.dumps(valid_quiz(), ensure_ascii=False, indent=2), encoding="utf-8")
            rendered = render_command(course, "unidad-1", source, html)
            self.assertTrue(rendered["ok"], rendered)

            result = run_browser_check(source, html, out_dir)

            self.assertTrue(result["ok"], result)
            self.assertTrue(result["modes"]["practice"]["feedback_visible_after_check"])
            self.assertEqual(result["modes"]["exam"]["score"], "100%")
            self.assertEqual(result["modes"]["exam"]["answered"], 2)
            self.assertEqual(set(result["screenshots"]), {"practice_feedback", "exam_question_mobile", "exam_result_mobile"})
            for path in result["screenshots"].values():
                self.assertGreater(Path(path).stat().st_size, 0)

    def test_validator_allows_integrative_questions_when_primary_topic_is_represented(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            course = make_course(root)
            quiz = valid_quiz()
            quiz["questions"][0]["concept_ids"] = ["variable", "precedencia"]

            result = validate_quiz_document(quiz, course=course, unit="unidad-1")

            self.assertTrue(result["ok"], result)

    def test_validator_rejects_unknown_concepts_and_unrepresented_primary_topic(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            course = make_course(root)
            quiz = valid_quiz()
            quiz["questions"][0]["concept_ids"] = ["precedencia", "no-existe"]

            result = validate_quiz_document(quiz, course=course, unit="unidad-1")

            self.assertFalse(result["ok"])
            self.assertIn("q1:unknown-concept:no-existe", result["errors"])
            self.assertIn("q1:primary-topic-not-represented:variables", result["errors"])

    def test_unassigned_primary_topic_can_include_supporting_assigned_concepts(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            course = make_course(root)
            quiz = valid_quiz()
            quiz["questions"][0]["concept_ids"] = ["suelto", "precedencia"]
            quiz["questions"][0]["topic_id"] = None

            result = validate_quiz_document(quiz, course=course, unit="unidad-1")
            self.assertTrue(result["ok"], result)

            quiz["questions"][0]["concept_ids"] = ["precedencia"]
            result = validate_quiz_document(quiz, course=course, unit="unidad-1")
            self.assertFalse(result["ok"])
            self.assertIn("q1:unassigned-primary-topic-not-represented", result["errors"])

    def test_publish_is_identity_and_keeps_sources_immutable(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            source_json = root / "source.json"
            source_html = root / "source.html"
            dest_json = root / "published" / "_source" / "quiz.json"
            dest_html = root / "published" / "quiz.html"
            report_path = root / "report.json"
            source_json.write_bytes(b'{"version":1}\n')
            source_html.write_bytes(b"<html>quiz</html>")
            before_json = source_json.read_bytes()
            before_html = source_html.read_bytes()

            report = publish_quiz(source_json, source_html, dest_json, dest_html, report_path)

            self.assertTrue(report["ok"])
            self.assertEqual(source_json.read_bytes(), before_json)
            self.assertEqual(source_html.read_bytes(), before_html)
            self.assertEqual(dest_json.read_bytes(), before_json)
            self.assertEqual(dest_html.read_bytes(), before_html)
            for row in report["files"]:
                self.assertEqual(row["transform"], "identity")
                self.assertEqual(row["source_sha256"], row["destination_sha256"])

    def test_quiz_run_cli_starts_inside_resolved_unit(self):
        slug = "zz-quiz-cli-" + uuid.uuid4().hex[:8]
        course = ROOT / "materias" / slug
        try:
            unit = course / "unidades" / "unidad-1"
            (course / "academico").mkdir(parents=True)
            (unit / "conocimiento").mkdir(parents=True)
            (course / "academico" / "academic.json").write_text(
                json.dumps({"units": [{"id": "U1", "name": "Unidad 1"}]}),
                encoding="utf-8",
            )
            (unit / "conocimiento" / "concepts.json").write_text(json.dumps({"version": 2, "concepts": {}}), encoding="utf-8")
            (unit / "conocimiento" / "topics.json").write_text(json.dumps({"version": 1, "unit_id": "unidad-1", "topics": {}, "unassigned_concept_ids": []}), encoding="utf-8")
            (unit / "conocimiento" / "figures.json").write_text(json.dumps({"version": 2, "figures": {}}), encoding="utf-8")

            cp = subprocess.run(
                [sys.executable, "scripts/quiz_run.py", "start", "--course", slug, "--unit", "unidad-1"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            payload = json.loads(cp.stdout)
            run = ROOT / payload["run_dir"]
            self.assertTrue(run.is_relative_to(unit / ".study" / "runs"))
            self.assertEqual(json.loads((run / "01-input.json").read_text(encoding="utf-8"))["unit_id"], "unidad-1")
        finally:
            shutil.rmtree(course, ignore_errors=True)

    def test_full_quiz_run_contract_binds_review_canonical_state_and_publication(self):
        slug = "zz-quiz-" + uuid.uuid4().hex[:8]
        course = ROOT / "materias" / slug
        try:
            unit = course / "unidades" / "unidad-1"
            (course / "academico").mkdir(parents=True)
            (unit / "conocimiento").mkdir(parents=True)
            (unit / ".study" / "runs" / "run-1").mkdir(parents=True)
            run = unit / ".study" / "runs" / "run-1"

            academic = course / "academico" / "academic.json"
            concepts = unit / "conocimiento" / "concepts.json"
            topics = unit / "conocimiento" / "topics.json"
            figures = unit / "conocimiento" / "figures.json"
            academic.write_text(json.dumps({"units": [{"id": "U1", "name": "Unidad 1"}]}), encoding="utf-8")
            concepts.write_text(json.dumps({"version": 2, "concepts": {"variable": {"id": "variable", "name": "Variable"}}}), encoding="utf-8")
            topics.write_text(json.dumps({"version": 1, "unit_id": "unidad-1", "topics": {"variables": {"id": "variables", "name": "Variables", "concept_ids": ["variable"]}}, "unassigned_concept_ids": []}), encoding="utf-8")
            figures.write_text(json.dumps({"version": 2, "figures": {}}), encoding="utf-8")

            quiz = valid_quiz()
            quiz["questions"] = [quiz["questions"][0]]
            candidate = run / "02-quiz.json"
            final = run / "04-final.json"
            rendered = run / "09-rendered.html"
            candidate.write_text(json.dumps(quiz, ensure_ascii=False, indent=2), encoding="utf-8")
            final.write_bytes(candidate.read_bytes())
            review = {
                "version": 1,
                "candidate_sha256": sha(candidate),
                "pass": True,
                "issues": [],
                "checks": {
                    "canonical_fidelity": True,
                    "single_best_answer": True,
                    "distractor_quality": True,
                    "no_answer_cues": True,
                    "feedback_quality": True,
                    "topic_coverage": True,
                },
            }
            (run / "03-review.json").write_text(json.dumps(review), encoding="utf-8")
            render_command(course, "unidad-1", final, rendered)
            integrity = check_command(course, "unidad-1", final, rendered)
            (run / "10-integrity.json").write_text(json.dumps(integrity), encoding="utf-8")

            interaction_root = run / "interaction-audit"
            interaction_root.mkdir()
            screenshots = {
                "practice_feedback": interaction_root / "practice-feedback.png",
                "exam_question_mobile": interaction_root / "exam-question-mobile.png",
                "exam_result_mobile": interaction_root / "exam-result-mobile.png",
            }
            for path in screenshots.values():
                path.write_bytes(b"png")
            (run / "10-interaction.json").write_text(
                json.dumps({
                    "ok": True,
                    "engine": "playwright-chromium",
                    "source_sha256": sha(final),
                    "html_sha256": sha(rendered),
                    "modes": {"practice": {"ok": True}, "exam": {"ok": True}},
                    "screenshots": {key: path.resolve().as_posix() for key, path in screenshots.items()},
                }),
                encoding="utf-8",
            )

            visual = run / "visual-audit"
            visual.mkdir()
            (visual / "audit.json").write_text(json.dumps({"ok": True, "engine": "chromium-set-content"}), encoding="utf-8")
            (visual / "desktop.png").write_bytes(b"desktop")
            (visual / "mobile.png").write_bytes(b"mobile")

            dest_json = unit / "preguntas" / "_source" / "unidad-1-quiz.json"
            dest_html = unit / "preguntas" / "unidad-1-quiz.html"
            publish_quiz(final, rendered, dest_json, dest_html, run / "11-publication.json")

            inp = {
                "pipeline": "quiz",
                "course": course.relative_to(ROOT).as_posix(),
                "scope": "unidad-1",
                "unit_id": "unidad-1",
                "academic_file": academic.relative_to(ROOT).as_posix(),
                "concepts_file": concepts.relative_to(ROOT).as_posix(),
                "topics_file": topics.relative_to(ROOT).as_posix(),
                "figures_file": figures.relative_to(ROOT).as_posix(),
                "academic_sha256": sha(academic),
                "concepts_sha256": sha(concepts),
                "topics_sha256": sha(topics),
                "figures_sha256": sha(figures),
            }
            (run / "01-input.json").write_text(json.dumps(inp), encoding="utf-8")
            manifest = {
                "version": 2,
                "pipeline": "quiz",
                "course": course.relative_to(ROOT).as_posix(),
                "scope": "unidad-1",
                "status": "running",
                "course_script_snapshot": [],
                "engine_snapshot": engine_snapshot(),
            }
            (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = validate_quiz_run(run)
            self.assertTrue(result["ok"], result)

            topics.write_text(json.dumps({"version": 1, "unit_id": "unidad-1", "topics": {}, "unassigned_concept_ids": ["variable"]}), encoding="utf-8")
            changed = validate_quiz_run(run)
            self.assertFalse(changed["ok"])
            self.assertIn("canonical-changed:topics", changed["errors"])
        finally:
            shutil.rmtree(course, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
