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
            self.assertEqual(report["version"], 2)
            self.assertEqual(dest_md.read_bytes(), source_md.read_bytes())
            self.assertEqual(dest_html.read_bytes(), source_html.read_bytes())
            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(saved["ok"])
            self.assertEqual({row["role"] for row in saved["files"]}, {"markdown", "html"})
            for row in saved["files"]:
                self.assertEqual(row["source_sha256"], row["destination_sha256"])
                self.assertEqual(row["resource_rewrites"], [])

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

    def test_publish_rebases_run_relative_images_to_final_markdown_and_html_locations(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            unit = Path(td) / "unidad-3"
            run = unit / ".study" / "runs" / "run-1"
            asset = unit / "assets" / "figures" / "u3-diagrama.png"
            source_md = run / "06-final.md"
            source_html = run / "09-rendered.html"
            dest_md = unit / "resumenes" / "_source" / "unidad-3-resumen.md"
            dest_html = unit / "resumenes" / "unidad-3-resumen.html"
            report_path = run / "11-publication.json"

            run.mkdir(parents=True)
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"fake-png")
            source_md.write_text(
                '# U3\n\n![Diagrama](../../../assets/figures/u3-diagrama.png "Figura")\n',
                encoding="utf-8",
            )
            source_html.write_text(
                '<html><body><img src="../../../assets/figures/u3-diagrama.png" alt="Diagrama"></body></html>',
                encoding="utf-8",
            )

            report = publish_pair(source_md, source_html, dest_md, dest_html, report_path)

            self.assertTrue(report["ok"])
            self.assertIn('../../assets/figures/u3-diagrama.png', dest_md.read_text(encoding="utf-8"))
            self.assertIn('../assets/figures/u3-diagrama.png', dest_html.read_text(encoding="utf-8"))
            self.assertEqual(source_md.read_bytes(), dest_md.read_bytes())
            self.assertEqual(source_html.read_bytes(), dest_html.read_bytes())
            self.assertTrue((dest_md.parent / "../../assets/figures/u3-diagrama.png").resolve().is_file())
            self.assertTrue((dest_html.parent / "../assets/figures/u3-diagrama.png").resolve().is_file())
            by_role = {row["role"]: row for row in report["files"]}
            self.assertEqual(by_role["markdown"]["resource_rewrites"][0]["original"], "../../../assets/figures/u3-diagrama.png")
            self.assertEqual(by_role["markdown"]["resource_rewrites"][0]["published"], "../../assets/figures/u3-diagrama.png")
            self.assertEqual(by_role["html"]["resource_rewrites"][0]["published"], "../assets/figures/u3-diagrama.png")
            self.assertNotEqual(by_role["html"]["pre_rebase_source_sha256"], by_role["html"]["source_sha256"])

    def test_missing_local_resource_aborts_without_overwriting_existing_publication(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            unit = Path(td) / "unidad-3"
            run = unit / ".study" / "runs" / "run-1"
            source_md = run / "06-final.md"
            source_html = run / "09-rendered.html"
            dest_md = unit / "resumenes" / "_source" / "unidad-3-resumen.md"
            dest_html = unit / "resumenes" / "unidad-3-resumen.html"
            report_path = run / "11-publication.json"

            run.mkdir(parents=True)
            dest_md.parent.mkdir(parents=True)
            dest_html.parent.mkdir(parents=True, exist_ok=True)
            source_md.write_text("![Rota](../../../assets/figures/no-existe.png)\n", encoding="utf-8")
            source_html.write_text('<img src="../../../assets/figures/no-existe.png">', encoding="utf-8")
            dest_md.write_text("old-md", encoding="utf-8")
            dest_html.write_text("old-html", encoding="utf-8")

            with self.assertRaisesRegex(OSError, "publication-resource-missing"):
                publish_pair(source_md, source_html, dest_md, dest_html, report_path)

            self.assertEqual(dest_md.read_text(encoding="utf-8"), "old-md")
            self.assertEqual(dest_html.read_text(encoding="utf-8"), "old-html")
            self.assertFalse(report_path.exists())


if __name__ == "__main__":
    unittest.main()
