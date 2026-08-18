from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import (
    run_engine_guard,
    scene_figure,
    scene_spec,
    visual_plan_v2,
    visual_policy,
    visual_reuse_v2,
    visual_review,
    visual_scene_policy_guard,
)
from tests.test_scene_v2 import free_scene

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
        self.assertIn("`generic-box-substitution`", rubric)
        self.assertIn("generic-box substitution is a blocking representational failure", rubric)
        self.assertIn("The repair should improve the drawing/structure, **not add more prose**", rubric)
        self.assertIn("Do **not** penalize boxes merely for being boxes", rubric)
        self.assertIn("Never demand decorative realism, unsupported internals", rubric)

        self.assertIn("rules/visual/figures.md", pipeline)
        self.assertIn("rules/evaluation/visual-rubric.md", pipeline)
        self.assertIn("generic-box-substitution", pipeline)
        self.assertNotIn("scripts/visual_scene_policy_guard.py", pipeline)
        self.assertIn("There is no third visual review", pipeline)
        self.assertIn("omit that figure", pipeline)
        self.assertEqual(scene_figure.MAX_ATTEMPTS, 2)

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

    def test_review_cannot_rebind_old_png_pass_to_new_visual_policy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wide = root / "wide.png"
            narrow = root / "narrow.png"
            wide.write_bytes(b"wide")
            narrow.write_bytes(b"narrow")
            policy = visual_policy.current_fingerprint()
            preview = {
                "visual_policy_sha256": policy,
                "entries": [{
                    "scene_id": "policy-scene",
                    "scene_sha256": "c" * 64,
                    "attempt": 1,
                    "variants": {
                        "wide": {"png": str(wide), "png_sha256": hashlib.sha256(b"wide").hexdigest()},
                        "narrow": {"png": str(narrow), "png_sha256": hashlib.sha256(b"narrow").hexdigest()},
                    },
                }],
            }
            review = {
                "version": 1,
                "vision_verified": True,
                "visual_policy_sha256": "0" * 64,
                "reviewer": {"id": "old-review", "capability": "vision", "independent": True},
                "figures": [{
                    "scene_id": "policy-scene",
                    "attempt": 1,
                    "status": "pass",
                    "inspected": [
                        {"variant": "wide", "file": str(wide), "sha256": hashlib.sha256(b"wide").hexdigest()},
                        {"variant": "narrow", "file": str(narrow), "sha256": hashlib.sha256(b"narrow").hexdigest()},
                    ],
                    "scores": {key: 5 for key in visual_review.SCORE_KEYS},
                    "issues": [],
                }],
            }
            with self.assertRaisesRegex(visual_review.VisualReviewError, "policy"):
                visual_review.bind_review_to_preview(review, preview)

    def test_empty_review_binds_only_to_empty_preview(self):
        policy = visual_policy.current_fingerprint()
        review = {
            "version": 1,
            "vision_verified": True,
            "visual_policy_sha256": policy,
            "reviewer": {"id": "vision-empty", "capability": "vision", "independent": True},
            "figures": [],
        }
        empty_preview = {"visual_policy_sha256": policy, "entries": []}
        binding = visual_review.bind_review_to_preview(review, empty_preview)
        self.assertTrue(binding["ok"])
        self.assertEqual(binding["bindings"], [])

        nonempty_preview = {
            "visual_policy_sha256": policy,
            "entries": [{"scene_id": "still-present", "attempt": 1, "scene_sha256": "a" * 64}],
        }
        with self.assertRaisesRegex(visual_review.VisualReviewError, "scene set"):
            visual_review.bind_review_to_preview(review, nonempty_preview)

    def test_changed_registered_v2_scene_requires_new_append_only_id(self):
        scene = scene_spec.validate_scene(free_scene("registered-scene"))
        changed = copy.deepcopy(scene)
        changed["layouts"]["wide"]["placements"]["a"]["x"] += 20
        figures = {
            "derived:registered-scene": {
                "origin": "derived",
                "unit_id": "unidad-1",
                "scene_generation": {
                    "schema_version": 2,
                    "scene_sha256": scene_spec.scene_sha256(scene),
                },
            }
        }
        with mock.patch.object(visual_plan_v2, "record_unit_id", return_value="unidad-1"):
            with self.assertRaisesRegex(visual_plan_v2.VisualPlanV2Error, "use a new scene id"):
                visual_plan_v2._assert_registered_v2_scene_is_same_revision(
                    Path("."), "unidad-1", figures, loc="visuals[0]", scene=changed
                )

    def test_policy_stale_registered_scene_guard_remains_available_for_maintenance(self):
        scene = scene_spec.validate_scene(free_scene("stale-scene"))
        scene_sha = scene_spec.scene_sha256(scene)
        rows = [{
            "scene": scene,
            "derived_figure_id": "derived:stale-scene",
            "visual_treatment": "reinterpret",
        }]
        registry = {
            "figures": {
                "derived:stale-scene": {
                    "origin": "derived",
                    "unit_id": "unidad-1",
                    "scene_generation": {
                        "schema_version": 2,
                        "scene_sha256": scene_sha,
                    },
                }
            }
        }
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / "02-plan.json"
            plan.write_text("{}\n", encoding="utf-8")
            patches = (
                mock.patch.object(visual_scene_policy_guard.visual_plan_v2, "inspect_plan", return_value=rows),
                mock.patch.object(visual_scene_policy_guard, "resolve_unit", return_value={"unit_id": "unidad-1"}),
                mock.patch.object(visual_scene_policy_guard, "load_registry", return_value=registry),
                mock.patch.object(visual_scene_policy_guard, "record_unit_id", return_value="unidad-1"),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with mock.patch.object(
                    visual_scene_policy_guard,
                    "_matching_current_policy_pass",
                    return_value=False,
                ):
                    report = visual_scene_policy_guard.check(Path(td), "unidad-1", plan)
                self.assertFalse(report["ok"])
                self.assertEqual(
                    report["issues"][0]["code"],
                    "registered-v2-composition-stale-under-current-policy",
                )

    def test_build_integrity_replays_finalizer_instead_of_trusting_ok_json(self):
        integrity = (ROOT / "scripts" / "artifact_integrity_v2.py").read_text(encoding="utf-8")
        finalizer = (ROOT / "scripts" / "visual_plan_v2.py").read_text(encoding="utf-8")
        self.assertIn("expected_build_report", finalizer)
        self.assertIn("finalization_attestation_sha256", finalizer)
        self.assertIn("expected_build_report", integrity)
        self.assertIn("visual-v2-build-not-finalizer-equivalent", integrity)

    def test_engine_mutation_marker_is_sticky_after_engine_is_restored(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / ".study" / "runs" / "r1"
            run.mkdir(parents=True)
            (run / "manifest.json").write_text(
                json.dumps({"status": "running", "engine_snapshot": {"scripts/x.py": "a" * 64}}),
                encoding="utf-8",
            )
            with mock.patch.object(
                run_engine_guard,
                "snapshot_issues",
                return_value=["engine-modified:scripts/artifact_integrity_v2.py"],
            ):
                with self.assertRaises(run_engine_guard.EngineGuardError):
                    run_engine_guard.guard_run(run, command=["artifact_integrity_v2.py", str(run)])
            marker = run / run_engine_guard.VIOLATION_FILE
            self.assertTrue(marker.is_file())

            with mock.patch.object(run_engine_guard, "snapshot_issues", return_value=[]):
                with self.assertRaisesRegex(run_engine_guard.EngineGuardError, "already invalidated"):
                    run_engine_guard.guard_run(run, command=["pipeline_run.py", "finish", str(run)])

    def test_synthetic_run_without_manifest_keeps_fixture_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(visual_reuse_v2._visual_policy_matches_current(Path(td)))


if __name__ == "__main__":
    unittest.main()
