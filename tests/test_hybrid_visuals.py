from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import illustration_figure, render_study, visual_plan_hybrid


def illustration_spec() -> dict:
    return {
        "schema_version": 1,
        "id": "cpu-chip",
        "subject": "generic computer microprocessor package",
        "view": "top-down",
        "must_show": ["square integrated-circuit package", "visible pins around the package"],
        "alt": "Dibujo a lápiz de un microprocesador visto desde arriba.",
        "caption": "Representación física simplificada de un microprocesador.",
        "based_on": ["concept:cpu"],
    }


def illustration_plan(need: str = "visual_helpful") -> dict:
    return {
        "visuals": [{
            "concept_id": "cpu",
            "need": need,
            "visual_treatment": "reinterpret",
            "visual_medium": "illustration",
            "derived_figure_id": "derived:cpu-chip",
            "based_on": ["concept:cpu"],
            "reason": "Physical recognition helps connect the term to hardware.",
            "illustration": illustration_spec(),
        }]
    }


class IllustrationContractTests(unittest.TestCase):
    def test_prompt_is_style_locked_and_forbids_textual_semantics(self):
        prompt = illustration_figure.build_prompt(illustration_spec())
        for phrase in (
            "pencil sketch",
            "Plain white background",
            "No text",
            "labels",
            "arrows",
            "Do not invent internal technical details",
        ):
            self.assertIn(phrase, prompt)

    def test_spec_rejects_unknown_freeform_prompt_field(self):
        spec = illustration_spec()
        spec["prompt"] = "draw whatever you want"
        with self.assertRaises(illustration_figure.IllustrationError):
            illustration_figure.validate_spec(spec)

    def test_generated_white_canvas_becomes_transparent_notebook_overlay(self):
        try:
            from PIL import Image, ImageDraw
        except Exception as exc:  # pragma: no cover - setup failure should be explicit
            self.fail(f"Pillow unavailable: {exc}")
        image = Image.new("RGB", (400, 300), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((120, 80, 280, 220), fill=(80, 80, 80))
        raw = io.BytesIO()
        image.save(raw, "PNG")
        svg, meta = illustration_figure._prepare_overlay(raw.getvalue(), "CPU")
        text = svg.decode("utf-8")
        self.assertIn('data-study-sketch="1"', text)
        self.assertIn('data-transparent-canvas="1"', text)
        self.assertIn('data-generated-illustration="1"', text)
        self.assertIn("data:image/png;base64,", text)
        self.assertLess(meta["output_size"][0], 400)
        self.assertLess(meta["output_size"][1], 300)
        self.assertTrue(meta["transparent_overlay"])

    def test_renderer_recognizes_generated_overlay_as_unframed_figure(self):
        try:
            from PIL import Image, ImageDraw
        except Exception as exc:  # pragma: no cover
            self.fail(f"Pillow unavailable: {exc}")
        image = Image.new("RGB", (120, 100), "white")
        ImageDraw.Draw(image).ellipse((30, 20, 90, 80), fill=(60, 60, 60))
        raw = io.BytesIO()
        image.save(raw, "PNG")
        svg, _meta = illustration_figure._prepare_overlay(raw.getvalue(), "object")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            asset = base / "x.illustration.svg"
            asset.write_bytes(svg)
            self.assertTrue(render_study.is_study_sketch(asset.name, base))


class HybridPlanTests(unittest.TestCase):
    def _inspect(self, payload: dict):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / "02-plan.json"
            plan.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                return visual_plan_hybrid.inspect_plan(Path(td), "unidad-1", plan)

    def test_illustration_is_valid_only_as_visual_helpful(self):
        rows = self._inspect(illustration_plan())
        self.assertEqual(rows[0]["visual_medium"], "illustration")
        self.assertEqual(rows[0]["figure_kind"], "illustration")

        with self.assertRaises(visual_plan_hybrid.VisualPlanError):
            self._inspect(illustration_plan("visual_required"))

    def test_missing_medium_remains_backward_compatible_diagram(self):
        payload = illustration_plan()
        row = payload["visuals"][0]
        row.pop("visual_medium")
        row.pop("illustration")
        row["sketch_spec"] = "02-sketches/cpu-chip.json"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "02-sketches").mkdir()
            spec = {
                "schema_version": 1,
                "id": "cpu-chip",
                "title": "CPU",
                "kind": "technical-schematic",
                "visual_treatment": "reinterpret",
                "description": "CPU conceptual block.",
                "alt": "CPU conceptual block.",
                "caption": "CPU conceptual block.",
                "based_on": ["concept:cpu"],
                "nodes": [{"id": "cpu", "label": "CPU", "based_on": ["concept:cpu"]}],
                "edges": [],
            }
            (root / "02-sketches" / "cpu-chip.json").write_text(json.dumps(spec), encoding="utf-8")
            plan = root / "02-plan.json"
            plan.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                rows = visual_plan_hybrid.inspect_plan(root, "unidad-1", plan)
        self.assertEqual(rows[0]["visual_medium"], "diagram")

    def test_provider_unavailable_is_reported_without_retry_loop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = root / "02-plan.json"
            plan.write_text(json.dumps(illustration_plan()), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}), \
                 mock.patch.object(
                     visual_plan_hybrid,
                     "generate_illustration",
                     side_effect=illustration_figure.IllustrationUnavailable("capacity"),
                 ) as generate:
                report = visual_plan_hybrid.materialize_plan(root, "unidad-1", plan)
            self.assertFalse(report["ok"])
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(report["illustration_unavailable"][0]["concept_id"], "cpu")


class HybridPipelineContractTests(unittest.TestCase):
    def test_summary_uses_hybrid_materializer_without_v2_scene_review_pipeline(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        self.assertIn("visual_plan_hybrid.py", text)
        self.assertIn("scripts/visual_plan.py", text)
        self.assertIn("one bounded provider call", text)
        self.assertIn("There is no independent per-illustration vision-review loop", text)
        self.assertNotIn("visual_plan_v2.py", text)
        self.assertNotIn("02-visual-review.json", text)

    def test_hybrid_policy_keeps_exact_semantics_out_of_generated_pixels(self):
        root = Path(__file__).resolve().parents[1]
        rules = (root / "rules" / "visual" / "figures.md").read_text(encoding="utf-8")
        self.assertIn("visual_medium: diagram", rules)
        self.assertIn("visual_medium: illustration", rules)
        self.assertIn("never `visual_required`", rules)
        self.assertIn("never generate the whole study page as an image", rules)


if __name__ == "__main__":
    unittest.main()
