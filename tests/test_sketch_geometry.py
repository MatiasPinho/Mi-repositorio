from __future__ import annotations

import unittest
from pathlib import Path

from scripts import sketch_figure, sketch_geometry

ROOT = Path(__file__).resolve().parents[1]


def dense_spec() -> dict:
    refs = ["concept:multiprogramacion"]
    nodes = [
        {"id": "a", "label": "Programa A", "shape": "box", "tone": "neutral", "rank": 0, "order": 0, "based_on": refs},
        {"id": "b", "label": "Programa B", "shape": "box", "tone": "neutral", "rank": 0, "order": 1, "based_on": refs},
        {"id": "cpu", "label": "CPU", "shape": "component", "tone": "primary", "rank": 1, "order": 0, "based_on": refs},
        {"id": "io", "label": "Dispositivo E/S", "shape": "component", "tone": "primary", "rank": 1, "order": 1, "based_on": refs},
    ]
    edges = [
        {"from": "a", "to": "cpu", "label": "ejecuta", "relation": "flow", "style": "solid", "tone": "primary", "based_on": refs},
        {"from": "b", "to": "io", "label": "espera E/S", "relation": "flow", "style": "solid", "tone": "primary", "based_on": refs},
        {"from": "a", "to": "io", "label": "mientras B espera", "relation": "relation", "style": "solid", "tone": "connection", "based_on": refs},
        {"from": "b", "to": "cpu", "label": "CPU sigue activa", "relation": "relation", "style": "solid", "tone": "connection", "based_on": refs},
    ]
    return {
        "schema_version": 1,
        "id": "multiprogramacion-densa",
        "title": "Ejecución Multiprogramada",
        "kind": "flow",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Relación entre dos programas, CPU y dispositivo de E/S.",
        "alt": "Diagrama de ejecución multiprogramada.",
        "caption": "Mientras un programa espera E/S, la CPU puede ejecutar otro.",
        "based_on": refs,
        "concepts": ["multiprogramacion"],
        "learner_focus": ["Evitar confundir espera de E/S con CPU ociosa"],
        "layout": {"direction": "top-to-bottom", "background": "transparent", "rank_gap": 72, "node_gap": 28},
        "nodes": nodes,
        "edges": edges,
        "groups": [],
    }


def horizontal_flow_spec(count: int = 5) -> dict:
    refs = ["concept:flow"]
    labels = [
        "Proceso en modo usuario",
        "Solicita un servicio",
        "Kernel privilegiado",
        "Retorno al proceso",
        "Continúa ejecución",
        "Paso extra",
    ]
    nodes = []
    edges = []
    for index in range(count):
        nodes.append({
            "id": f"n{index}",
            "label": labels[index],
            "detail": "paso breve" if index % 2 else "",
            "shape": "process" if index not in {1, 3} else "data",
            "tone": "primary" if index == 2 else "neutral",
            "rank": index,
            "order": 0,
            "based_on": refs,
        })
        if index:
            edges.append({
                "from": f"n{index - 1}",
                "to": f"n{index}",
                "relation": "flow",
                "style": "solid",
                "tone": "primary",
                "based_on": refs,
            })
    return {
        "schema_version": 1,
        "id": "horizontal-legible",
        "title": "Flujo horizontal legible",
        "kind": "flow",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Flujo horizontal para verificar escala de cuaderno.",
        "alt": "Cinco pasos conectados horizontalmente.",
        "caption": "El flujo no debe reducir la tipografía por exceder el ancho de la hoja.",
        "based_on": refs,
        "concepts": ["flow"],
        "learner_focus": ["Mantener legibilidad"],
        "layout": {"direction": "left-to-right", "background": "transparent", "rank_gap": 118, "node_gap": 56},
        "nodes": nodes,
        "edges": edges,
        "groups": [],
    }


