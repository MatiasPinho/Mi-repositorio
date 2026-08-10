from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT))

from scripts.pdf_probe import probe_pdf, scan_course  # noqa: E402
from scripts.pdf_stress import make_pdf, run_benchmark  # noqa: E402


class PdfStressTests(unittest.TestCase):
    def test_frozen_pdf_benchmark_passes(self):
        result = run_benchmark()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["total"], 10)

    def test_corrupt_pdf_is_reported_without_exception(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "corrupto.pdf"
            make_pdf(path, "corrupt")
            result = probe_pdf(path)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], "unreadable")
            self.assertEqual(result["pages"], 0)

    def test_course_scan_continues_after_corrupt_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td) / "course"
            official = course / "fuentes" / "oficiales"
            official.mkdir(parents=True)
            make_pdf(official / "A — bueno.pdf", "text")
            make_pdf(official / "B — corrupto.pdf", "corrupt")
            result = scan_course(course)
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["healthy"], 1)
            self.assertEqual(result["unreadable"], 1)
            self.assertEqual(result["files"][0]["file"], "oficiales/A — bueno.pdf")
            self.assertEqual(result["files"][1]["file"], "oficiales/B — corrupto.pdf")

    def test_image_only_page_is_flagged_without_ocr(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "scan.pdf"
            make_pdf(path, "image-only")
            result = probe_pdf(path)
            self.assertTrue(result["ok"])
            self.assertEqual(result["image_only_pages"], 1)
            self.assertTrue(result["page_metrics"][0]["likely_scanned"])
            self.assertFalse(result["page_metrics"][0]["has_text_layer"])


if __name__ == "__main__":
    unittest.main()
