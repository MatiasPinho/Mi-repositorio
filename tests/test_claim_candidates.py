import json
import tempfile
import unittest
from pathlib import Path

from scripts.claim_candidates import (
    AUTO_ORIGIN,
    extract_candidates_from_text,
    run_benchmark,
    scan_course,
    write_candidates,
)


class ClaimCandidateTests(unittest.TestCase):
    def make_course(self, root: Path) -> Path:
        course = root / "course"
        (course / "academico").mkdir(parents=True)
        (course / "fuentes" / "transcripciones").mkdir(parents=True)
        (course / "fuentes" / "oficiales").mkdir(parents=True)
        (course / "academico" / "academic.json").write_text(
            json.dumps({"version": 2, "claims": [], "claim_candidates": []}),
            encoding="utf-8",
        )
        return course

    def test_frozen_benchmark_passes(self):
        result = run_benchmark()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["passed"], result["total"])

    def test_ambiguous_pronoun_is_candidate_but_not_semantic_ready(self):
        rows = extract_candidates_from_text(
            "Esto entra en el parcial.",
            source="transcripciones/clase.txt",
            source_type="teacher_transcript",
            locator={"segment": 1},
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["semantic_ready"])
        self.assertEqual(rows[0]["hints"]["object"], "")

    def test_transcript_candidate_preserves_timestamp_and_stays_pending(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            transcript = course / "fuentes" / "transcripciones" / "clase.srt"
            transcript.write_text(
                "1\n00:12:34,000 --> 00:12:39,000\nUnidad 4 no entra en el final.\n\n",
                encoding="utf-8",
            )
            result = scan_course(course)
            self.assertEqual(result["total"], 1)
            row = result["candidates"][0]
            self.assertEqual(row["review_status"], "pending")
            self.assertEqual(row["source_type_suggestion"], "teacher_transcript")
            self.assertEqual(row["locator"]["timestamp"], "00:12:34")
            self.assertEqual(row["evidence_ref"], "transcripciones/clase.srt#00:12:34")
            self.assertFalse(row["hints"]["value"])

    def test_write_never_promotes_candidate_into_canonical_claims(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            transcript = course / "fuentes" / "transcripciones" / "clase.txt"
            transcript.write_text("Unidad 2 entra en el parcial.\n", encoding="utf-8")
            result = write_candidates(course, scan_course(course))
            self.assertEqual(result["written"], 1)
            data = json.loads((course / "academico" / "academic.json").read_text(encoding="utf-8"))
            self.assertEqual(data["claims"], [])
            self.assertEqual(len(data["claim_candidates"]), 1)
            self.assertEqual(data["claim_candidates"][0]["origin"], AUTO_ORIGIN)

    def test_rescan_is_idempotent_and_preserves_review_status(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            transcript = course / "fuentes" / "transcripciones" / "clase.txt"
            transcript.write_text("La materia se aprueba con 6.\n", encoding="utf-8")
            write_candidates(course, scan_course(course))
            academic = course / "academico" / "academic.json"
            data = json.loads(academic.read_text(encoding="utf-8"))
            data["claim_candidates"][0]["review_status"] = "accepted"
            data["claim_candidates"][0]["review_notes"] = "verified in context"
            academic.write_text(json.dumps(data), encoding="utf-8")

            write_candidates(course, scan_course(course))
            data = json.loads(academic.read_text(encoding="utf-8"))
            self.assertEqual(len(data["claim_candidates"]), 1)
            self.assertEqual(data["claim_candidates"][0]["review_status"], "accepted")
            self.assertEqual(data["claim_candidates"][0]["review_notes"], "verified in context")

    def test_full_scan_removes_generated_candidates_for_deleted_source(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            transcript = course / "fuentes" / "transcripciones" / "clase.txt"
            transcript.write_text("Unidad 2 entra en el parcial.\n", encoding="utf-8")
            write_candidates(course, scan_course(course))
            transcript.unlink()
            write_candidates(course, scan_course(course))
            data = json.loads((course / "academico" / "academic.json").read_text(encoding="utf-8"))
            self.assertEqual(data["claim_candidates"], [])

    def test_change_signal_never_declares_supersession(self):
        rows = extract_candidates_from_text(
            "Finalmente el parcial va a ser escrito.",
            source="transcripciones/clase.txt",
            source_type="teacher_transcript",
            locator={"segment": 1},
        )
        row = next(item for item in rows if item["kind"] == "change-signal")
        self.assertFalse(row["semantic_ready"])
        self.assertNotIn("supersedes", row)
        self.assertEqual(row["hints"]["change_signal"], True)

    def test_pdf_candidate_keeps_page_locator_when_pymupdf_is_available(self):
        try:
            import fitz
        except Exception:
            self.skipTest("PyMuPDF not installed")

        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            pdf = course / "fuentes" / "oficiales" / "unidad.pdf"
            doc = fitz.open()
            try:
                page = doc.new_page()
                page.insert_text((72, 72), "Una pila se define como una estructura LIFO.")
                doc.save(pdf)
            finally:
                doc.close()

            result = scan_course(course)
            row = next(item for item in result["candidates"] if item["kind"] == "definition")
            self.assertEqual(row["locator"]["page"], 1)
            self.assertEqual(row["source_type_suggestion"], "official_course_material")
            self.assertEqual(row["evidence_ref"], "oficiales/unidad.pdf#page=1")


if __name__ == "__main__":
    unittest.main()
