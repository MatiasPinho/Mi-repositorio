from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from scripts import artifact_integrity, code_highlight_v2, scene_figure, scene_pencil, scene_preflight, visual_review
from tests.test_scene_v2 import free_scene


class FirstRealRunRegressionTests(unittest.TestCase):
    def test_semantic_empty_shape_is_a_hard_preflight_failure(self):
        scene = free_scene()
        scene["elements"][1].pop("label")
        report = scene_preflight.preflight_scene(scene)
        self.assertFalse(report["ok"])
        self.assertTrue(any(issue["code"] == "empty-semantic-shape" for issue in report["issues"]))

    def test_long_pencil_edge_is_subdivided_not_ruler_straight(self):
        first = scene_pencil.rough_polyline(
            [(0.0, 0.0), (620.0, 0.0)], "seed", "edge",
            jitter_scale=1.65, bend_scale=2.85,
        )
        second = scene_pencil.rough_polyline(
            [(0.0, 0.0), (620.0, 0.0)], "seed", "edge",
            jitter_scale=1.65, bend_scale=2.85,
        )
        self.assertEqual(first, second)
        self.assertGreaterEqual(first.count(" Q "), 10, first)

    def test_review_issue_shape_matches_schema_contract_exactly(self):
        scores = {key: 5 for key in visual_review.SCORE_KEYS}
        review = {
            "version": 1,
            "vision_verified": True,
            "reviewer": {"id": "vision", "capability": "vision", "independent": True},
            "figures": [{
                "scene_id": "s",
                "attempt": 1,
                "status": "pass",
                "inspected": [
                    {"variant": "wide", "file": "wide.png", "sha256": "a" * 64},
                    {"variant": "narrow", "file": "narrow.png", "sha256": "b" * 64},
                ],
                "scores": scores,
                "issues": [{
                    "severity": "minor",
                    "type": "spacing",
                    "elements": ["a"],
                    "problem": "tight",
                    "repair": "add space",
                }],
            }],
        }
        self.assertEqual(visual_review.validate_review(review)["figures"][0]["issues"][0]["type"], "spacing")
        broken = json.loads(json.dumps(review))
        del broken["figures"][0]["issues"][0]["elements"]
        with self.assertRaises(visual_review.VisualReviewError):
            visual_review.validate_review(broken)

    def test_java_basic_and_prolog_receive_static_syntax_colour(self):
        source = (
            '<pre><code class="language-java">public class A { int n = 2; }</code></pre>'
            '<pre><code class="language-basic">10 PRINT "HOLA"\n20 GOTO 10</code></pre>'
            '<pre><code class="language-prolog">padre(juan, maria).\nabuelo(X,Z) :- padre(X,Y), padre(Y,Z).</code></pre>'
        )
        rendered, report = code_highlight_v2.transform(source)
        self.assertEqual(report["highlighted_blocks"], 3)
        self.assertEqual(report["unsupported_languages"], [])
        self.assertEqual(rendered.count("syntax-highlighted"), 3)
        self.assertIn("syntax-keyword", rendered)
        self.assertIn("syntax-number", rendered)

    def test_identical_scene_preview_reuses_attempt_and_png_hashes(self):
        slug = "zz-v2-reuse-" + uuid.uuid4().hex[:8]
        course = ROOT / "materias" / slug
        try:
            for rel in ("academico", "conocimiento", "assets/figures", ".study/runs/run-1"):
                (course / rel).mkdir(parents=True, exist_ok=True)
            (course / "academico" / "academic.json").write_text(
                json.dumps({"identity": {"subject": "Reuse"}, "units": [{"id": "U1", "name": "Unidad 1"}]}),
                encoding="utf-8",
            )
            (course / "conocimiento" / "figures.json").write_text(json.dumps({"version": 2, "figures": {}}), encoding="utf-8")
            (course / "conocimiento" / "concepts.json").write_text(json.dumps({"version": 2, "concepts": {}}), encoding="utf-8")
            run = course / ".study" / "runs" / "run-1"

            def fake_shot(_svg: bytes, path: Path, *, variant: str) -> None:
                path.write_bytes(("png:" + variant).encode())

            with mock.patch.object(scene_figure, "_screenshot_svg", side_effect=fake_shot):
                first = scene_figure.preview_scene(course, "U1", free_scene("reuse-scene"), run)
                second = scene_figure.preview_scene(course, "U1", free_scene("reuse-scene"), run)
            self.assertEqual(first["attempt"], 1)
            self.assertEqual(second["attempt"], 1)
            self.assertTrue(second["reused"])
            self.assertEqual(first["variants"]["wide"]["png_sha256"], second["variants"]["wide"]["png_sha256"])
            attempts = list((run / "02-visual-attempts" / "reuse-scene").glob("[0-9][0-9]"))
            self.assertEqual(len(attempts), 1)
        finally:
            shutil.rmtree(course, ignore_errors=True)

    def test_legacy_integrity_distinguishes_auto_discovery_from_explicit_none(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            md = root / "06-final.md"
            rendered = root / "09-rendered.html"
            (root / "02-plan.json").write_text("{}", encoding="utf-8")
            md.write_text("texto", encoding="utf-8")
            rendered.write_text("<html><body>texto</body></html>", encoding="utf-8")
            patches = (
                mock.patch.object(artifact_integrity, "validate_images", return_value=[]),
                mock.patch.object(artifact_integrity, "validate_caption_comments", return_value=[]),
                mock.patch.object(artifact_integrity, "html_image_issues", return_value=[]),
                mock.patch.object(artifact_integrity, "load_registry", return_value={"figures": {}}),
                mock.patch.object(artifact_integrity, "registry_issues", return_value=[]),
                mock.patch.object(artifact_integrity, "resolve_unit", return_value={"unit_id": "U1"}),
                mock.patch.object(artifact_integrity, "has_unit_layout", return_value=False),
                mock.patch.object(artifact_integrity, "artifact_usage_issues", return_value=([], 7)),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
                auto = artifact_integrity.check(root, md, rendered, "U1", "summary")
                explicit_none = artifact_integrity.check(root, md, rendered, "U1", "summary", None)
            self.assertTrue(auto["visual_plan_checked"])
            self.assertEqual(auto["planned_visual_count"], 7)
            self.assertFalse(explicit_none["visual_plan_checked"])
            self.assertEqual(explicit_none["planned_visual_count"], 0)


if __name__ == "__main__":
    unittest.main()
