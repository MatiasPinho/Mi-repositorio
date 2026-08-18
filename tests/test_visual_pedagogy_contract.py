from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import visual_reuse_v2

ROOT = Path(__file__).resolve().parents[1]


class VisualPedagogyContractTests(unittest.TestCase):
    def test_v2_prefers_graphic_explanation_without_banning_valid_containers(self):
        figures = (ROOT / "rules" / "visual" / "figures.md").read_text(encoding="utf-8")
        rubric = (ROOT / "rules" / "evaluation" / "visual-rubric.md").read_text(encoding="utf-8")
        pipeline = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")

        self.assertIn("## Graphic explanatory density", figures)
        self.assertIn("visual encoding of the idea", figures)
        self.assertIn("do not default mechanically to a symmetric grid of labeled boxes", figures)
        self.assertIn("There is no minimum element count", figures)
        self.assertIn("Graphic richness never permits invented detail", figures)

        self.assertIn("## Representational fit", figures)
        self.assertIn("simplified iconic/schematic sketch", figures)
        self.assertIn("CPU may read as a chip package with pins", figures)
        self.assertIn("not named templates", figures)
        self.assertIn("more explanatory drawing, spatial structure and visual cues", figures)
        self.assertIn("avoid **generic-box substitution**", figures)

        self.assertIn("the drawing itself carries explanatory work", rubric)
        self.assertIn("### Representational fit inside `pedagogical_value`", rubric)
        self.assertIn("plain box labeled `CPU`", rubric)
        self.assertIn("score `pedagogical_value <= 3`", rubric)
        self.assertIn("The repair should improve the drawing/structure, **not add more prose**", rubric)
        self.assertIn("Do **not** penalize boxes merely for being boxes", rubric)
        self.assertIn("Never demand decorative realism, unsupported internals", rubric)

        self.assertIn("rules/visual/figures.md", pipeline)
        self.assertIn("rules/evaluation/visual-rubric.md", pipeline)

    def test_cross_run_visual_pass_is_invalidated_when_visual_policy_changes(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            current = visual_reuse_v2._current_visual_policy()
            (run / "manifest.json").write_text(
                json.dumps({"engine_snapshot": current}),
                encoding="utf-8",
            )
            self.assertTrue(visual_reuse_v2._visual_policy_matches_current(run))

            stale = dict(current)
            stale[visual_reuse_v2.VISUAL_POLICY_FILES[0]] = "0" * 64
            (run / "manifest.json").write_text(
                json.dumps({"engine_snapshot": stale}),
                encoding="utf-8",
            )
            self.assertFalse(visual_reuse_v2._visual_policy_matches_current(run))

    def test_synthetic_run_without_manifest_keeps_fixture_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(visual_reuse_v2._visual_policy_matches_current(Path(td)))


if __name__ == "__main__":
    unittest.main()
