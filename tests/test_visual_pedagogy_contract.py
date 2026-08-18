from __future__ import annotations

import unittest
from pathlib import Path

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

        self.assertIn("the drawing itself carries explanatory work", rubric)
        self.assertIn("score `pedagogical_value <= 3`", rubric)
        self.assertIn("Do **not** penalize boxes merely for being boxes", rubric)
        self.assertIn("Never demand extra visual detail that is not supported by provenance", rubric)

        self.assertIn("rules/visual/figures.md", pipeline)
        self.assertIn("rules/evaluation/visual-rubric.md", pipeline)


if __name__ == "__main__":
    unittest.main()
