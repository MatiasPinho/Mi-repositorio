from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from scripts import artifact_integrity, figure_assets, illustration_figure, render_study, visual_plan_hybrid

ROOT = Path(__file__).resolve().parents[1]


def illustration_spec(figure_id: str = "cpu-chip") -> dict:
    return {
        "schema_version": 1,
        "id": figure_id,
        "subject": "generic computer microprocessor package",
        "view": "top-down",
        "must_show": ["square integrated-circuit package", "visible pins around the package"],
        "alt": "Dibujo a lápiz de un microprocesador visto desde arriba.",
        "caption": "Representación física simplificada de un microprocesador.",
        "based_on": ["concept:cpu"],
    }


def illustration_plan(need: str = "visual_helpful", figure_id: str = "cpu-chip") -> dict:
    return {
        "visuals": [{
            "concept_id": "cpu",
            "need": need,
            "visual_treatment": "reinterpret",
            "visual_medium": "illustration",
            "derived_figure_id": f"derived:{figure_id}",
            "based_on": ["concept:cpu"],
            "reason": "Physical recognition helps connect the term to hardware.",
            "illustration": illustration_spec(figure_id),
        }]
    }


def fake_image_bytes() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 80, 280, 220), fill=(80, 80, 80))
    raw = io.BytesIO()
    image.save(raw, "PNG")
    return raw.getvalue()


def fake_provider(_spec: dict) -> tuple[bytes, dict]:
    return fake_image_bytes(), {
        "provider": "test-provider",
        "model": "test-image-model",
        "seed": 123,
        "prompt_sha256": "a" * 64,
    }


class IllustrationContractTests(unittest.TestCase):
    def test_prompt_is_style_locked_and_forbids_textual_semantics(self):
        prompt = illustration_figure.build_prompt(illustration_spec())
        for phrase in (
            "pencil sketch",
            "Plain white background",
            "No text",
            "labels",
            "arrows",
            "Do not invent internal technical details",
        ):
            self.assertIn(phrase, prompt)

    def test_spec_rejects_unknown_freeform_prompt_field(self):
        spec = illustration_spec()
        spec["prompt"] = "draw whatever you want"
        with self.assertRaises(illustration_figure.IllustrationError):
            illustration_figure.validate_spec(spec)

    def test_generated_white_canvas_becomes_transparent_notebook_overlay(self):
        svg, meta = illustration_figure._prepare_overlay(fake_image_bytes(), "CPU")
        text = svg.decode("utf-8")
        self.assertIn('data-study-sketch="1"', text)
        self.assertIn('data-transparent-canvas="1"', text)
        self.assertIn('data-generated-illustration="1"', text)
        self.assertIn("data:image/png;base64,", text)
        self.assertLess(meta["output_size"][0], 400)
        self.assertLess(meta["output_size"][1], 300)
        self.assertTrue(meta["transparent_overlay"])

    def test_renderer_recognizes_generated_overlay_as_unframed_figure(self):
        svg, _meta = illustration_figure._prepare_overlay(fake_image_bytes(), "object")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            asset = base / "x.illustration.svg"
            asset.write_bytes(svg)
            self.assertTrue(render_study.is_study_sketch(asset.name, base))

    def test_provider_success_and_capacity_payloads_are_bounded(self):
        encoded = __import__("base64").b64encode(fake_image_bytes()).decode("ascii")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({"success": True, "result": {"image": encoded}}).encode()

        with mock.patch.dict("os.environ", {
            "CLOUDFLARE_ACCOUNT_ID": "account",
            "CLOUDFLARE_API_TOKEN": "secret",
        }, clear=False), mock.patch.object(illustration_figure.urllib.request, "urlopen", return_value=Response()):
            raw, meta = illustration_figure._cloudflare(illustration_spec())
        self.assertEqual(raw, fake_image_bytes())
        self.assertEqual(meta["model"], illustration_figure.MODEL)
        self.assertNotIn("secret", json.dumps(meta))

        error = illustration_figure.urllib.error.HTTPError(
            "https://example.invalid", 503, "capacity", {}, io.BytesIO(b'{"error":"capacity"}')
        )
        with mock.patch.dict("os.environ", {
            "CLOUDFLARE_ACCOUNT_ID": "account",
            "CLOUDFLARE_API_TOKEN": "secret",
        }, clear=False), mock.patch.object(illustration_figure.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(illustration_figure.IllustrationUnavailable):
                illustration_figure._cloudflare(illustration_spec())


class HybridPlanTests(unittest.TestCase):
    def _inspect(self, payload: dict):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / "02-plan.json"
            plan.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                return visual_plan_hybrid.inspect_plan(Path(td), "unidad-1", plan)

    def test_illustration_is_valid_only_as_visual_helpful(self):
        rows = self._inspect(illustration_plan())
        self.assertEqual(rows[0]["visual_medium"], "illustration")
        self.assertEqual(rows[0]["figure_kind"], "illustration")

        with self.assertRaises(visual_plan_hybrid.VisualPlanError):
            self._inspect(illustration_plan("visual_required"))

    def test_missing_medium_remains_backward_compatible_diagram(self):
        payload = illustration_plan()
        row = payload["visuals"][0]
        row.pop("visual_medium")
        row.pop("illustration")
        row["sketch_spec"] = "02-sketches/cpu-chip.json"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "02-sketches").mkdir()
            spec = {
                "schema_version": 1,
                "id": "cpu-chip",
                "title": "CPU",
                "kind": "technical-schematic",
                "visual_treatment": "reinterpret",
                "description": "CPU conceptual block.",
                "alt": "CPU conceptual block.",
                "caption": "CPU conceptual block.",
                "based_on": ["concept:cpu"],
                "nodes": [{"id": "cpu", "label": "CPU", "based_on": ["concept:cpu"]}],
                "edges": [],
            }
            (root / "02-sketches" / "cpu-chip.json").write_text(json.dumps(spec), encoding="utf-8")
            plan = root / "02-plan.json"
            plan.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}):
                rows = visual_plan_hybrid.inspect_plan(root, "unidad-1", plan)
        self.assertEqual(rows[0]["visual_medium"], "diagram")

    def test_provider_unavailable_is_reported_without_retry_loop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = root / "02-plan.json"
            plan.write_text(json.dumps(illustration_plan()), encoding="utf-8")
            with mock.patch.object(visual_plan_hybrid, "resolve_unit", return_value={"unit_id": "unidad-1"}), \
                 mock.patch.object(visual_plan_hybrid, "load_registry", return_value={"figures": {}}), \
                 mock.patch.object(
                     visual_plan_hybrid,
                     "generate_illustration",
                     side_effect=illustration_figure.IllustrationUnavailable("capacity"),
                 ) as generate:
                report = visual_plan_hybrid.materialize_plan(root, "unidad-1", plan)
            self.assertFalse(report["ok"])
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(report["illustration_unavailable"][0]["concept_id"], "cpu")


class HybridRegistryAndIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.slug = "zz-hybrid-" + uuid.uuid4().hex[:8]
        self.course = ROOT / "materias" / self.slug
        (self.course / "academico").mkdir(parents=True)
        (self.course / "conocimiento").mkdir()
        (self.course / "assets" / "figures").mkdir(parents=True)
        (self.course / "academico" / "academic.json").write_text(json.dumps({
            "identity": {"subject": "Hybrid Test"},
            "units": [{"id": "U1", "name": "Unidad 1: Hardware"}],
        }), encoding="utf-8")
        (self.course / "conocimiento" / "concepts.json").write_text(json.dumps({
            "version": 2,
            "concepts": {
                "cpu": {"id": "cpu", "name": "CPU", "unit": "U1", "unit_id": "unidad-1"},
            },
        }), encoding="utf-8")
        (self.course / "conocimiento" / "figures.json").write_text(
            json.dumps({"version": 2, "figures": {}}), encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.course, ignore_errors=True)

    def test_registration_is_valid_retry_stable_and_collision_safe(self):
        with mock.patch.object(illustration_figure, "_cloudflare", side_effect=fake_provider) as provider:
            first = illustration_figure.generate_and_register(
                self.course, "U1", illustration_spec(), concept_id="cpu"
            )
            second = illustration_figure.generate_and_register(
                self.course, "Unidad 1", illustration_spec(), concept_id="cpu"
            )
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(first["record"]["asset"], "assets/figures/cpu-chip.illustration.svg")
        registry = figure_assets.load_registry(self.course)
        self.assertEqual(figure_assets.registry_issues(self.course, registry), [])
        metadata = registry["figures"]["derived:cpu-chip"]["illustration_generation"]
        self.assertEqual(metadata["method"], "generated-illustration")
        self.assertNotIn("token", json.dumps(metadata).lower())

        changed = illustration_spec()
        changed["must_show"] = ["square package"]
        with mock.patch.object(illustration_figure, "_cloudflare", side_effect=fake_provider) as provider:
            with self.assertRaises(illustration_figure.IllustrationError):
                illustration_figure.generate_and_register(self.course, "U1", changed, concept_id="cpu")
        self.assertEqual(provider.call_count, 0)

    def test_hybrid_build_and_integrity_accept_registered_illustration(self):
        run = self.course / ".study" / "runs" / "hybrid-integrity"
        run.mkdir(parents=True)
        plan = run / "02-plan.json"
        plan.write_text(json.dumps(illustration_plan(), ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(illustration_figure, "_cloudflare", side_effect=fake_provider):
            report = visual_plan_hybrid.materialize_plan(self.course, "U1", plan)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["entries"][0]["visual_medium"], "illustration")

        md = run / "06-final.md"
        html = run / "09-rendered.html"
        md.write_text(
            '# CPU\n\nEl procesador es el componente central de este ejemplo.\n\n'
            '![Microprocesador](../../../assets/figures/cpu-chip.illustration.svg "Representación física simplificada")\n',
            encoding="utf-8",
        )
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "render_study.py"), str(md), str(html),
            "--kind", "summary", "--course", "Hybrid Test", "--scope", "Unidad 1", "--check",
        ], cwd=ROOT, text=True, capture_output=True, check=True)
        result = artifact_integrity.check(self.course, md, html, "U1", "summary", plan)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["planned_visual_count"], 1)


class HybridPipelineContractTests(unittest.TestCase):
    def test_summary_uses_hybrid_materializer_without_v2_scene_review_pipeline(self):
        text = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        self.assertIn("visual_plan_hybrid.py", text)
        self.assertIn("scripts/visual_plan.py", text)
        self.assertIn("one bounded provider call", text)
        self.assertIn("There is no independent per-illustration vision-review loop", text)
        self.assertNotIn("visual_plan_v2.py", text)
        self.assertNotIn("02-visual-review.json", text)

    def test_hybrid_policy_keeps_exact_semantics_out_of_generated_pixels(self):
        rules = (ROOT / "rules" / "visual" / "figures.md").read_text(encoding="utf-8")
        self.assertIn("visual_medium: diagram", rules)
        self.assertIn("visual_medium: illustration", rules)
        self.assertIn("never `visual_required`", rules)
        self.assertIn("never generate the whole study page as an image", rules)


if __name__ == "__main__":
    unittest.main()
