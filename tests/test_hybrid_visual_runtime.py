from __future__ import annotations

import base64
import io
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

from scripts import illustration_figure, sketch_figure
from scripts import visual_plan_hybrid_runtime as runtime


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
            self.assertEqual(sketch_figure.GENERATOR_VERSION, 3)
            self.assertEqual(illustration_figure.VERSION, 2)
            self.assertIs(sketch_figure._node_dimensions, runtime._node_dimensions_polished)
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
