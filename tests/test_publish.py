from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from scripts.publish_artifact import publish_pair


class AtomicPublicationTests(unittest.TestCase):
    def test_publish_pair_is_byte_exact_and_writes_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            td = Path(td)
            source_md = td / "source.md"
            source_html = td / "source.html"
            dest_md = td / "published" / "_source" / "unit.md"
            dest_html = td / "published" / "unit.html"
            report_path = td / "run" / "11-publication.json"

            source_md.write_bytes("# Resumen\nContenido con ñ y á.\n".encode("utf-8"))
            source_html.write_bytes(("<!doctype html><html><body>" + "contenido" * 5000 + "</body></html>").encode("utf-8"))

            report = publish_pair(source_md, source_html, dest_md, dest_html, report_path)

            self.assertTrue(report["ok"])
            self.assertEqual(dest_md.read_bytes(), source_md.read_bytes())
            self.assertEqual(dest_html.read_bytes(), source_html.read_bytes())
            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(saved["ok"])
            self.assertEqual({row["role"] for row in saved["files"]}, {"markdown", "html"})
            for row in saved["files"]:
                self.assertEqual(row["source_sha256"], row["destination_sha256"])

    def test_republish_replaces_existing_files_without_truncation_or_temp_leaks(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            td = Path(td)
            source_md = td / "source.md"
            source_html = td / "source.html"
            dest_md = td / "published" / "_source" / "unit.md"
            dest_html = td / "published" / "unit.html"
            report_path = td / "run" / "11-publication.json"
            dest_md.parent.mkdir(parents=True, exist_ok=True)
            dest_html.parent.mkdir(parents=True, exist_ok=True)
            dest_md.write_text("old markdown", encoding="utf-8")
            dest_html.write_text("old html", encoding="utf-8")

            expected_md = ("# Nuevo\n" + "línea\n" * 1000).encode("utf-8")
            expected_html = ("<!doctype html><html><head><title>Completo</title></head><body>" + "x" * 250000 + "</body></html>").encode("utf-8")
            source_md.write_bytes(expected_md)
            source_html.write_bytes(expected_html)

            publish_pair(source_md, source_html, dest_md, dest_html, report_path)

            self.assertEqual(dest_md.read_bytes(), expected_md)
            self.assertEqual(dest_html.read_bytes(), expected_html)
            self.assertTrue(dest_html.read_text(encoding="utf-8").endswith("</body></html>"))
            leaked = list((td / "published").rglob(".study-publish-*.tmp"))
            self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
