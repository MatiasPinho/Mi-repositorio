from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import scene_figure, visual_plan_v2


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


if __name__ == "__main__":
    unittest.main()