class SketchGeometryTests(unittest.TestCase):
    def test_dense_edge_labels_get_collision_free_lanes(self):
        report = sketch_geometry.analyze_spec(dense_spec())
        self.assertTrue(report["ok"], report["issues"])
        offsets = list(report["label_offsets"].values())
        self.assertTrue(any(float(value) != 0.0 for value in offsets))

        boxes = [sketch_geometry.Rect(*row["box"]) for row in report["label_boxes"]]
        for index, left in enumerate(boxes):
            for right in boxes[index + 1 :]:
                self.assertFalse(left.intersects(right, sketch_geometry.EDGE_LABEL_GAP))

    def test_renderer_owned_minimum_gaps_override_too_tight_hints(self):
        report = sketch_geometry.analyze_spec(dense_spec())
        self.assertGreaterEqual(report["effective_layout"]["node_gap"], sketch_geometry.MIN_NODE_GAP)
        self.assertGreaterEqual(report["effective_layout"]["rank_gap"], sketch_geometry.MIN_RANK_GAP)

    def test_overwide_edge_label_is_rejected_before_svg_registration(self):
        spec = dense_spec()
        spec["edges"][0]["label"] = "etiqueta demasiado larga " * 3
        report = sketch_geometry.analyze_spec(spec)
        self.assertFalse(report["ok"])
        self.assertTrue(any(issue.startswith("edge-label-too-wide:0:") for issue in report["issues"]))

    def test_horizontal_flow_is_compacted_to_notebook_width_without_shrinking_fonts(self):
        report = sketch_geometry.analyze_spec(horizontal_flow_spec())
        self.assertTrue(report["ok"], report["issues"])
        self.assertLessEqual(report["width"], sketch_geometry.MAX_VIEWBOX_WIDTH)
        self.assertIn(report["size_class"], {"M", "L", "XL"})
        self.assertGreaterEqual(
            report["rendered_node_label_px"], sketch_geometry.NODE_LABEL_MIN_RENDERED
        )
        self.assertLessEqual(
            report["effective_layout"]["rank_gap"], sketch_geometry.HORIZONTAL_RANK_GAP_MAX
        )

    def test_six_step_horizontal_flow_fails_instead_of_becoming_tiny(self):
        report = sketch_geometry.analyze_spec(horizontal_flow_spec(6))
        self.assertFalse(report["ok"])
        self.assertTrue(
            any(issue.startswith("canvas-too-wide:") for issue in report["issues"]),
            report,
        )

    def test_connector_ports_land_on_node_borders_and_avoid_unrelated_nodes(self):
        report = sketch_geometry.analyze_spec(horizontal_flow_spec())
        self.assertTrue(report["ok"], report["issues"])
        self.assertFalse(any("connector-intrusion" in issue for issue in report["issues"]))
        self.assertEqual(len(report["connector_paths"]), 4)

    def test_installed_render_policy_embeds_notebook_typography_and_exact_edge_ports(self):
        spec = horizontal_flow_spec(4)
        report, restore = sketch_geometry.install_for_spec(spec)
        try:
            edge_path = sketch_figure._rough_polyline(
                [(10.0, 20.0), (30.0, 20.0), (30.0, 50.0)],
                "seed",
                "edge-1-a-b:main",
                scale=1.15,
            )
            svg, render_report = sketch_figure.render_svg(spec)
        finally:
            restore()

        self.assertTrue(edge_path.startswith("M 10.00 20.00"), edge_path)
        self.assertIn("30.00 50.00", edge_path)
        text = svg.decode("utf-8")
        self.assertIn('font-family:"Neucha"', text)
        self.assertIn('font-family:"Architects Daughter"', text)
        self.assertIn('data-typography="carpeta-notebook-v1"', text)
        self.assertIn('data-pencil-policy="deterministic-pencil-v2"', text)
        self.assertIn(f'data-layout-size="{report["size_class"]}"', text)
        self.assertEqual(render_report["typography_policy"], sketch_geometry.TYPOGRAPHY_POLICY)
        self.assertEqual(render_report["pencil_policy"], sketch_geometry.PENCIL_POLICY)

    def test_summary_pipeline_runs_geometry_gate_before_plan_lock(self):
        text = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        geometry_pos = text.index("sketch_geometry.py validate-plan")
        lock_pos = text.index("resumen_guard.py validate-plan")
        self.assertLess(geometry_pos, lock_pos)
        self.assertIn("resumen_visual_build.py --run", text)


if __name__ == "__main__":
    unittest.main()
