from __future__ import annotations

import unittest
from pathlib import Path

from scripts import sketch_geometry

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

    def test_summary_pipeline_runs_geometry_gate_before_plan_lock(self):
        text = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        geometry_pos = text.index("sketch_geometry.py validate-plan")
        lock_pos = text.index("resumen_guard.py validate-plan")
        self.assertLess(geometry_pos, lock_pos)
        self.assertIn("resumen_visual_build.py --run", text)


if __name__ == "__main__":
    unittest.main()
