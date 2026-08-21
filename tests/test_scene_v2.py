from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from scripts import artifact_integrity_v2, scene_figure, scene_preflight, scene_render, scene_responsive, scene_spec, visual_audit_v2, visual_review
from scripts import publish_artifact


def free_scene(scene_id: str = "free-scene") -> dict:
    return {
        "schema_version": 2,
        "id": scene_id,
        "title": "Relación libre",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "representation_role": "structural",
        "description": "Escena libre con región, dos conceptos y una conexión curva.",
        "alt": "Dos conceptos dentro de una región conectados por una curva",
        "caption": "La composición espacial y la curva hacen visible la relación.",
        "based_on": ["concept:a", "concept:b", "concept:relation"],
        "elements": [
            {"id": "region", "type": "region", "shape": "ellipse", "members": ["a", "b"], "label": "Contexto", "tone": "neutral", "based_on": ["concept:relation"]},
            {"id": "a", "type": "shape", "shape": "rounded", "label": "A", "tone": "primary", "based_on": ["concept:a"]},
            {"id": "b", "type": "shape", "shape": "circle", "label": "B", "tone": "example", "based_on": ["concept:b"]},
            {"id": "ab", "type": "connector", "from": "a", "to": "b", "relation": "relation", "arrowheads": "end", "tone": "connection", "based_on": ["concept:relation"]},
            {"id": "note", "type": "annotation", "text": "mirá la relación", "tone": "warning", "based_on": ["concept:relation"]}
        ],
        "layouts": {
            "wide": {
                "canvas": {"width": 780, "height": 430},
                "placements": {
                    "region": {"x": 40, "y": 55, "width": 700, "height": 275},
                    "a": {"x": 120, "y": 145, "width": 150, "height": 90},
                    "b": {"x": 510, "y": 125, "width": 130, "height": 130},
                    "ab": {"commands": [{"op": "move", "x": 270, "y": 190}, {"op": "cubic", "cx1": 340, "cy1": 90, "cx2": 430, "cy2": 300, "x": 510, "y": 190}]},
                    "note": {"x": 250, "y": 345, "width": 280, "height": 55, "text_anchor": "middle"}
                },
                "allowed_overlaps": []
            },
            "narrow": {
                "canvas": {"width": 400, "height": 720},
                "placements": {
                    "region": {"x": 35, "y": 45, "width": 330, "height": 520},
                    "a": {"x": 125, "y": 110, "width": 150, "height": 90},
                    "b": {"x": 135, "y": 350, "width": 130, "height": 130},
                    "ab": {"commands": [{"op": "move", "x": 200, "y": 200}, {"op": "quadratic", "cx": 285, "cy": 280, "x": 200, "y": 350}]},
                    "note": {"x": 60, "y": 615, "width": 280, "height": 55, "text_anchor": "middle"}
                },
                "allowed_overlaps": []
            }
        }
    }


