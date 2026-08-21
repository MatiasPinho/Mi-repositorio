from __future__ import annotations

import base64
import io
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

from scripts import illustration_figure, sketch_figure
from scripts import visual_plan_hybrid_runtime as runtime


def _flow_spec() -> dict:
    return {
        "schema_version": 1,
        "id": "runtime-flow",
        "title": "Entrada y salida",
        "kind": "flow",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Flujo real para probar el runtime pulido.",
        "alt": "Una entrada conduce a una salida",
        "caption": "El flujo conserva su estructura.",
        "based_on": ["concept:flow"],
        "concepts": ["flow"],
        "learner_focus": ["Seguir la relación"],
        "layout": {"direction": "top-to-bottom", "background": "transparent"},
        "nodes": [
            {
                "id": "input",
                "label": "Entrada",
                "shape": "data",
                "tone": "primary",
                "rank": 0,
                "order": 0,
                "based_on": ["concept:flow"],
            },
            {
                "id": "output",
                "label": "Salida",
                "shape": "process",
                "tone": "example",
                "rank": 1,
                "order": 0,
                "based_on": ["concept:flow"],
            },
        ],
        "edges": [
            {"from": "input", "to": "output", "based_on": ["concept:flow"]},
        ],
        "groups": [],
    }


def _horizontal_chain_spec() -> dict:
    nodes = []
    edges = []
    for index in range(5):
        nodes.append({
            "id": f"step-{index}",
            "label": f"Paso {index + 1} con explicación visible",
            "detail": "Detalle breve que debe conservar aire interno.",
            "shape": "rounded",
            "tone": "primary" if index == 0 else "neutral",
            "rank": index,
            "order": 0,
            "based_on": ["concept:chain"],
        })
        if index:
            edges.append({
                "from": f"step-{index - 1}",
                "to": f"step-{index}",
                "based_on": ["concept:chain"],
            })
    return {
        "schema_version": 1,
        "id": "runtime-horizontal-chain",
        "title": "Cadena horizontal extensa",
        "kind": "flow",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Cadena suficientemente larga para necesitar reflow.",
        "alt": "Cinco pasos conectados en orden",
        "caption": "El orden se conserva aunque cambie la orientación visual.",
        "based_on": ["concept:chain"],
        "concepts": ["chain"],
        "learner_focus": ["Seguir el orden sin reducir legibilidad"],
        "layout": {"direction": "left-to-right", "background": "transparent"},
        "nodes": nodes,
        "edges": edges,
        "groups": [],
    }


def _wide_rank_spec() -> dict:
    nodes = [{
        "id": "root",
        "label": "Nodo raíz con explicación suficientemente larga",
        "detail": "Debe mantener una caja amplia y texto legible.",
        "shape": "rounded",
        "tone": "primary",
        "rank": 0,
        "order": 0,
        "based_on": ["concept:wide"],
    }]
    edges = []
    for index in range(4):
        child = f"child-{index}"
        nodes.append({
            "id": child,
            "label": f"Hijo {index + 1} con una etiqueta deliberadamente extensa",
            "detail": "Detalle que no debe comprimirse contra los bordes.",
            "shape": "rounded",
            "tone": "neutral",
            "rank": 1,
            "order": index,
            "based_on": ["concept:wide"],
        })
        edges.append({"from": "root", "to": child, "based_on": ["concept:wide"]})
    return {
        "schema_version": 1,
        "id": "runtime-wide-rank",
        "title": "Rango ancho",
        "kind": "tree",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Árbol que obliga al runtime a elegir una composición legible.",
        "alt": "Una raíz conectada con cuatro hijos",
        "caption": "La composición se adapta al ancho final del cuaderno.",
        "based_on": ["concept:wide"],
        "concepts": ["wide"],
        "learner_focus": ["Leer cada nodo sin compresión"],
        "layout": {"direction": "top-to-bottom", "background": "transparent"},
        "nodes": nodes,
        "edges": edges,
        "groups": [],
    }


