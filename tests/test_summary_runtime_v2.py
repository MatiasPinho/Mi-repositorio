from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import fidelity_guard, run_timing, scene_spec, summary_presence, visual_reuse_v2, visual_review
from tests.test_scene_v2 import free_scene


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SummaryPresenceTests(unittest.TestCase):
    def test_finished_run_is_not_published_summary(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td)
            old_run = course / ".study" / "runs" / "old"
            old_run.mkdir(parents=True)
            (old_run / "manifest.json").write_text(json.dumps({"status": "finished"}), encoding="utf-8")
            with mock.patch.object(summary_presence, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(summary_presence, "has_unit_layout", return_value=False):
                report = summary_presence.inspect_summary(course, "unidad-1")
            self.assertFalse(report["published"])
            self.assertEqual(report["reason"], "published-pair-missing")
            self.assertFalse(report["run_history_considered"])

    def test_actual_markdown_html_pair_is_published(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td)
            out = course / "resumenes"
            out.mkdir()
            (out / "resumen-unidad-1.md").write_text("# x", encoding="utf-8")
            (out / "resumen-unidad-1.html").write_text("<html>x</html>", encoding="utf-8")
            with mock.patch.object(summary_presence, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(summary_presence, "has_unit_layout", return_value=False):
                report = summary_presence.inspect_summary(course, "unidad-1")
            self.assertTrue(report["published"])
            self.assertEqual(report["pairs"][0]["stem"], "resumen-unidad-1")


class FidelityGuardTests(unittest.TestCase):
    def ledger(self):
        return {
            "constraints": [{
                "id": "claim:x",
                "status": "unresolved",
                "relation": "contradiction",
                "handling": "attribute-competing-evidence; do-not-pick-winner",
            }]
        }

    def test_source_majority_winner_language_hard_fails(self):
        text = (
            "> [!WARNING] Conflicto interno del apunte\n"
            "> El apunte dice A y la diapositiva dice B. La formulación A es la que aparece en más fuentes y la que se usa en la materia.\n"
        )
        report = fidelity_guard.check(text, self.ledger())
        self.assertFalse(report["ok"])
        self.assertTrue(any(issue["code"].startswith("unresolved-conflict-") for issue in report["issues"]))

    def test_neutral_attribution_of_competing_evidence_passes(self):
        text = (
            "> [!WARNING] Conflicto interno del apunte\n"
            "> El apunte presenta A y la diapositiva presenta B. El material no resuelve cuál corrige a cuál, por lo que se conservan ambas formulaciones.\n"
        )
        report = fidelity_guard.check(text, self.ledger())
        self.assertTrue(report["ok"], report)


class RuntimeTimingTests(unittest.TestCase):
    def test_runtime_report_uses_real_milestone_mtimes(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            start = datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc).timestamp()
            (run / "manifest.json").write_text(json.dumps({"started_at": datetime.fromtimestamp(start, timezone.utc).isoformat()}), encoding="utf-8")
            milestones = [
                ("02-plan.json", 60),
                ("02-visual-build.json", 180),
                ("03-draft.md", 300),
                ("04-humanized.md", 360),
                ("06-final.md", 480),
                ("09-rendered.html", 490),
                ("10-integrity.json", 500),
                ("visual-audit/audit.json", 520),
                ("11-publication.json", 540),
            ]
            for rel, offset in milestones:
                path = run / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
                os.utime(path, (start + offset, start + offset))
            report = run_timing.build_report(run)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["total_seconds"], 540.0)
            by_name = {row["stage"]: row for row in report["stages"]}
            self.assertEqual(by_name["PLAN"]["seconds"], 60.0)
            self.assertEqual(by_name["VISUAL_BUILD"]["seconds"], 120.0)
            self.assertEqual(by_name["ACADEMIC_REVIEW"]["seconds"], 120.0)


class CrossRunVisualReuseTests(unittest.TestCase):
    def test_exact_prior_hash_bound_pass_is_seeded_without_new_vision(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td)
            prior = course / ".study" / "runs" / "prior"
            current = course / ".study" / "runs" / "current"
            prior.mkdir(parents=True)
            current.mkdir(parents=True)
            plan = current / "02-plan.json"
            plan.write_text("{}", encoding="utf-8")
            review_write = current / "02-visual-review.json"

            scene = scene_spec.validate_scene(free_scene("cross-run"))
            scene_hash = scene_spec.scene_sha256(scene)
            wide_svg = b"approved-wide-svg"
            narrow_svg = b"approved-narrow-svg"
            wide_png = b"approved-wide-png"
            narrow_png = b"approved-narrow-png"

            assets = course / "assets" / "figures"
            assets.mkdir(parents=True)
            (assets / "cross-run.svg").write_bytes(wide_svg)
            (assets / "cross-run-narrow.svg").write_bytes(narrow_svg)

            attempt = prior / "02-visual-attempts" / "cross-run" / "01"
            attempt.mkdir(parents=True)
            old_scene = attempt / "scene.json"
            old_scene.write_bytes(scene_spec.scene_bytes(scene))
            old_preflight = attempt / "preflight.json"
            old_preflight.write_text(json.dumps({"ok": True}), encoding="utf-8")
            old_wide_svg = attempt / "cross-run.svg"; old_wide_svg.write_bytes(wide_svg)
            old_narrow_svg = attempt / "cross-run-narrow.svg"; old_narrow_svg.write_bytes(narrow_svg)
            old_wide_png = attempt / "wide.png"; old_wide_png.write_bytes(wide_png)
            old_narrow_png = attempt / "narrow.png"; old_narrow_png.write_bytes(narrow_png)

            preview_entry = {
                "version": 1,
                "ok": True,
                "unit_id": "unidad-1",
                "scene_id": "cross-run",
                "scene_sha256": scene_hash,
                "scene_file": str(old_scene),
                "attempt": 1,
                "attempt_dir": str(attempt),
                "reused": False,
                "preflight": str(old_preflight),
                "variants": {
                    "wide": {"svg": str(old_wide_svg), "svg_sha256": sha_bytes(wide_svg), "png": str(old_wide_png), "png_sha256": sha_bytes(wide_png)},
                    "narrow": {"svg": str(old_narrow_svg), "svg_sha256": sha_bytes(narrow_svg), "png": str(old_narrow_png), "png_sha256": sha_bytes(narrow_png)},
                },
            }
            (prior / "02-visual-preview.json").write_text(json.dumps({"version": 1, "ok": True, "entries": [preview_entry], "preserved": []}), encoding="utf-8")
            scores = {key: 5 for key in visual_review.SCORE_KEYS}
            prior_review = {
                "version": 1,
                "vision_verified": True,
                "reviewer": {"id": "prior-vision", "capability": "vision", "independent": True},
                "figures": [{
                    "scene_id": "cross-run",
                    "attempt": 1,
                    "status": "pass",
                    "inspected": [
                        {"variant": "wide", "file": str(old_wide_png), "sha256": sha_bytes(wide_png)},
                        {"variant": "narrow", "file": str(old_narrow_png), "sha256": sha_bytes(narrow_png)},
                    ],
                    "scores": scores,
                    "issues": [],
                }],
            }
            (prior / "02-visual-review.json").write_text(json.dumps(prior_review), encoding="utf-8")

            row = {
                "concept_id": "c",
                "visual_treatment": "reinterpret",
                "derived_figure_id": "derived:cross-run",
                "based_on": scene["based_on"],
                "scene": scene,
            }
            registry = {"figures": {"derived:cross-run": {
                "origin": "derived",
                "visual_treatment": "reinterpret",
                "based_on": scene["based_on"],
                "scene_generation": {
                    "schema_version": 2,
                    "scene_sha256": scene_hash,
                    "variants": {
                        "wide": {"asset": "assets/figures/cross-run.svg", "asset_sha256": sha_bytes(wide_svg)},
                        "narrow": {"asset": "assets/figures/cross-run-narrow.svg", "asset_sha256": sha_bytes(narrow_svg)},
                    },
                    "visual_review": {
                        "attempt": 1,
                        "wide_png_sha256": sha_bytes(wide_png),
                        "narrow_png_sha256": sha_bytes(narrow_png),
                    },
                },
            }}}

            with mock.patch.object(visual_reuse_v2.visual_plan_v2, "inspect_plan", return_value=[row]), \
                 mock.patch.object(visual_reuse_v2, "load_registry", return_value=registry), \
                 mock.patch.object(visual_reuse_v2, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_reuse_v2, "record_unit_id", return_value="unidad-1"), \
                 mock.patch.object(visual_reuse_v2, "has_unit_layout", return_value=False):
                report = visual_reuse_v2.prepare(course, "unidad-1", plan, review_write)

            self.assertTrue(report["all_reused"], report)
            self.assertEqual(report["scene_ids"], ["cross-run"])
            seeded = json.loads(review_write.read_text(encoding="utf-8"))
            self.assertEqual(seeded["reviewer"]["id"], "prior-vision")
            self.assertEqual(seeded["figures"][0]["attempt"], 1)
            new_preview = json.loads((current / "02-visual-attempts" / "cross-run" / "01" / "preview.json").read_text(encoding="utf-8"))
            self.assertTrue(new_preview["reused_cross_run"])
            self.assertEqual(new_preview["variants"]["wide"]["png_sha256"], sha_bytes(wide_png))


if __name__ == "__main__":
    unittest.main()
