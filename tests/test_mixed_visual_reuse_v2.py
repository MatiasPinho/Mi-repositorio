from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import visual_plan_v2, visual_reuse_v2


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MixedVisualReuseV2Tests(unittest.TestCase):
    def test_registered_legacy_derived_can_be_reused_without_scene_spec(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td)
            figures_dir = course / "assets" / "figures"
            figures_dir.mkdir(parents=True)
            asset = figures_dir / "legacy-one.svg"
            spec = figures_dir / "legacy-one.sketch.json"
            asset.write_text("<svg>legacy</svg>", encoding="utf-8")
            spec.write_text(json.dumps({"id": "legacy-one"}), encoding="utf-8")

            plan = course / "02-plan.json"
            plan.write_text(json.dumps({
                "visuals": [{
                    "concept_id": "concept:c",
                    "need": "visual_helpful",
                    "visual_treatment": "preserve+derived_sketch",
                    "reason": "Existing companion remains pedagogically useful",
                    "fidelity_reason": "Source pixels must remain available beside the sketch",
                    "source_figure_id": "source:one",
                    "derived_figure_id": "derived:legacy-one",
                    "based_on": ["concept:c"],
                }]
            }), encoding="utf-8")

            registry = {"figures": {
                "source:one": {
                    "origin": "source",
                    "unit_id": "unidad-1",
                    "asset": "assets/figures/source-one.png",
                },
                "derived:legacy-one": {
                    "origin": "derived",
                    "unit_id": "unidad-1",
                    "asset": "assets/figures/legacy-one.svg",
                    "asset_sha256": sha(asset),
                    "visual_treatment": "preserve+derived_sketch",
                    "source_figure_id": "source:one",
                    "based_on": ["concept:c"],
                    "generation": {
                        "method": "deterministic-svg",
                        "spec": "assets/figures/legacy-one.sketch.json",
                        "spec_sha256": sha(spec),
                    },
                },
            }}

            with mock.patch.object(visual_plan_v2, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_v2, "load_registry", return_value=registry), \
                 mock.patch.object(visual_plan_v2, "record_unit_id", return_value="unidad-1"), \
                 mock.patch.object(visual_plan_v2, "has_unit_layout", return_value=False):
                rows = visual_plan_v2.inspect_plan(course, "unidad-1", plan)

            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["reuse_registered"])
            self.assertEqual(rows[0]["reuse_kind"], "legacy")
            self.assertEqual(rows[0]["derived_figure_id"], "derived:legacy-one")
            self.assertNotIn("scene_spec", rows[0])

    def test_registered_v2_without_current_scene_spec_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td)
            figures_dir = course / "assets" / "figures"
            figures_dir.mkdir(parents=True)
            source_asset = figures_dir / "source-one.png"
            derived_asset = figures_dir / "v2-one.svg"
            source_asset.write_bytes(b"source")
            derived_asset.write_text("<svg>v2</svg>", encoding="utf-8")

            plan = course / "02-plan.json"
            plan.write_text(json.dumps({
                "visuals": [{
                    "concept_id": "concept:c",
                    "need": "visual_helpful",
                    "visual_treatment": "preserve+derived_sketch",
                    "reason": "Reuse a previously reviewed V2 companion",
                    "fidelity_reason": "Keep the source beside the derived explanation",
                    "source_figure_id": "source:one",
                    "derived_figure_id": "derived:v2-one",
                    "based_on": ["concept:c"],
                }]
            }), encoding="utf-8")

            registry = {"figures": {
                "source:one": {
                    "origin": "source",
                    "unit_id": "unidad-1",
                    "asset": "assets/figures/source-one.png",
                },
                "derived:v2-one": {
                    "origin": "derived",
                    "unit_id": "unidad-1",
                    "asset": "assets/figures/v2-one.svg",
                    "asset_sha256": sha(derived_asset),
                    "visual_treatment": "preserve+derived_sketch",
                    "source_figure_id": "source:one",
                    "based_on": ["concept:c"],
                    "scene_generation": {
                        "schema_version": 2,
                        "method": "deterministic-scene-svg",
                    },
                },
            }}

            with mock.patch.object(visual_plan_v2, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_v2, "load_registry", return_value=registry), \
                 mock.patch.object(visual_plan_v2, "record_unit_id", return_value="unidad-1"), \
                 mock.patch.object(visual_plan_v2, "has_unit_layout", return_value=False):
                with self.assertRaisesRegex(visual_plan_v2.VisualPlanV2Error, "scene_spec required for registered V2 reuse"):
                    visual_plan_v2.inspect_plan(course, "unidad-1", plan)

    def test_preview_only_renders_current_scene_not_registered_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td)
            plan = course / "02-plan.json"
            plan.write_text("{}", encoding="utf-8")
            rows = [
                {
                    "concept_id": "legacy",
                    "visual_treatment": "preserve+derived_sketch",
                    "source_figure_id": "source:one",
                    "derived_figure_id": "derived:legacy-one",
                    "registered_asset": "assets/figures/legacy-one.svg",
                    "registered_asset_sha256": "a" * 64,
                    "reuse_registered": True,
                    "reuse_kind": "legacy",
                },
                {
                    "concept_id": "new",
                    "visual_treatment": "reinterpret",
                    "derived_figure_id": "derived:new-one",
                    "scene": {"id": "new-one"},
                    "reuse_registered": False,
                },
            ]
            preview_entry = {"ok": True, "scene_id": "new-one"}
            with mock.patch.object(visual_plan_v2, "inspect_plan", return_value=rows), \
                 mock.patch.object(visual_plan_v2.scene_figure, "preview_scene", return_value=preview_entry) as preview_scene:
                report = visual_plan_v2.preview_plan(course, "unidad-1", plan)

            preview_scene.assert_called_once()
            self.assertEqual(report["entries"], [preview_entry])
            self.assertEqual(len(report["reused_registered"]), 1)
            self.assertEqual(report["reused_registered"][0]["derived_figure_id"], "derived:legacy-one")

    def test_cross_run_cache_ignores_registered_legacy_rows(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td)
            current = course / ".study" / "runs" / "current"
            current.mkdir(parents=True)
            plan = current / "02-plan.json"
            plan.write_text("{}", encoding="utf-8")
            legacy = {
                "concept_id": "legacy",
                "visual_treatment": "preserve+derived_sketch",
                "derived_figure_id": "derived:legacy-one",
                "reuse_registered": True,
                "reuse_kind": "legacy",
            }
            with mock.patch.object(visual_reuse_v2.visual_plan_v2, "inspect_plan", return_value=[legacy]), \
                 mock.patch.object(visual_reuse_v2, "resolve_unit", return_value={"unit_id": "unidad-1"}):
                report = visual_reuse_v2.prepare(
                    course,
                    "unidad-1",
                    plan,
                    current / "02-visual-review.json",
                )

            self.assertTrue(report["ok"])
            self.assertFalse(report["all_reused"])
            self.assertEqual(report["reason"], "no-current-v2-scenes")
            self.assertEqual(report["registered_reuse_ids"], ["derived:legacy-one"])


if __name__ == "__main__":
    unittest.main()
