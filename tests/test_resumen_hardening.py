from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import resumen_guard

ROOT = Path(__file__).resolve().parents[1]


class ResumenHardeningTests(unittest.TestCase):
    def test_pipeline_uses_guarded_runtime_entrypoints(self):
        text = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        self.assertIn("resumen_guard.py preflight", text)
        self.assertIn("resumen_guard.py validate-plan", text)
        self.assertIn("resumen_visual_build.py --run", text)
        self.assertIn("resumen_guard.py prepare-review", text)
        self.assertIn("resumen_guard.py render", text)
        self.assertIn("resumen_finalize.py finish", text)
        self.assertIn("effective_status: finished", text)
        self.assertIn("never invent `study.py artifacts mark`", text)

    def test_visual_not_needed_is_not_in_planned_derived_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "02-plan.json").write_text(
                json.dumps(
                    {
                        "visuals": [
                            {
                                "need": "visual_required",
                                "visual_treatment": "reinterpret",
                                "derived_figure_id": "required-one",
                            },
                            {
                                "need": "visual_not_needed",
                                "visual_treatment": "reinterpret",
                                "derived_figure_id": "omitted-one",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                resumen_guard._selected_treatments(run),
                {"derived:required-one": "reinterpret"},
            )

    def test_plan_coverage_rejects_unassigned_and_missing_concepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run = base / "run"
            run.mkdir()
            concepts = base / "concepts.json"
            topics = base / "topics.json"
            concepts.write_text(
                json.dumps({"version": 2, "concepts": {"a": {}, "b": {}}}),
                encoding="utf-8",
            )
            topics.write_text(
                json.dumps({"version": 1, "topics": {"topic-1": {}}}),
                encoding="utf-8",
            )
            (run / "01-input.json").write_text(
                json.dumps(
                    {
                        "concepts_file": str(concepts),
                        "topics_file": str(topics),
                    }
                ),
                encoding="utf-8",
            )
            plan = {
                "concept_order": [{"concepts": ["a"]}],
                "unassigned_concepts": ["b"],
                "topic_coverage": {},
            }
            issues = resumen_guard._plan_coverage_issues(run, plan)
            self.assertIn("plan-unassigned-concept:b", issues)
            self.assertIn("plan-canonical-concept-missing:b", issues)
            self.assertIn("plan-topic-missing:topic-1", issues)

    def test_plan_coverage_accepts_complete_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run = base / "run"
            run.mkdir()
            concepts = base / "concepts.json"
            topics = base / "topics.json"
            concepts.write_text(
                json.dumps({"version": 2, "concepts": {"a": {}, "b": {}}}),
                encoding="utf-8",
            )
            topics.write_text(
                json.dumps({"version": 1, "topics": {"topic-1": {}}}),
                encoding="utf-8",
            )
            (run / "01-input.json").write_text(
                json.dumps(
                    {
                        "concepts_file": str(concepts),
                        "topics_file": str(topics),
                    }
                ),
                encoding="utf-8",
            )
            plan = {
                "concept_order": [{"concepts": ["a", "b"]}],
                "unassigned_concepts": [],
                "topic_coverage": {"topic-1": ["a", "b"]},
            }
            self.assertEqual(resumen_guard._plan_coverage_issues(run, plan), [])


if __name__ == "__main__":
    unittest.main()
