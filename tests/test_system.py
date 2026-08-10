from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(script: str, *args: str):
    cp = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
    )
    return cp.stdout.strip(), cp.stderr.strip()


class StudySystemTests(unittest.TestCase):
    def make_course(self, td: str) -> Path:
        course = Path(td) / "course"
        for sub in ["fuentes", "conocimiento", "progreso", "academico"]:
            (course / sub).mkdir(parents=True, exist_ok=True)
        (course / "conocimiento" / "concepts.json").write_text('{"version":2,"concepts":{}}\n', encoding="utf-8")
        (course / "progreso" / "progress.json").write_text('{"version":2,"concepts":{}}\n', encoding="utf-8")
        (course / "academico" / "academic.json").write_text(
            json.dumps({
                "version": 1,
                "identity": {},
                "units": [{"id": "U1", "name": "Unidad 1", "topics": ["Funciones"]}],
                "assessments": [],
                "rules": [],
                "official_status": {},
            }),
            encoding="utf-8",
        )
        return course

    def test_prerequisite_is_not_double_counted(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run("concept_graph.py", "upsert", "--course", str(course), "--concept", "Funciones")
            run("concept_graph.py", "upsert", "--course", str(course), "--concept", "Recursividad")
            run("concept_graph.py", "link", "--course", str(course), "--concept", "Recursividad", "--type", "depends-on", "--target", "Funciones")
            run("study_tracker.py", "add", "--course", str(course), "--concept", "Funciones")
            out, _ = run("study_tracker.py", "due", "--course", str(course))
            rows = json.loads(out)
            self.assertEqual(rows[0]["prerequisite_for_count"], 1)

    def test_assessment_relevance_is_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run("concept_graph.py", "upsert", "--course", str(course), "--concept", "Funciones")
            run("concept_graph.py", "relevance", "--course", str(course), "--concept", "Funciones", "--assessment", "parcial-1", "--status", "confirmed", "--evidence", "Temario")
            run("concept_graph.py", "relevance", "--course", str(course), "--concept", "Funciones", "--assessment", "parcial-2", "--status", "excluded", "--evidence", "Temario")
            run("study_tracker.py", "add", "--course", str(course), "--concept", "Funciones")
            p1, _ = run("study_tracker.py", "due", "--course", str(course), "--assessment", "parcial-1")
            p2, _ = run("study_tracker.py", "due", "--course", str(course), "--assessment", "parcial-2")
            r1 = json.loads(p1)[0]
            r2 = json.loads(p2)[0]
            self.assertEqual(r1["assessment_relevance"], "confirmed")
            self.assertEqual(r2["assessment_relevance"], "excluded")
            self.assertGreater(r1["study_priority"], r2["study_priority"])

    def test_source_fingerprint_detects_stale_concept(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            src = course / "fuentes" / "unidad-1.txt"
            src.write_text("version uno", encoding="utf-8")
            run("concept_graph.py", "source", "--course", str(course), "--concept", "Funciones", "--file", "unidad-1.txt", "--section", "1")
            fresh, _ = run("concept_graph.py", "stale", "--course", str(course))
            self.assertEqual(json.loads(fresh), [])
            src.write_text("version dos", encoding="utf-8")
            stale, _ = run("concept_graph.py", "stale", "--course", str(course))
            rows = json.loads(stale)
            self.assertEqual(rows[0]["reason"], "source-changed")
            self.assertEqual(rows[0]["concept"], "Funciones")

    def test_academic_validation_warns_on_unbacked_confirmed_scope(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run("academic_context.py", "add-assessment", "--course", str(course), "--id", "parcial-1", "--type", "parcial", "--name", "Parcial 1", "--scope-unit", "U1", "--scope-status", "confirmed")
            out, _ = run("academic_context.py", "validate", "--course", str(course))
            data = json.loads(out)
            messages = [i["message"] for i in data["issues"]]
            self.assertTrue(any("confirmed scope lacks evidence" in m for m in messages))

    def test_sync_adds_untracked_graph_concepts(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run("concept_graph.py", "upsert", "--course", str(course), "--concept", "Funciones", "--unit", "U1")
            out, _ = run("study_tracker.py", "sync", "--course", str(course))
            result = json.loads(out)
            self.assertEqual(result["added"], ["Funciones"])
            due, _ = run("study_tracker.py", "due", "--course", str(course))
            self.assertEqual(json.loads(due)[0]["name"], "Funciones")

    def test_due_can_infer_relevance_from_assessment_unit_scope(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run("academic_context.py", "add-assessment", "--course", str(course), "--id", "parcial-1", "--type", "parcial", "--name", "Parcial 1", "--scope-unit", "U1", "--scope-status", "confirmed", "--source", "Temario")
            run("concept_graph.py", "upsert", "--course", str(course), "--concept", "Funciones", "--unit", "U1")
            run("study_tracker.py", "add", "--course", str(course), "--concept", "Funciones", "--unit", "U1")
            out, _ = run("study_tracker.py", "due", "--course", str(course), "--assessment", "Parcial 1")
            row = json.loads(out)[0]
            self.assertEqual(row["assessment"], "parcial-1")
            self.assertEqual(row["assessment_relevance"], "confirmed")
            self.assertIn("assessment-confirmed:parcial-1", row["priority_reasons"])
            # Push review into the future, then verify assessment mode can still surface it.
            run("study_tracker.py", "record", "--course", str(course), "--concept", "Funciones", "--rating", "5")
            future, _ = run("study_tracker.py", "due", "--course", str(course), "--assessment", "parcial-1", "--include-not-due")
            future_row = json.loads(future)[0]
            self.assertIn("assessment-review-not-due", future_row["priority_reasons"])

    def test_academic_validation_catches_unknown_parent_and_topic(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run("academic_context.py", "add-assessment", "--course", str(course), "--id", "rec-1", "--type", "recuperatorio", "--name", "Recuperatorio 1", "--parent", "missing", "--scope-topic", "Tema inexistente", "--scope-status", "likely", "--source", "Aviso")
            out, _ = run("academic_context.py", "validate", "--course", str(course))
            data = json.loads(out)
            messages = [i["message"] for i in data["issues"]]
            self.assertTrue(any("parent assessment does not exist" in m for m in messages))
            self.assertTrue(any("scope references unknown topic" in m for m in messages))

    def test_transcript_parser_preserves_timestamps_and_flags_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            tdir = course / "fuentes" / "transcripciones"
            tdir.mkdir(parents=True, exist_ok=True)
            src = tdir / "clase-1.srt"
            src.write_text("1\n00:00:10,000 --> 00:00:14,000\nOjo con esto, es un error tipico.\n\n2\n00:00:20,000 --> 00:00:24,000\nEsto probablemente entra en el parcial.\n", encoding="utf-8")
            out, _ = run("transcript_tools.py", "inspect", "--course", str(course))
            rows = json.loads(out)
            self.assertEqual(rows[0]["timestamped_segments"], 2)
            self.assertEqual(rows[0]["cue_candidates"][0]["start"], "00:00:10")
            cue_types = {t for c in rows[0]["cue_candidates"] for t in c["cue_types"]}
            self.assertIn("common-error", cue_types)
            self.assertIn("exam-cue", cue_types)

    def test_transcript_source_and_teacher_signal_remain_separate_from_exam_scope(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            tdir = course / "fuentes" / "transcripciones"
            tdir.mkdir(parents=True, exist_ok=True)
            src = tdir / "clase.txt"
            src.write_text("[00:12:00] Esto es importante", encoding="utf-8")
            run("concept_graph.py", "source", "--course", str(course), "--concept", "Arrays", "--file", "transcripciones/clase.txt", "--timestamp", "00:12:00", "--kind", "transcript")
            run("concept_graph.py", "emphasis", "--course", str(course), "--concept", "Arrays", "--file", "transcripciones/clase.txt", "--timestamp", "00:12:00", "--type", "important", "--text", "Esto es importante", "--confidence", "explicit")
            out, _ = run("concept_graph.py", "show", "--course", str(course), "--concept", "Arrays")
            card = json.loads(out)
            self.assertEqual(card["sources"][0]["timestamp"], "00:12:00")
            self.assertEqual(card["sources"][0]["kind"], "transcript")
            self.assertEqual(card["teaching_signals"][0]["type"], "important")
            self.assertEqual(card["assessment_relevance"]["by_assessment"], {})

    def test_teacher_emphasis_is_only_a_soft_priority_signal(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run("concept_graph.py", "upsert", "--course", str(course), "--concept", "Arrays", "--unit", "U1")
            run("concept_graph.py", "emphasis", "--course", str(course), "--concept", "Arrays", "--file", "transcripciones/clase.txt", "--type", "exam-cue", "--text", "Capaz esto entra", "--confidence", "ambiguous")
            run("study_tracker.py", "add", "--course", str(course), "--concept", "Arrays", "--unit", "U1")
            out, _ = run("study_tracker.py", "due", "--course", str(course))
            row = json.loads(out)[0]
            self.assertTrue(any(r.startswith("teacher-emphasis:") for r in row["priority_reasons"]))
            self.assertLess(row["study_priority"], 12.0)
            self.assertEqual(row["assessment_relevance"], "unknown")

    def test_vtt_speaker_and_windows_encodings_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            tdir = course / "fuentes" / "transcripciones"
            tdir.mkdir(parents=True, exist_ok=True)
            vtt = tdir / "clase.vtt"
            vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Profesor Pérez>Esto es importante.</v>\n", encoding="utf-8")
            out, _ = run("transcript_tools.py", "inspect", "--course", str(course), "--file", "transcripciones/clase.vtt", "--write")
            rows = json.loads(out)
            self.assertEqual(rows[0]["cue_candidates"][0]["speaker"], "Profesor Pérez")

            txt = tdir / "windows.txt"
            txt.write_bytes("[00:01:00] Presten atención con la asignación".encode("cp1252"))
            out, _ = run("transcript_tools.py", "inspect", "--course", str(course), "--file", "transcripciones/windows.txt")
            rows = json.loads(out)
            self.assertEqual(rows[0]["timestamped_segments"], 1)
            self.assertIn("atención", rows[0]["cue_candidates"][0]["text"].lower())


if __name__ == "__main__":
    unittest.main()
