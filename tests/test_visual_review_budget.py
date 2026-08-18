from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import scene_figure, visual_plan_v2

ROOT = Path(__file__).resolve().parents[1]


class VisualReviewBudgetTests(unittest.TestCase):
    def test_third_reviewable_attempt_is_rejected_by_engine(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            root = run / "02-visual-attempts" / "scene-a"
            for slot in (1, 2):
                attempt = root / f"{slot:02d}"
                attempt.mkdir(parents=True)
                (attempt / "preview.json").write_text(
                    json.dumps({"ok": True}),
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(scene_figure.SceneFigureError, "maximum 2 visual attempts exceeded"):
                scene_figure._next_attempt(run, "scene-a")

    def test_pruned_failed_scene_produces_empty_current_preview(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = root / "02-plan.json"
            plan.write_text(
                json.dumps({
                    "visuals": [{
                        "concept_id": "concept-a",
                        "need": "visual_not_needed",
                    }]
                }),
                encoding="utf-8",
            )

            with mock.patch.object(
                visual_plan_v2,
                "resolve_unit",
                return_value={"unit_id": "unidad-1"},
            ), mock.patch.object(
                visual_plan_v2,
                "load_registry",
                return_value={"figures": {}},
            ):
                report = visual_plan_v2.preview_plan(root, "unidad-1", plan)

            self.assertTrue(report["ok"])
            self.assertEqual(report["entries"], [])
            self.assertEqual(report["preserved"], [])
            self.assertEqual(report["reused_registered"], [])

    def test_runtime_contract_prevents_cost_driven_visual_avoidance_and_creator_self_review(self):
        runtime = (ROOT / "pipelines" / "_shared" / "summary-runtime-optimization.md").read_text(encoding="utf-8")
        pipeline = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        figures = (ROOT / "rules" / "visual" / "figures.md").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "visual-system-v2.md").read_text(encoding="utf-8")

        self.assertIn("summary-runtime-optimization.md", pipeline)

        self.assertIn("Visual selection is pedagogical, not a runtime shortcut", runtime)
        self.assertIn("Never choose it merely to save tokens, time, review work or tool calls", runtime)
        self.assertIn("one creative pass before independent review", runtime)
        self.assertIn("must **not inspect its own preview PNG/SVG", runtime)
        self.assertIn("There is no third visual review", runtime)

        self.assertIn("must be chosen **only because prose genuinely teaches that concept as well or better without a figure**", figures)
        self.assertIn("must never be selected to reduce runtime, token use, review calls or implementation effort", figures)
        self.assertIn("the scene creator does **not** inspect or subjectively review its own preview", figures)
        self.assertIn("at most two reviewed attempts per scene", figures)
        self.assertNotIn("maximum three reviewed attempts per scene", figures)

        self.assertIn("creator does **not** inspect, score or visually polish its own PNG/SVG", docs)
        self.assertIn("at most **two reviewed attempts per scene**", docs)
        self.assertIn("There is no third visual review", docs)
        self.assertIn("must not open its own passing preview to run a private quality pass", docs)
        self.assertNotIn("At most three reviewed attempts", docs)


if __name__ == "__main__":
    unittest.main()
