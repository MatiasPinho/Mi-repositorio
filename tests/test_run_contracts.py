from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from scripts.pipeline_run import _validate_canonical_snapshot, _validate_publication, sha
from scripts.publish_artifact import publish_pair


class RunContractTests(unittest.TestCase):
    def test_canonical_snapshot_detects_each_changed_input(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            run = root / "run"
            run.mkdir()
            paths = {
                "academic": root / "academic.json",
                "concepts": root / "concepts.json",
                "topics": root / "topics.json",
                "figures": root / "figures.json",
            }
            for label, path in paths.items():
                path.write_text(json.dumps({"kind": label, "version": 1}), encoding="utf-8")
            payload = {
                "academic_file": paths["academic"].relative_to(ROOT).as_posix(),
                "academic_sha256": sha(paths["academic"]),
                "concepts_file": paths["concepts"].relative_to(ROOT).as_posix(),
                "concepts_sha256": sha(paths["concepts"]),
                "topics_file": paths["topics"].relative_to(ROOT).as_posix(),
                "topics_sha256": sha(paths["topics"]),
                "figures_file": paths["figures"].relative_to(ROOT).as_posix(),
                "figures_sha256": sha(paths["figures"]),
            }
            (run / "01-input.json").write_text(json.dumps(payload), encoding="utf-8")

            errors: list[str] = []
            _validate_canonical_snapshot(run, errors)
            self.assertEqual(errors, [])

            for label, path in paths.items():
                original = path.read_bytes()
                path.write_text(json.dumps({"kind": label, "version": 2}), encoding="utf-8")
                errors = []
                _validate_canonical_snapshot(run, errors)
                self.assertEqual(errors, [f"canonical-changed:{label}"])
                path.write_bytes(original)

    def test_publication_v3_binds_immutable_source_to_transformed_destination(self):
        slug = "zz-run-contract-" + uuid.uuid4().hex[:8]
        course = ROOT / "materias" / slug
        try:
            run = course / ".study" / "runs" / "run-1"
            source_md = run / "06-final.md"
            source_html = run / "09-rendered.html"
            dest_md = course / "resumenes" / "_source" / "unidad-1-resumen.md"
            dest_html = course / "resumenes" / "unidad-1-resumen.html"
            report = run / "11-publication.json"
            asset = course / "assets" / "figures" / "figure.png"
            run.mkdir(parents=True)
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"png")
            source_md.write_text("![Figura](../../../assets/figures/figure.png)\n", encoding="utf-8")
            source_html.write_text('<img src="../../../assets/figures/figure.png">', encoding="utf-8")
            source_md_before = source_md.read_bytes()
            source_html_before = source_html.read_bytes()

            publication = publish_pair(source_md, source_html, dest_md, dest_html, report)
            self.assertEqual(publication["version"], 3)
            self.assertEqual(source_md.read_bytes(), source_md_before)
            self.assertEqual(source_html.read_bytes(), source_html_before)

            manifest = {"course": course.relative_to(ROOT).as_posix()}
            errors: list[str] = []
            _validate_publication(run, manifest, errors)
            self.assertEqual(errors, [])

            source_md.write_text(source_md.read_text(encoding="utf-8") + "mutated\n", encoding="utf-8")
            errors = []
            _validate_publication(run, manifest, errors)
            self.assertIn("publication-source-mutated:markdown", errors)
        finally:
            shutil.rmtree(course, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
