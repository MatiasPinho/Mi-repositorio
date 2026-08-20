from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import render_study


class InlineSketchTypographyTests(unittest.TestCase):
    def test_generated_sketch_is_inlined_hides_kind_and_uses_notebook_typography(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            svg = root / "flow.svg"
            svg.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"
  viewBox="0 0 400 200" data-study-sketch="1" data-transparent-canvas="1">
  <style>
    .sketch-title{font:600 29px serif;fill:#111}
    .sketch-label{font:600 22px serif;fill:#111}
    .sketch-detail{font:400 17px serif;fill:#666}
    .sketch-kind{font:400 15px serif;fill:#666}
  </style>
  <text class="sketch-title" x="20" y="40">Título</text>
  <text class="sketch-kind" x="380" y="40">flujo</text>
  <text class="sketch-label" x="200" y="100">Nodo</text>
  <text class="sketch-detail" x="200" y="130">Detalle</text>
</svg>
""",
                encoding="utf-8",
            )

            html, _toc, _title = render_study.render_markdown(
                '# X\n\n![Esquema](flow.svg "Descripción")\n',
                image_base=root,
            )

            self.assertIn('<figure class="study-sketch">', html)
            self.assertIn('class="notebook-sketch-svg"', html)
            self.assertIn('data-inline-study-sketch="1"', html)
            self.assertNotIn('<img ', html)
            self.assertNotIn('class="sketch-kind"', html)
            self.assertIn('class="sketch-label"', html)

            css = (render_study.HANDDRAWN_STRUCTURES_CSS).read_text(encoding="utf-8")
            self.assertIn('svg.notebook-sketch-svg .sketch-kind', css)
            self.assertIn('font-family: var(--study-font-body) !important', css)
            self.assertIn('font-family: var(--study-font-display) !important', css)


if __name__ == "__main__":
    unittest.main()