class SceneV2PureTests(unittest.TestCase):
    def test_normalization_and_render_are_byte_deterministic(self):
        scene = free_scene()
        normalized = scene_spec.validate_scene(scene)
        reordered = {key: scene[key] for key in reversed(list(scene))}
        self.assertEqual(normalized, scene_spec.validate_scene(reordered))
        first, a = scene_render.render_variant(normalized, "wide", narrow_asset="free-scene-narrow.svg")
        second, b = scene_render.render_variant(reordered, "wide", narrow_asset="free-scene-narrow.svg")
        self.assertEqual(first, second)
        self.assertEqual(a["svg_sha256"], b["svg_sha256"])
        self.assertIn(b'data-study-scene="1"', first)
        self.assertIn(b'data-study-sketch="1"', first)
        self.assertIn(b'data-narrow-variant="free-scene-narrow.svg"', first)
        self.assertNotIn(b"<script", first.lower())
        self.assertNotIn(b"<foreignObject", first)

    def test_v2_is_free_composition_not_five_legacy_kinds(self):
        scene = scene_spec.validate_scene(free_scene())
        self.assertNotIn("kind", scene)
        self.assertEqual({e["type"] for e in scene["elements"]}, {"region", "shape", "connector", "annotation"})
        self.assertNotEqual(scene["layouts"]["wide"]["placements"]["a"], scene["layouts"]["narrow"]["placements"]["a"])

    def test_markup_injection_and_missing_provenance_are_rejected(self):
        scene = free_scene()
        scene["elements"][4]["text"] = '<svg onload="x">'
        with self.assertRaises(scene_spec.SceneSpecError):
            scene_spec.validate_scene(scene)
        scene = free_scene()
        scene["elements"][1]["based_on"] = []
        with self.assertRaises(scene_spec.SceneSpecError):
            scene_spec.validate_scene(scene)
        scene = free_scene()
        scene["elements"][4]["semantic"] = False
        with self.assertRaises(scene_spec.SceneSpecError):
            scene_spec.validate_scene(scene)

    def test_geometry_only_variants_must_place_same_element_set(self):
        scene = free_scene()
        del scene["layouts"]["narrow"]["placements"]["note"]
        with self.assertRaisesRegex(scene_spec.SceneSpecError, "place every semantic element"):
            scene_spec.validate_scene(scene)

    def test_invalid_path_is_rejected(self):
        scene = free_scene()
        scene["layouts"]["wide"]["placements"]["ab"]["commands"][0] = {"op": "cubic", "cx1": 1, "cy1": 1, "cx2": 2, "cy2": 2, "x": 3, "y": 3}
        with self.assertRaisesRegex(scene_spec.SceneSpecError, "first command must be move"):
            scene_spec.validate_scene(scene)

    def test_accidental_overlap_fails_but_declared_overlap_passes(self):
        scene = free_scene()
        for variant in ("wide", "narrow"):
            scene["layouts"][variant]["placements"]["b"].update({"x": 150, "y": 150})
        report = scene_preflight.preflight_scene(scene)
        self.assertFalse(report["ok"])
        self.assertTrue(any(x["code"] == "accidental-overlap" for x in report["issues"]))
        for variant in ("wide", "narrow"):
            scene["layouts"][variant]["allowed_overlaps"].append(["a", "b"])
        report = scene_preflight.preflight_scene(scene)
        self.assertFalse(any(x["code"] == "accidental-overlap" and set(x["elements"]) == {"a", "b"} for x in report["issues"]))

    def test_out_of_bounds_and_connector_through_unrelated_shape_fail(self):
        scene = free_scene()
        scene["layouts"]["wide"]["placements"]["b"]["x"] = 760
        report = scene_preflight.preflight_scene(scene)
        self.assertTrue(any(x["code"] == "out-of-bounds" and "b" in x["elements"] for x in report["issues"]))
        scene = free_scene()
        scene["elements"].insert(3, {"id": "blocker", "type": "shape", "shape": "rounded", "label": "X", "tone": "neutral", "based_on": ["concept:relation"]})
        for variant, placement in (("wide", {"x": 350, "y": 140, "width": 110, "height": 100}), ("narrow", {"x": 145, "y": 260, "width": 110, "height": 80})):
            scene["layouts"][variant]["placements"]["blocker"] = placement
        report = scene_preflight.preflight_scene(scene)
        self.assertTrue(any(x["code"] == "connector-through-element" and "blocker" in x["elements"] for x in report["issues"]))

    def test_scale_aware_pencil_metrics_are_perceptually_stable(self):
        scene = free_scene()
        wide = scene_render.render_variant(scene, "wide", narrow_asset="free-scene-narrow.svg")[1]
        narrow = scene_render.render_variant(scene, "narrow")[1]
        for key in ("main_width_px", "ghost_width_px", "jitter_px", "label_font_px"):
            self.assertAlmostEqual(wide["pencil_metrics"][key], narrow["pencil_metrics"][key], places=5)
        self.assertGreaterEqual(wide["pencil_metrics"]["jitter_px"], .8)

    def test_visual_review_requires_real_bound_wide_and_narrow_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wide = root / "wide.png"; narrow = root / "narrow.png"
            wide.write_bytes(b"wide"); narrow.write_bytes(b"narrow")
            preview = {"entries": [{
                "scene_id": "free-scene", "attempt": 1,
                "variants": {
                    "wide": {"png": str(wide), "png_sha256": hashlib.sha256(b"wide").hexdigest()},
                    "narrow": {"png": str(narrow), "png_sha256": hashlib.sha256(b"narrow").hexdigest()},
                }
            }]}
            scores = {key: 5 for key in visual_review.SCORE_KEYS}
            review = {"version": 1, "vision_verified": True, "reviewer": {"id": "vision-run", "capability": "vision", "independent": True}, "figures": [{
                "scene_id": "free-scene", "attempt": 1, "status": "pass", "scores": scores, "issues": [],
                "inspected": [
                    {"variant": "wide", "file": str(wide), "sha256": hashlib.sha256(b"wide").hexdigest()},
                    {"variant": "narrow", "file": str(narrow), "sha256": hashlib.sha256(b"narrow").hexdigest()},
                ]
            }]}
            self.assertTrue(visual_review.bind_review_to_preview(review, preview)["ok"])
            bad = copy.deepcopy(review); bad["vision_verified"] = False
            with self.assertRaises(visual_review.VisualReviewError):
                visual_review.bind_review_to_preview(bad, preview)
            stale = copy.deepcopy(review); stale["figures"][0]["inspected"][1]["sha256"] = "0" * 64
            with self.assertRaisesRegex(visual_review.VisualReviewError, "does not match"):
                visual_review.bind_review_to_preview(stale, preview)

    def test_responsive_transform_uses_narrow_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene = free_scene()
            narrow_name = "free-scene-narrow.svg"
            wide_bytes, _ = scene_render.render_variant(scene, "wide", narrow_asset=narrow_name)
            narrow_bytes, _ = scene_render.render_variant(scene, "narrow")
            (root / "free-scene.svg").write_bytes(wide_bytes)
            (root / narrow_name).write_bytes(narrow_bytes)
            html = '<figure class="study-sketch"><div class="plate"><img src="free-scene.svg" alt="x"></div></figure>'
            transformed, rows = scene_responsive.responsive_html(root / "page.html", html)
            self.assertEqual(rows[0]["scene_id"], "free-scene")
            self.assertIn('<picture class="study-scene-picture" data-scene-id="free-scene">', transformed)
            self.assertIn('srcset="free-scene-narrow.svg"', transformed)

    def test_html_variant_binding_requires_exact_registered_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            content = root / "content"
            run = content / "run"
            assets = content / "assets" / "figures"
            run.mkdir(parents=True)
            assets.mkdir(parents=True)
            wide = assets / "wide.svg"
            wrong = assets / "wrong.svg"
            wide.write_bytes(b"approved-wide")
            wrong.write_bytes(b"also-existing")
            meta = {
                "asset": "assets/figures/wide.svg",
                "asset_sha256": hashlib.sha256(b"approved-wide").hexdigest(),
            }
            html_path = run / "page.html"
            good = artifact_integrity_v2._scene_html_variant_issues(
                html_path, content, "derived:s", "wide", "../assets/figures/wide.svg", meta
            )
            self.assertEqual(good, [])
            bad = artifact_integrity_v2._scene_html_variant_issues(
                html_path, content, "derived:s", "wide", "../assets/figures/wrong.svg", meta
            )
            self.assertTrue(any(issue.startswith("scene-html-variant-mismatch:") for issue in bad))

    def test_responsive_audit_proves_selected_variant(self):
        wide = "data:image/svg+xml;base64,V0lERQ=="
        narrow = "data:image/svg+xml;base64,TkFSUk9X"
        markup = (
            '<picture class="study-scene-picture" data-scene-id="s">'
            f'<source media="(max-width: 48rem)" srcset="{narrow}">'
            f'<img src="{wide}"></picture>'
        )
        selected, issue = visual_audit_v2._responsive_selection(markup, narrow, "mobile", "s")
        self.assertEqual(selected, "narrow")
        self.assertIsNone(issue)
        selected, issue = visual_audit_v2._responsive_selection(markup, wide, "desktop", "s")
        self.assertEqual(selected, "wide")
        self.assertIsNone(issue)
        selected, issue = visual_audit_v2._responsive_selection(markup, wide, "mobile", "s")
        self.assertEqual(selected, "wide")
        self.assertIn("scene-responsive-variant-mismatch", issue or "")


