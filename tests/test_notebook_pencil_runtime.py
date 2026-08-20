from __future__ import annotations

import re
import unittest

from scripts import scene_pencil, sketch_figure, sketch_notebook_polish
from scripts import visual_plan_hybrid_runtime as runtime


def sample_spec() -> dict:
    refs = ["concept:runtime"]
    return {
        "schema_version": 1,
        "id": "runtime-notebook-polish",
        "title": "El sistema operativo entre programas y hardware",
        "kind": "flow",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Fixture para el tratamiento visual del runtime activo.",
        "alt": "Flujo de prueba con nodos de distintas formas.",
        "caption": "Fixture de lápiz, tipografía y ajuste de texto.",
        "based_on": refs,
        "concepts": ["runtime"],
        "learner_focus": ["Mantener el lenguaje visual del cuaderno"],
        "layout": {
            "direction": "top-to-bottom",
            "background": "transparent",
            "rank_gap": 104,
            "node_gap": 52,
        },
        "nodes": [
            {
                "id": "usuario",
                "label": "Programas y personas usuarias",
                "detail": "Piden servicios para ejecutar tareas sin operar el hardware directamente",
                "shape": "component",
                "tone": "primary",
                "rank": 0,
                "order": 0,
                "based_on": refs,
            },
            {
                "id": "decision",
                "label": "¿Hay una interrupción pendiente?",
                "detail": "La decisión debe conservar texto dentro de los lados inclinados",
                "shape": "decision",
                "tone": "warning",
                "rank": 1,
                "order": 0,
                "based_on": refs,
            },
            {
                "id": "hardware",
                "label": "Hardware",
                "detail": "Procesador, memoria, E/S y bus",
                "shape": "box",
                "tone": "neutral",
                "rank": 2,
                "order": 0,
                "based_on": refs,
            },
        ],
        "edges": [
            {
                "from": "usuario",
                "to": "decision",
                "relation": "flow",
                "style": "solid",
                "tone": "primary",
                "based_on": refs,
            },
            {
                "from": "decision",
                "to": "hardware",
                "relation": "flow",
                "style": "solid",
                "tone": "primary",
                "based_on": refs,
            },
        ],
        "groups": [],
    }


class NotebookPencilPrimitiveTests(unittest.TestCase):
    def test_connector_roughness_keeps_exact_logical_ports(self):
        value = scene_pencil.rough_polyline(
            [(10.0, 20.0), (80.0, 20.0), (80.0, 90.0)],
            "seed",
            "edge-1-source-target:main",
            jitter_scale=2.0,
            bend_scale=3.0,
        )
        self.assertTrue(value.startswith("M 10.00 20.00"), value)
        self.assertRegex(value, r"80\.00 90\.00$")

    def test_closed_shapes_have_stable_but_non_identical_pencil_variants(self):
        points = [(0.0, 0.0), (200.0, 0.0), (200.0, 100.0), (0.0, 100.0)]
        first = scene_pencil.rough_polyline(
            points, "seed", "node-alpha:main", jitter_scale=1.65, bend_scale=2.85, closed=True
        )
        repeat = scene_pencil.rough_polyline(
            points, "seed", "node-alpha:main", jitter_scale=1.65, bend_scale=2.85, closed=True
        )
        second = scene_pencil.rough_polyline(
            points, "seed", "node-beta:main", jitter_scale=1.65, bend_scale=2.85, closed=True
        )
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, second)
        self.assertGreater(first.count("Q "), 4)

    def test_shape_aware_text_budget_keeps_decision_text_inside_safe_content_width(self):
        node = sample_spec()["nodes"][1]
        width, _height, label_lines, detail_lines = sketch_notebook_polish.node_dimensions(node)
        factor = sketch_notebook_polish.INNER_WIDTH_FACTOR["decision"]
        safe_width = width * factor - sketch_notebook_polish.NODE_PADDING_X * 2.0
        self.assertGreaterEqual(width, sketch_notebook_polish.MIN_WIDTH["decision"])
        for line in label_lines:
            self.assertLessEqual(
                len(line) * sketch_notebook_polish.LABEL_CHAR_WIDTH,
                safe_width + sketch_notebook_polish.LABEL_CHAR_WIDTH,
            )
        for line in detail_lines:
            self.assertLessEqual(
                len(line) * sketch_notebook_polish.DETAIL_CHAR_WIDTH,
                safe_width + sketch_notebook_polish.DETAIL_CHAR_WIDTH,
            )


class ActiveHybridNotebookPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime.install_runtime_polish()

    def test_active_runtime_keeps_fonts_shape_variants_and_title_meta_contract(self):
        svg, report = sketch_figure.render_svg(sample_spec())
        text = svg.decode("utf-8")

        self.assertIn('data-sketch-polish="carpeta-sketch-polish-v1"', text)
        self.assertIn('data-node-text-policy="fit-first-v2"', text)
        self.assertIn('data-shape-policy="pencil-shape-variants-v1"', text)
        self.assertIn('data-title-meta-policy="baseline-safe-v1"', text)
        self.assertIn('data-svg-typography="carpeta-svg-fonts-v1"', text)
        self.assertIn('font-family:"Neucha"', text)
        self.assertIn('font-family:"Architects Daughter"', text)
        self.assertRegex(
            text,
            r'<text class="sketch-kind"[^>]*y="52\.00"[^>]*data-role="figure-kind"',
        )

        variants = re.findall(r'data-pencil-variant="([abc])"', text)
        self.assertEqual(len(variants), 3)
        self.assertIn('data-pencil-profile="scale-aware-v2"', text)
        self.assertTrue(report["style_audit"]["ok"], report["style_audit"])

    def test_all_node_outlines_remain_double_trace_pencil_paths(self):
        svg, _report = sketch_figure.render_svg(sample_spec())
        text = svg.decode("utf-8")
        for node_id in ("usuario", "decision", "hardware"):
            match = re.search(
                rf'<g id="node-{node_id}".*?</g>',
                text,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match, node_id)
            body = match.group(0)
            self.assertIn('data-pencil-trace="main"', body)
            self.assertIn('data-pencil-trace="ghost"', body)
            self.assertGreaterEqual(body.count("Q "), 2)


if __name__ == "__main__":
    unittest.main()