class HybridVisualRuntimeTests(unittest.TestCase):
    def test_node_boxes_gain_breathing_room(self):
        node = {
            "label": "Un nodo con una etiqueta bastante larga",
            "detail": "Detalle que no debe quedar pegado al borde.",
            "shape": "rounded",
        }
        old_width, old_height, _labels, _details = runtime._ORIGINAL_NODE_DIMENSIONS(node)
        width, height, _labels, _details = runtime._node_dimensions_polished(node)
        self.assertGreater(width, old_width)
        self.assertGreater(height, old_height)
        self.assertGreaterEqual(width, 232)
        self.assertGreaterEqual(height, 116)

    def test_layout_guard_reflows_unreadable_horizontal_chain(self):
        old_dimensions = sketch_figure._node_dimensions
        try:
            sketch_figure._node_dimensions = runtime._node_dimensions_polished
            runtime._layout_polished(sketch_figure.validate_spec(_horizontal_chain_spec()))
            report = runtime._ACTIVE_LAYOUT_REPORT
        finally:
            sketch_figure._node_dimensions = old_dimensions

        self.assertEqual(report["profile"], "v2-display-guard")
        self.assertEqual(report["requested_direction"], "left-to-right")
        self.assertEqual(report["resolved_direction"], "top-to-bottom")
        self.assertGreaterEqual(report["display_scale"], runtime.MIN_LAYOUT_SCALE)
        self.assertLessEqual(report["density"], runtime.V2_MAX_DENSITY)

    def test_layout_guard_uses_single_column_before_shrinking_long_nodes(self):
        old_dimensions = sketch_figure._node_dimensions
        try:
            sketch_figure._node_dimensions = runtime._node_dimensions_polished
            runtime._layout_polished(sketch_figure.validate_spec(_wide_rank_spec()))
            report = runtime._ACTIVE_LAYOUT_REPORT
        finally:
            sketch_figure._node_dimensions = old_dimensions

        self.assertEqual(report["max_nodes_per_row"], 1)
        self.assertGreaterEqual(report["display_scale"], runtime.MIN_LAYOUT_SCALE)
        self.assertTrue(
            report["min_display_gap_px"] is None
            or report["min_display_gap_px"] >= runtime.V2_MIN_DISPLAY_GAP_PX
        )

    def test_polished_renderer_keeps_real_self_closing_paths_valid(self):
        old_dimensions = sketch_figure._node_dimensions
        old_layout = sketch_figure._layout
        old_rough = sketch_figure._rough_polyline
        try:
            sketch_figure._node_dimensions = runtime._node_dimensions_polished
            sketch_figure._layout = runtime._layout_polished
            sketch_figure._rough_polyline = runtime._rough_polyline_polished
            svg, report = runtime._render_svg_polished(_flow_spec())
        finally:
            sketch_figure._node_dimensions = old_dimensions
            sketch_figure._layout = old_layout
            sketch_figure._rough_polyline = old_rough

        root = ET.fromstring(svg)
        paths = root.findall(".//{http://www.w3.org/2000/svg}path")
        stroked = [path for path in paths if path.get("stroke")]

        self.assertTrue(stroked)
        self.assertTrue(all(path.get("vector-effect") == "non-scaling-stroke" for path in stroked))
        self.assertNotIn(b'/ vector-effect=', svg)
        self.assertEqual(root.get("data-layout-profile"), "v2-display-guard")
        self.assertTrue(report["layout"]["display_scale"] >= runtime.MIN_LAYOUT_SCALE)
        self.assertTrue(report["style_audit"]["ok"], report["style_audit"])

    def test_tight_crop_removes_transparent_tail_without_provider_call(self):
        image = Image.new("RGBA", (420, 320), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((110, 55, 305, 205), fill=(80, 80, 80, 255))
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        encoded = base64.b64encode(raw.getvalue()).decode("ascii")
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="320" '
            'viewBox="0 0 420 320" data-transparent-canvas="1" data-generated-illustration="1">'
            '<title>test</title>'
            f'<image width="420" height="320" href="data:image/png;base64,{encoded}"/>'
            '</svg>'
        ).encode("utf-8")

        tightened, meta = runtime._tighten_overlay_svg(svg)
        root = ET.fromstring(tightened)
        self.assertLess(int(root.get("width", "0")), 420)
        self.assertLess(int(root.get("height", "0")), 320)
        self.assertEqual(root.get("data-crop-version"), "2")
        self.assertEqual(meta["crop_version"], 2)

    def test_runtime_installs_scale_aware_pencil_without_new_model_stage(self):
        old_version = sketch_figure.GENERATOR_VERSION
        old_illustration_version = illustration_figure.VERSION
        old_dimensions = sketch_figure._node_dimensions
        old_layout = sketch_figure._layout
        old_rough = sketch_figure._rough_polyline
        old_render = sketch_figure.render_svg
        old_prepare = illustration_figure._prepare_overlay
        try:
            runtime.install_runtime_polish()
            self.assertEqual(sketch_figure.GENERATOR_VERSION, 4)
            self.assertEqual(illustration_figure.VERSION, 2)
            self.assertIs(sketch_figure._node_dimensions, runtime._node_dimensions_polished)
            self.assertIs(sketch_figure._layout, runtime._layout_polished)
            self.assertIs(sketch_figure._rough_polyline, runtime._rough_polyline_polished)
            self.assertIs(sketch_figure.render_svg, runtime._render_svg_polished)
            self.assertIs(illustration_figure._prepare_overlay, runtime._prepare_overlay_polished)
        finally:
            sketch_figure.GENERATOR_VERSION = old_version
            illustration_figure.VERSION = old_illustration_version
            sketch_figure._node_dimensions = old_dimensions
            sketch_figure._layout = old_layout
            sketch_figure._rough_polyline = old_rough
            sketch_figure.render_svg = old_render
            illustration_figure._prepare_overlay = old_prepare


if __name__ == "__main__":
    unittest.main()
