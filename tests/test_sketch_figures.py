from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import artifact_integrity, sketch_figure, visual_plan

STUDY = ROOT / "study.py"
FIGURES = ROOT / "scripts" / "figure_assets.py"


def flow_spec(figure_id: str = "deterministic-flow") -> dict:
    return {
        "schema_version": 1,
        "id": figure_id,
        "title": "Entrada, decisión y salida",
        "kind": "flow",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Flujo de prueba con una decisión explícita.",
        "alt": "Una entrada pasa por una decisión y produce dos salidas",
        "caption": "Cada rama conserva su etiqueta exacta.",
        "based_on": ["concept:flow", "concept:decision"],
        "concepts": ["flow", "decision"],
        "learner_focus": ["Seguir ambas ramas sin inferir pasos"],
        "layout": {"direction": "top-to-bottom", "background": "transparent"},
        "nodes": [
            {
                "id": "input",
                "label": "Entrada A & B",
                "shape": "data",
                "tone": "primary",
                "rank": 0,
                "order": 0,
                "based_on": ["concept:flow"],
            },
            {
                "id": "decision",
                "label": "¿A > B?",
                "shape": "decision",
                "tone": "warning",
                "rank": 1,
                "order": 0,
                "based_on": ["concept:decision"],
            },
            {
                "id": "yes",
                "label": "Mostrar A",
                "shape": "process",
                "tone": "example",
                "rank": 2,
                "order": 0,
                "based_on": ["concept:decision"],
            },
            {
                "id": "no",
                "label": "Mostrar B",
                "shape": "process",
                "tone": "connection",
                "rank": 2,
                "order": 1,
                "based_on": ["concept:decision"],
            },
        ],
        "edges": [
            {"from": "input", "to": "decision", "based_on": ["concept:flow"]},
            {
                "from": "decision",
                "to": "yes",
                "label": "Sí",
                "based_on": ["concept:decision"],
            },
            {
                "from": "decision",
                "to": "no",
                "label": "No",
                "based_on": ["concept:decision"],
            },
        ],
        "groups": [],
    }


