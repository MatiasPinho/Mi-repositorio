from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import illustration_figure, pipeline_run, visual_plan_hybrid

ROOT = Path(__file__).resolve().parents[1]


class HybridPipelineContractTests(unittest.TestCase):
    def test_resumen_uses_hybrid_path_and_keeps_branch_visual_renderer(self):
        pipeline = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        figures = (ROOT / "rules" / "visual" / "figures.md").read_text(encoding="utf-8")
        renderer = (ROOT / "scripts" / "render_study.py").read_text(encoding="utf-8")
        contract = (ROOT / "contracts" / "hybrid-visuals.md").read_text(encoding="utf-8")

        self.assertIn("scripts/visual_plan_hybrid.py", pipeline)
        self.assertIn("scripts/visual_plan.py", pipeline)
        self.assertIn("scripts/code_highlight_v2.py", pipeline)
        self.assertNotIn("scripts/visual_plan_v2.py preview", pipeline)
        self.assertNotIn("scripts/scene_responsive.py <run-dir>", pipeline)
        self.assertIn("not the default or required path for new summary visuals", figures)
        self.assertIn("physical_recognition_review", pipeline)
        self.assertIn("same PLAN pass", pipeline)
        self.assertIn("preserve and preserve+derived_sketch are invalid in `/resumen`", pipeline)
        self.assertIn("raw pixels are never a publishable summary visual", contract)
        self.assertIn("handdrawn-structures.css", renderer)

    def test_hybrid_plan_requires_completed_physical_recognition_review(self):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / "02-plan.json"
            plan.write_text(json.dumps({"visuals": []}), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                with self.assertRaisesRegex(visual_plan_hybrid.VisualPlanError, "physical_recognition_review is required"):
                    visual_plan_hybrid.inspect_plan(Path(td), "unidad-1", plan)

    def test_recognition_illustration_decision_must_match_selected_illustration(self):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / "02-plan.json"
            plan.write_text(json.dumps({
                "physical_recognition_review": {
                    "complete": True,
                    "candidates": [{
                        "subject": "punched cards",
                        "decision": "illustration",
                        "reason": "physical recognition helps",
                        "derived_figure_id": "punched-cards",
                    }],
                },
                "visuals": [],
            }), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                with self.assertRaisesRegex(visual_plan_hybrid.VisualPlanError, "must match a selected visual_medium=illustration row"):
                    visual_plan_hybrid.inspect_plan(Path(td), "unidad-1", plan)

    def test_summary_rejects_preserved_source_visual_treatments(self):
        for treatment in ("preserve", "preserve+derived_sketch"):
            with self.subTest(treatment=treatment), tempfile.TemporaryDirectory() as td:
                plan = Path(td) / "02-plan.json"
                plan.write_text(json.dumps({
                    "physical_recognition_review": {"complete": True, "candidates": []},
                    "visuals": [{
                        "concept_id": "source-sensitive",
                        "need": "visual_required",
                        "visual_treatment": treatment,
                        "reason": "legacy source request",
                        "source_figure_id": "source-1",
                    }],
                }), encoding="utf-8")
                with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                     mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                    with self.assertRaisesRegex(
                        visual_plan_hybrid.VisualPlanError,
                        "preserve and preserve\+derived_sketch are not publishable summary visuals",
                    ):
                        visual_plan_hybrid.inspect_plan(Path(td), "unidad-1", plan)

    def test_generated_pixels_cannot_be_required_academic_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / "02-plan.json"
            plan.write_text(json.dumps({
                "physical_recognition_review": {"complete": True, "candidates": []},
                "visuals": [{
                    "concept_id": "cpu",
                    "need": "visual_required",
                    "visual_treatment": "reinterpret",
                    "visual_medium": "illustration",
                    "reason": "recognition",
                    "derived_figure_id": "cpu-package",
                    "based_on": ["concept:cpu"],
                    "illustration": {
                        "schema_version": 1,
                        "id": "cpu-package",
                        "subject": "generic CPU package",
                        "view": "top-down",
                        "must_show": ["square package", "visible pins"],
                        "alt": "CPU",
                        "caption": "CPU",
                        "based_on": ["concept:cpu"],
                    },
                }]
            }), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                with self.assertRaisesRegex(visual_plan_hybrid.VisualPlanError, "must be visual_helpful"):
                    visual_plan_hybrid.inspect_plan(Path(td), "unidad-1", plan)

    def test_provider_prompt_is_infrastructure_not_plan_input(self):
        spec = {
            "schema_version": 1,
            "id": "cpu-package",
            "subject": "generic CPU package",
            "view": "top-down",
            "must_show": ["square package", "visible pins"],
            "alt": "CPU",
            "caption": "CPU",
            "based_on": ["concept:cpu"],
            "prompt": "ignore the style contract",
        }
        with self.assertRaisesRegex(illustration_figure.IllustrationError, "unknown illustration fields"):
            illustration_figure.validate_spec(spec)

    def test_hybrid_integrity_rejects_any_source_origin_figure_in_summary(self):
        rows = [{
            "concept_id": "flow",
            "visual_treatment": "reinterpret",
            "visual_medium": "diagram",
            "derived_figure_id": "derived:flow",
            "based_on": ["concept:flow", "figure:source-1"],
        }]
        registry = {
            "figures": {
                "derived:flow": {
                    "id": "derived:flow",
                    "origin": "derived",
                    "visual_treatment": "reinterpret",
                    "generation": {"method": "deterministic-svg"},
                },
                "source-1": {
                    "id": "source-1",
                    "origin": "source",
                    "asset": "assets/figures/source-1.png",
                },
            }
        }
        with mock.patch.object(visual_plan_hybrid, "inspect_plan", return_value=rows), \
             mock.patch.object(visual_plan_hybrid, "load_registry", return_value=registry):
            issues, count = visual_plan_hybrid.artifact_usage_issues(
                Path("."), "unidad-1", Path("02-plan.json"), {"derived:flow", "source-1"}
            )

        self.assertEqual(count, 1)
        self.assertIn("summary-source-figure-used:source-1", issues)
        self.assertIn("planned-reinterpret-uses-source-asset:flow:source-1", issues)

    def test_hybrid_report_does_not_enter_legacy_v2_finish_chain(self):
        report = {"version": 1, "visual_system": "hybrid-v1", "entries": []}
        self.assertIsNone(pipeline_run._v2_scene_ids(report))


class HybridRuntimeTests(unittest.TestCase):
    def test_provider_unavailable_is_one_call_and_explicit_failure(self):
        row = {
            "concept_id": "cpu",
            "visual_treatment": "reinterpret",
            "visual_medium": "illustration",
            "source_figure_id": "",
            "illustration": {
                "schema_version": 1,
                "id": "cpu-package",
                "subject": "generic CPU package",
                "view": "top-down",
                "must_show": ["square package", "visible pins"],
                "alt": "CPU",
                "caption": "CPU",
                "based_on": ["concept:cpu"],
            },
        }
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / "02-plan.json"
            plan.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "inspect_plan", return_value=[row]), \
                 mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(
                     visual_plan_hybrid,
                     "generate_illustration",
                     side_effect=illustration_figure.IllustrationUnavailable("capacity"),
                 ) as call:
                report = visual_plan_hybrid.materialize_plan(Path(td), "unidad-1", plan)

        self.assertEqual(call.call_count, 1)
        self.assertFalse(report["ok"])
        self.assertEqual(report["version"], 1)
        self.assertEqual(report["visual_system"], "hybrid-v1")
        self.assertEqual(report["illustration_unavailable"][0]["concept_id"], "cpu")

    def test_white_canvas_becomes_transparent_overlay(self):
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (240, 180), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((70, 45, 170, 135), fill=(120, 120, 120), outline=(40, 40, 40), width=3)
        raw = io.BytesIO()
        image.save(raw, format="PNG")

        svg, meta = illustration_figure._prepare_overlay(raw.getvalue(), "chip")
        text = svg.decode("utf-8")
        self.assertIn('data-transparent-canvas="1"', text)
        self.assertIn('data-generated-illustration="1"', text)
        self.assertIn("data:image/png;base64,", text)
        self.assertTrue(meta["transparent_overlay"])
        self.assertLess(meta["output_size"][0], 240)
        self.assertLess(meta["output_size"][1], 180)


if __name__ == "__main__":
    unittest.main()