class SceneV2RegistryTests(unittest.TestCase):
    def setUp(self):
        self.slug = "zz-scene-v2-" + uuid.uuid4().hex[:8]
        self.course = ROOT / "materias" / self.slug
        for rel in ("academico", "conocimiento", "assets/figures", ".study/runs/run-1"):
            (self.course / rel).mkdir(parents=True, exist_ok=True)
        (self.course / "academico" / "academic.json").write_text(json.dumps({"identity":{"subject":"Scene V2"},"units":[{"id":"U1","name":"Unidad 1: V2"}]}), encoding="utf-8")
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps({"version":2,"figures":{}}), encoding="utf-8")
        (self.course / "conocimiento" / "concepts.json").write_text(json.dumps({"version":2,"concepts":{}}), encoding="utf-8")
        self.run = self.course / ".study" / "runs" / "run-1"

    def tearDown(self):
        shutil.rmtree(self.course, ignore_errors=True)

    def _bound(self, scene: dict, attempt: int = 1):
        wide, _ = scene_render.render_variant(scene, "wide", narrow_asset=f"{scene['id']}-narrow.svg")
        narrow, _ = scene_render.render_variant(scene, "narrow")
        attempt_dir = self.run / "02-visual-attempts" / scene["id"] / f"{attempt:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        wide_path = attempt_dir / f"{scene['id']}.svg"; narrow_path = attempt_dir / f"{scene['id']}-narrow.svg"
        wide_path.write_bytes(wide); narrow_path.write_bytes(narrow)
        wide_png = attempt_dir / "wide.png"; narrow_png = attempt_dir / "narrow.png"
        wide_png.write_bytes(b"review-wide"); narrow_png.write_bytes(b"review-narrow")
        preview = {"scene_id":scene["id"],"scene_sha256":scene_spec.scene_sha256(scene),"attempt":attempt,"variants":{
            "wide":{"svg":str(wide_path),"svg_sha256":hashlib.sha256(wide).hexdigest(),"png":str(wide_png),"png_sha256":hashlib.sha256(b"review-wide").hexdigest()},
            "narrow":{"svg":str(narrow_path),"svg_sha256":hashlib.sha256(narrow).hexdigest(),"png":str(narrow_png),"png_sha256":hashlib.sha256(b"review-narrow").hexdigest()}}}
        review = {"scene_id":scene["id"],"attempt":attempt,"status":"pass","inspected":[
            {"variant":"wide","file":str(wide_png),"sha256":hashlib.sha256(b"review-wide").hexdigest()},
            {"variant":"narrow","file":str(narrow_png),"sha256":hashlib.sha256(b"review-narrow").hexdigest()}]}
        return preview, review

    def test_preview_never_mutates_registry(self):
        before = (self.course / "conocimiento" / "figures.json").read_bytes()
        with mock.patch.object(scene_figure, "_screenshot_svg", side_effect=lambda _svg, path, variant: path.write_bytes(variant.encode())):
            result = scene_figure.preview_scene(self.course, "U1", free_scene(), self.run)
        self.assertTrue(result["ok"], result)
        self.assertEqual(before, (self.course / "conocimiento" / "figures.json").read_bytes())

    def test_preflight_failures_do_not_consume_visual_attempt_budget(self):
        bad = free_scene("budget-scene")
        bad["layouts"]["wide"]["placements"]["b"]["x"] = 760
        for _ in range(3):
            report = scene_figure.preview_scene(self.course, "U1", bad, self.run)
            self.assertFalse(report["ok"])
            self.assertIsNone(report["attempt"])
        failures = list((self.run / "02-visual-preflight-failures" / "budget-scene").glob("[0-9][0-9]"))
        self.assertEqual(len(failures), 3)
        with mock.patch.object(scene_figure, "_screenshot_svg", side_effect=lambda _svg, path, variant: path.write_bytes(variant.encode())):
            accepted = scene_figure.preview_scene(self.course, "U1", free_scene("budget-scene"), self.run)
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(accepted["attempt"], 1)

    def test_finalize_registers_both_variants_and_exact_retry_is_idempotent(self):
        scene = scene_spec.validate_scene(free_scene())
        preview, review = self._bound(scene)
        first = scene_figure.finalize_scene(self.course, "U1", scene, preview, review)
        self.assertTrue(first["created"])
        second = scene_figure.finalize_scene(self.course, "Unidad 1", scene, preview, review)
        self.assertFalse(second["created"])
        record = second["record"]
        self.assertEqual(record["scene_generation"]["schema_version"], 2)
        self.assertTrue((self.course / record["scene_generation"]["variants"]["narrow"]["asset"]).is_file())

    def test_finalize_refuses_changed_scene_after_review(self):
        scene = scene_spec.validate_scene(free_scene())
        preview, review = self._bound(scene)
        changed = copy.deepcopy(scene)
        changed["layouts"]["wide"]["placements"]["a"]["x"] += 10
        with self.assertRaisesRegex(scene_figure.SceneFigureError, "different scene"):
            scene_figure.finalize_scene(self.course, "U1", changed, preview, review)

    def test_finalize_preflights_all_permanent_asset_collisions(self):
        scene = scene_spec.validate_scene(free_scene("atomic-collision"))
        preview, review = self._bound(scene)
        assets = self.course / "assets" / "figures"
        narrow = assets / "atomic-collision-narrow.svg"
        narrow.write_bytes(b"foreign")
        with self.assertRaisesRegex(scene_figure.SceneFigureError, "asset collision"):
            scene_figure.finalize_scene(self.course, "U1", scene, preview, review)
        self.assertFalse((assets / "atomic-collision.scene.json").exists())
        self.assertFalse((assets / "atomic-collision.svg").exists())
        self.assertEqual(narrow.read_bytes(), b"foreign")

    def test_finalize_registration_failure_rolls_back_created_assets(self):
        scene = scene_spec.validate_scene(free_scene("atomic-rollback"))
        preview, review = self._bound(scene)
        assets = self.course / "assets" / "figures"
        with mock.patch.object(scene_figure, "register_derived", side_effect=ValueError("registration failed")):
            with self.assertRaisesRegex(ValueError, "registration failed"):
                scene_figure.finalize_scene(self.course, "U1", scene, preview, review)
        self.assertFalse((assets / "atomic-rollback.scene.json").exists())
        self.assertFalse((assets / "atomic-rollback.svg").exists())
        self.assertFalse((assets / "atomic-rollback-narrow.svg").exists())
        registry = json.loads((self.course / "conocimiento" / "figures.json").read_text(encoding="utf-8"))
        self.assertNotIn("derived:atomic-rollback", registry.get("figures", {}))