class SketchFigureTests(unittest.TestCase):
    def setUp(self):
        self.slug = "zz-sketch-" + uuid.uuid4().hex[:8]
        self.course = ROOT / "materias" / self.slug
        (self.course / "academico").mkdir(parents=True)
        (self.course / "conocimiento").mkdir()
        (self.course / "assets" / "figures").mkdir(parents=True)
        (self.course / "academico" / "academic.json").write_text(json.dumps({
            "identity": {"subject": "Sketch Test"},
            "units": [{"id": "U1", "name": "Unidad 1: Diagramas"}],
        }), encoding="utf-8")
        (self.course / "conocimiento" / "concepts.json").write_text(json.dumps({
            "version": 2,
            "concepts": {
                "flow": {"id": "flow", "name": "Flow", "unit": "U1", "unit_id": "unidad-1"},
                "decision": {"id": "decision", "name": "Decision", "unit": "U1", "unit_id": "unidad-1"},
            },
        }), encoding="utf-8")
        (self.course / "conocimiento" / "figures.json").write_text(
            json.dumps({"version": 2, "figures": {}}), encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.course, ignore_errors=True)

    def run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(STUDY), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="strict",
            check=check,
        )

    def test_render_is_byte_reproducible_and_preserves_exact_text(self):
        spec = flow_spec()
        first, report = sketch_figure.render_svg(spec)
        reordered = {key: spec[key] for key in reversed(list(spec))}
        second, second_report = sketch_figure.render_svg(reordered)
        self.assertEqual(first, second)
        self.assertEqual(report["svg_sha256"], second_report["svg_sha256"])
        self.assertEqual(hashlib.sha256(first).hexdigest(), report["svg_sha256"])
        self.assertIn(b'data-study-sketch="1"', first)
        self.assertIn(b'data-transparent-canvas="1"', first)
        self.assertIn(b'data-pencil-style="graphite-overlay-v1"', first)
        self.assertNotIn(b"<rect", first)
        self.assertNotIn(b"<pattern", first)
        self.assertNotIn(b"background:", first.lower())
        self.assertIn(report["spec_sha256"].encode("ascii"), first)
        self.assertTrue(report["style_audit"]["ok"], report["style_audit"])
        root = ET.fromstring(first)
        visible = " ".join(text.strip() for text in root.itertext() if text.strip())
        self.assertIn("Entrada A & B", visible)
        self.assertIn("¿A > B?", visible)
        self.assertIn("Sí", visible)
        self.assertNotIn("<script", first.decode("utf-8").lower())

    def test_style_audit_rejects_opaque_frame_and_excessively_clean_geometry(self):
        svg, _report = sketch_figure.render_svg(flow_spec("style-audit"))
        text = svg.decode("utf-8")

        opaque = text.replace("</svg>", '<rect width="100%" height="100%" fill="#fff"/></svg>')
        opaque_report = sketch_figure.audit_svg_style(opaque)
        self.assertFalse(opaque_report["ok"])
        self.assertIn("opaque-or-framed-rect", opaque_report["issues"])

        framed = text.replace(
            "</svg>", '<path d="M 0 0 L 680 0 L 680 900 L 0 900 Z" fill="none"/></svg>'
        )
        frame_report = sketch_figure.audit_svg_style(framed)
        self.assertFalse(frame_report["ok"])
        self.assertIn("outer-frame-path", frame_report["issues"])

        clean = text.replace(" Q ", " L ")
        clean_report = sketch_figure.audit_svg_style(clean)
        self.assertFalse(clean_report["ok"])
        self.assertTrue(
            any(issue.startswith("perfectly-straight-trace:") for issue in clean_report["issues"]),
            clean_report,
        )

    def test_supported_diagram_kinds_share_the_same_strict_contract(self):
        for kind in sorted(sketch_figure.FIGURE_KINDS):
            with self.subTest(kind=kind):
                spec = flow_spec(f"sample-{kind}")
                spec["kind"] = kind
                if kind == "tree":
                    spec["edges"] = [
                        {"from": "input", "to": "decision", "based_on": ["concept:flow"]},
                        {"from": "decision", "to": "yes", "based_on": ["concept:decision"]},
                        {"from": "decision", "to": "no", "based_on": ["concept:decision"]},
                    ]
                svg, report = sketch_figure.render_svg(spec)
                self.assertGreater(len(svg), 1000)
                self.assertEqual(report["kind"], kind)

    def test_contract_and_summary_pipeline_expose_the_deterministic_flow(self):
        schema = json.loads((ROOT / "contracts" / "sketch-figure.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(set(schema["properties"]["kind"]["enum"]), sketch_figure.FIGURE_KINDS)
        pipeline = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        self.assertIn("02-sketches", pipeline)
        self.assertIn("figures generate-sketch", pipeline)
        self.assertIn("scripts/visual_plan.py", pipeline)
        self.assertLess(pipeline.index("**VISUAL BUILD**"), pipeline.index("**DRAFT**"))
        self.assertIn("--plan <run-dir>/02-plan.json", pipeline)
        self.assertIn("never create normal diagrams with an image-generation model", pipeline)
        documentation = (ROOT / "docs" / "sketch-figures.md").read_text(encoding="utf-8")
        self.assertIn("scripts/sketch_figure.py", documentation)
        self.assertIn("preserve+derived_sketch", documentation)

    def test_visual_plan_materializes_registered_svg_before_draft_and_is_retry_stable(self):
        run = self.course / ".study" / "runs" / "materialize"
        sketches = run / "02-sketches"
        sketches.mkdir(parents=True)
        spec = flow_spec("planned-flow")
        (sketches / "planned-flow.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8"
        )
        plan_path = run / "02-plan.json"
        plan_path.write_text(json.dumps({
            "visuals": [{
                "concept_id": "flow",
                "need": "visual_required",
                "visual_treatment": "reinterpret",
                "derived_figure_id": "derived:planned-flow",
                "sketch_spec": "02-sketches/planned-flow.json",
                "based_on": spec["based_on"],
                "reason": "El flujo se reconstruye sin perder relaciones.",
            }]
        }, ensure_ascii=False), encoding="utf-8")

        first = visual_plan.materialize_plan(self.course, "U1", plan_path)
        second = visual_plan.materialize_plan(self.course, "Unidad 1", plan_path)
        self.assertEqual(first, second)
        self.assertEqual(first["entries"][0]["asset"], "assets/figures/planned-flow.svg")
        self.assertTrue((self.course / first["entries"][0]["asset"]).is_file())
        registry = json.loads((self.course / "conocimiento" / "figures.json").read_text(encoding="utf-8"))
        self.assertIn("derived:planned-flow", registry["figures"])

    def test_preserve_requires_an_explicit_fidelity_reason(self):
        source = self.course / "assets" / "figures" / "source-flow.png"
        source.write_bytes(b"source")
        registry_path = self.course / "conocimiento" / "figures.json"
        registry_path.write_text(json.dumps({
            "version": 2,
            "figures": {
                "source-flow": {
                    "id": "source-flow",
                    "unit": "U1",
                    "unit_id": "unidad-1",
                    "origin": "source",
                    "kind": "flow",
                    "source_file": "oficiales/source.pdf",
                    "asset": "assets/figures/source-flow.png",
                    "asset_sha256": hashlib.sha256(b"source").hexdigest(),
                }
            },
        }), encoding="utf-8")
        run = self.course / ".study" / "runs" / "preserve-reason"
        run.mkdir(parents=True)
        plan = run / "02-plan.json"
        plan.write_text(json.dumps({
            "visuals": [{
                "concept_id": "flow",
                "need": "visual_helpful",
                "visual_treatment": "preserve",
                "source_figure_id": "source-flow",
                "figure_kind": "flow",
                "reason": "La figura ayuda a seguir el proceso.",
            }]
        }), encoding="utf-8")
        with self.assertRaisesRegex(visual_plan.VisualPlanError, "fidelity_reason"):
            visual_plan.inspect_plan(self.course, "U1", plan)

    def test_integrity_gate_rejects_source_png_when_plan_says_reinterpret(self):
        source_bytes = b"source-png"
        source = self.course / "assets" / "figures" / "source-flow.png"
        source.write_bytes(source_bytes)
        registry_path = self.course / "conocimiento" / "figures.json"
        registry_path.write_text(json.dumps({
            "version": 2,
            "figures": {
                "source-flow": {
                    "id": "source-flow",
                    "unit": "U1",
                    "unit_id": "unidad-1",
                    "origin": "source",
                    "kind": "flow",
                    "source_file": "oficiales/source.pdf",
                    "asset": "assets/figures/source-flow.png",
                    "asset_sha256": hashlib.sha256(source_bytes).hexdigest(),
                }
            },
        }), encoding="utf-8")
        run = self.course / ".study" / "runs" / "artifact-gate"
        sketches = run / "02-sketches"
        sketches.mkdir(parents=True)
        spec = flow_spec("source-reinterpretation")
        spec["based_on"].append("figure:source-flow")
        (sketches / "source-reinterpretation.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8"
        )
        plan = run / "02-plan.json"
        plan.write_text(json.dumps({
            "visuals": [{
                "concept_id": "flow",
                "need": "visual_required",
                "visual_treatment": "reinterpret",
                "derived_figure_id": "derived:source-reinterpretation",
                "sketch_spec": "02-sketches/source-reinterpretation.json",
                "based_on": spec["based_on"],
                "reason": "Todas las relaciones se pueden reconstruir.",
            }]
        }, ensure_ascii=False), encoding="utf-8")
        visual_plan.materialize_plan(self.course, "U1", plan)

        md = run / "06-final.md"
        html = run / "09-rendered.html"
        md.write_text(
            '# Flujo\n\n![Flujo](../../../assets/figures/source-flow.png "Flujo")\n',
            encoding="utf-8",
        )
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "render_study.py"), str(md), str(html),
            "--kind", "summary", "--course", "Sketch Test", "--scope", "Unidad 1", "--check",
        ], cwd=ROOT, text=True, capture_output=True, check=True)
        failed = artifact_integrity.check(self.course, md, html, "U1", "summary", plan)
        self.assertFalse(failed["ok"], failed)
        self.assertIn(
            "planned-reinterpret-derived-not-used:flow:derived:source-reinterpretation",
            failed["issues"],
        )
        self.assertIn(
            "planned-reinterpret-uses-source-asset:flow:source-flow",
            failed["issues"],
        )

        md.write_text(
            '# Flujo\n\n![Flujo](../../../assets/figures/source-reinterpretation.svg "Flujo")\n',
            encoding="utf-8",
        )
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "render_study.py"), str(md), str(html),
            "--kind", "summary", "--course", "Sketch Test", "--scope", "Unidad 1", "--check",
        ], cwd=ROOT, text=True, capture_output=True, check=True)
        passed = artifact_integrity.check(self.course, md, html, "U1", "summary", plan)
        self.assertTrue(passed["ok"], passed)

    def test_validation_rejects_unsafe_or_unauditable_specs(self):
        cases = []
        preserve = flow_spec("preserve")
        preserve["visual_treatment"] = "preserve"
        cases.append((preserve, "visual_treatment"))
        missing_evidence = flow_spec("missing-evidence")
        del missing_evidence["nodes"][0]["based_on"]
        cases.append((missing_evidence, "based_on"))
        unknown_node = flow_spec("unknown-node")
        unknown_node["edges"][0]["to"] = "ghost"
        cases.append((unknown_node, "declared nodes"))
        free_style = flow_spec("free-style")
        free_style["nodes"][0]["color"] = "red"
        cases.append((free_style, "unknown fields"))
        unlabeled_relation = flow_spec("unlabeled-relation")
        unlabeled_relation["edges"][0]["relation"] = "dependency"
        cases.append((unlabeled_relation, "label"))
        disconnected_tree = flow_spec("disconnected-tree")
        disconnected_tree["kind"] = "tree"
        disconnected_tree["edges"] = [
            {"from": "decision", "to": "yes", "based_on": ["concept:decision"]},
            {"from": "yes", "to": "decision", "based_on": ["concept:decision"]},
            {"from": "input", "to": "no", "based_on": ["concept:flow"]},
        ]
        cases.append((disconnected_tree, "acyclic and reachable"))
        for spec, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(sketch_figure.SketchSpecError, message):
                    sketch_figure.validate_spec(spec)

    def test_generate_command_is_atomic_idempotent_and_collision_safe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            spec_path = Path(temp_dir) / "figure.json"
            spec = flow_spec()
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            first = json.loads(self.run_cli(
                "figures", "generate-sketch", self.slug,
                "--unit", "U1", "--spec", str(spec_path),
            ).stdout)
            self.assertTrue(first["created"], first)
            svg = self.course / "assets" / "figures" / "deterministic-flow.svg"
            saved_spec = self.course / "assets" / "figures" / "deterministic-flow.sketch.json"
            self.assertTrue(svg.is_file())
            self.assertTrue(saved_spec.is_file())
            original_svg = svg.read_bytes()

            again = json.loads(self.run_cli(
                "figures", "generate-sketch", self.slug,
                "--unit", "Unidad 1", "--spec", str(spec_path),
            ).stdout)
            self.assertFalse(again["created"])
            self.assertEqual(first["svg_sha256"], again["svg_sha256"])

            changed = flow_spec()
            changed["nodes"][0]["label"] = "Otra entrada"
            spec_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            collision = self.run_cli(
                "figures", "generate-sketch", self.slug,
                "--unit", "U1", "--spec", str(spec_path), check=False,
            )
            self.assertNotEqual(collision.returncode, 0)
            self.assertIn("refusing overwrite", collision.stdout + collision.stderr)
            self.assertEqual(svg.read_bytes(), original_svg)

            verified = subprocess.run(
                [sys.executable, str(FIGURES), "verify", "--course", self.slug],
                cwd=ROOT, text=True, capture_output=True, encoding="utf-8", check=True,
            )
            self.assertTrue(json.loads(verified.stdout)["ok"])

    def test_generation_routes_assets_specs_and_registry_to_canonical_unit(self):
        unit = self.course / "unidades" / "unidad-1"
        for relative in ["conocimiento", "assets/figures", "fuentes", "progreso", "resumenes/_source"]:
            (unit / relative).mkdir(parents=True, exist_ok=True)
        (unit / "conocimiento" / "figures.json").write_text(
            json.dumps({"version": 2, "figures": {}}), encoding="utf-8"
        )
        result = sketch_figure.generate_and_register(self.course, "Unidad 1", flow_spec("canonical-flow"))
        self.assertTrue(result["created"], result)
        self.assertTrue((unit / "assets" / "figures" / "canonical-flow.svg").is_file())
        self.assertTrue((unit / "assets" / "figures" / "canonical-flow.sketch.json").is_file())
        registry = json.loads((unit / "conocimiento" / "figures.json").read_text(encoding="utf-8"))
        self.assertIn("derived:canonical-flow", registry["figures"])
        self.assertNotIn(
            "derived:canonical-flow",
            json.loads((self.course / "conocimiento" / "figures.json").read_text(encoding="utf-8"))["figures"],
        )

    def test_registry_verification_detects_spec_tampering(self):
        result = sketch_figure.generate_and_register(self.course, "U1", flow_spec("tamper-check"))
        self.assertTrue(result["created"])
        spec_path = self.course / "assets" / "figures" / "tamper-check.sketch.json"
        spec_path.write_text(spec_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        cp = subprocess.run(
            [sys.executable, str(FIGURES), "verify", "--course", self.slug],
            cwd=ROOT, text=True, capture_output=True, encoding="utf-8",
        )
        self.assertNotEqual(cp.returncode, 0)
        reasons = {issue["reason"] for issue in json.loads(cp.stdout)["issues"]}
        self.assertIn("generated-spec-changed", reasons)

    def test_preserve_companion_requires_and_registers_original_link(self):
        source_asset = self.course / "assets" / "figures" / "source-flow.png"
        source_asset.parent.mkdir(parents=True, exist_ok=True)
        source_bytes = b"original-source-pixels-must-not-change"
        source_asset.write_bytes(source_bytes)
        registry_path = self.course / "conocimiento" / "figures.json"
        registry_path.write_text(json.dumps({
            "version": 2,
            "figures": {
                "source-flow": {
                    "id": "source-flow",
                    "unit": "U1",
                    "unit_id": "unidad-1",
                    "origin": "source",
                    "source_file": "oficiales/source.pdf",
                    "asset": "assets/figures/source-flow.png",
                    "asset_sha256": hashlib.sha256(source_bytes).hexdigest(),
                }
            },
        }), encoding="utf-8")
        spec = flow_spec("flow-companion")
        spec["visual_treatment"] = "preserve+derived_sketch"
        spec["source_figure_id"] = "source-flow"
        spec["based_on"].append("figure:source-flow")
        result = sketch_figure.generate_and_register(self.course, "U1", spec)
        self.assertTrue(result["created"])
        self.assertEqual(source_asset.read_bytes(), source_bytes)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        row = registry["figures"]["derived:flow-companion"]
        self.assertEqual(row["source_figure_id"], "source-flow")
        self.assertEqual(row["visual_treatment"], "preserve+derived_sketch")


if __name__ == "__main__":
    unittest.main()
