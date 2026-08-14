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
                if label == "figures":
                    self.assertIn("canonical-changed:figures", errors)
                    self.assertIn("missing-01-figures.json", errors)
                else:
                    self.assertEqual(errors, [f"canonical-changed:{label}"])
                path.write_bytes(original)

    def test_publication_v3_binds_immutable_source_to_transformed_destination(self):
        slug = "zz-run-contract-" + uuid.uuid4().hex[:8]
        course = ROOT / "materias" / slug
        try:
            run = course / ".study" / "runs" / "run-1"
            # Without a 05-review.json fixture, pipeline_run correctly resolves the
            # repair-path accepted candidate as 08-final.md. This test isolates
            # publication semantics rather than synthesizing an academic review.
            source_md = run / "08-final.md"
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

    def test_figure_snapshot_allows_only_append_only_planned_derived_records(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            run = root / "run"
            run.mkdir()
            academic = root / "academic.json"
            concepts = root / "concepts.json"
            topics = root / "topics.json"
            figures = root / "figures.json"
            for path in (academic, concepts, topics):
                path.write_text(json.dumps({"version": 1}), encoding="utf-8")
            initial = {
                "version": 2,
                "figures": {
                    "source-flow": {
                        "id": "source-flow",
                        "origin": "source",
                        "asset": "assets/figures/source-flow.png",
                    }
                },
            }
            figures.write_text(json.dumps(initial), encoding="utf-8")
            (run / "01-figures.json").write_bytes(figures.read_bytes())
            (run / "01-input.json").write_text(json.dumps({
                "academic_file": academic.relative_to(ROOT).as_posix(),
                "academic_sha256": sha(academic),
                "concepts_file": concepts.relative_to(ROOT).as_posix(),
                "concepts_sha256": sha(concepts),
                "topics_file": topics.relative_to(ROOT).as_posix(),
                "topics_sha256": sha(topics),
                "figures_file": figures.relative_to(ROOT).as_posix(),
                "figures_sha256": sha(figures),
            }), encoding="utf-8")
            plan = run / "02-plan.json"
            plan.write_text(json.dumps({
                "visuals": [{
                    "concept_id": "flow",
                    "need": "visual_required",
                    "visual_treatment": "reinterpret",
                    "derived_figure_id": "derived:flow",
                }]
            }), encoding="utf-8")
            (run / "02-visual-build.json").write_text(json.dumps({
                "ok": True,
                "plan_sha256": sha(plan),
                "entries": [{
                    "visual_treatment": "reinterpret",
                    "derived_figure_id": "derived:flow",
                }],
            }), encoding="utf-8")

            after = json.loads(json.dumps(initial))
            after["figures"]["derived:flow"] = {
                "id": "derived:flow",
                "origin": "derived",
                "visual_treatment": "reinterpret",
                "asset": "assets/figures/flow.svg",
            }
            figures.write_text(json.dumps(after), encoding="utf-8")
            errors: list[str] = []
            _validate_canonical_snapshot(run, errors)
            self.assertEqual(errors, [])

            after["figures"]["source-flow"]["asset"] = "assets/figures/changed.png"
            figures.write_text(json.dumps(after), encoding="utf-8")
            errors = []
            _validate_canonical_snapshot(run, errors)
            self.assertIn("canonical-figure-modified:source-flow", errors)


if __name__ == "__main__":
    unittest.main()