class SceneV2PublicationTests(unittest.TestCase):
    def test_publish_rebases_responsive_srcset(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td)
            run = root / "deep" / "run"; dest = root / "published"
            assets = root / "assets"; run.mkdir(parents=True); dest.mkdir(); assets.mkdir()
            (assets / "wide.svg").write_text("wide", encoding="utf-8")
            (assets / "narrow.svg").write_text("narrow", encoding="utf-8")
            md = run / "x.md"; html = run / "x.html"; out_md = dest / "x.md"; out_html = dest / "x.html"; report = run / "report.json"
            wide_rel = Path("../..") / "assets" / "wide.svg"
            narrow_rel = Path("../..") / "assets" / "narrow.svg"
            md.write_text(f"![x]({wide_rel.as_posix()})\n", encoding="utf-8")
            html.write_text(f'<picture data-scene-id="x"><source srcset="{narrow_rel.as_posix()}"><img src="{wide_rel.as_posix()}"></picture>', encoding="utf-8")
            result = publish_artifact.publish_pair(md, html, out_md, out_html, report)
            self.assertTrue(result["ok"])
            published = out_html.read_text(encoding="utf-8")
            self.assertIn("narrow.svg", published)
            self.assertEqual(len(result["files"][1]["resource_rewrites"]), 2)


if __name__ == "__main__":
    unittest.main()
