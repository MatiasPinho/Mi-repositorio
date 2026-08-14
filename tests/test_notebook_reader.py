import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "scripts" / "render_study.py"
VISUAL_AUDIT = ROOT / "scripts" / "visual_audit.py"


class NotebookReaderTests(unittest.TestCase):
    def test_renderer_embeds_reader_without_replacing_semantic_content(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            md = td / "summary.md"
            out = td / "summary.html"
            md.write_text(
                "# Unidad 1\n\nUna introducción.\n\n## Tema\n\n" + "\n\n".join(
                    f"Párrafo {i} con contenido suficiente para formar varias hojas físicas."
                    for i in range(1, 45)
                ),
                encoding="utf-8",
            )
            cp = subprocess.run(
                [sys.executable, str(RENDER), str(md), str(out), "--kind", "summary", "--check"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            page = out.read_text(encoding="utf-8")
            self.assertIn('<article data-kind="summary">', page)
            self.assertIn("Párrafo 44", page)
            self.assertIn(".notebook-stack", page)
            self.assertIn(".notebook-leaf.is-neighbor", page)
            self.assertIn("notebook-turn-corner", page)
            self.assertIn("PAGED_KINDS", page)
            self.assertIn("continuous-fallback", page)

    def test_reader_navigation_is_page_stack_and_flip_uses_only_outer_edge(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")
        self.assertIn("is-neighbor", js)
        self.assertIn("go(index)", js)
        self.assertIn("notebook-turn-corner", js)
        self.assertIn("event.target.closest('.notebook-turn-corner')", js)
        self.assertIn("rotateY", css)
        self.assertIn("backface-visibility: hidden", css)
        self.assertIn("cursor: pointer", css)

        turn_rule = css.split(".notebook-turn-corner {", 1)[1].split("}", 1)[0]
        self.assertIn("top: 0", turn_rule)
        self.assertIn("bottom: 0", turn_rule)
        self.assertIn("width: 2.5rem", turn_rule)
        self.assertIn("height: auto", turn_rule)
        self.assertIn("background: transparent", turn_rule)
        self.assertIn(".notebook-turn-corner::after", css)
        self.assertIn(".notebook-back-face .notebook-turn-corner", css)

    def test_reader_keeps_safe_fallback_and_three_hole_binding(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")
        self.assertIn("oversize-block", js)
        self.assertIn("post-pagination-overflow", js)
        self.assertIn("14%", css)
        self.assertIn("50%", css)
        self.assertIn("86%", css)
        self.assertNotIn("repeat-y;\n}", css.split("article::after", 1)[1].split("}", 1)[0])

    def test_reader_reserves_inline_room_for_neighbour_peeks_on_tablet(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")
        self.assertIn("--notebook-leaf-hover-extra: .75rem", css)
        self.assertIn("100%\n      - var(--notebook-leaf-peek)", css)
        self.assertNotIn("100vw - 6.25rem", css)
        self.assertIn("@media (min-width: 48.01rem) and (max-width: 64rem)", css)
        self.assertIn("--notebook-leaf-peek: clamp(1.35rem, 3vw, 2rem)", css)
        self.assertIn("const hoverExtra = cssLengthPx", js)
        self.assertIn("peek + hoverBoost", js)

    def test_hidden_sheets_do_not_expand_document_scroll_width(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        self.assertIn("if (distance > 1)", js)
        self.assertIn("translateX(0) scale(var(--notebook-leaf-scale)) rotateY(0deg)", js)
        self.assertIn("visibility:hidden still has geometry", js)

    def test_pagination_measures_inside_final_stack_and_uses_real_overflow(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")
        self.assertIn("stack.appendChild(measure)", js)
        self.assertIn("frontFace.appendChild(numberFront)", js)
        self.assertIn("backFace.appendChild(numberBack)", js)
        self.assertIn("makeTurnCorner(frontFace, 'front'", js)
        self.assertIn("const overflows = (page) => page.scrollHeight > page.clientHeight + 1", js)
        self.assertNotIn("page.clientHeight - reserve", js)
        self.assertIn("fixed border-box height", js)
        self.assertIn(".notebook-measure-host {", css)
        self.assertIn("inset: 0", css)

    def test_tablet_browser_audit_has_no_horizontal_or_page_overflow(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            md = td / "summary.md"
            html = td / "summary.html"
            audit_dir = td / "audit"
            md.write_text(
                "# Unidad 3\n\nIntroducción del resumen.\n\n## Algoritmos\n\n" + "\n\n".join(
                    f"Párrafo {i} con una explicación breve que debe distribuirse entre muchas hojas sin desbordar el carrusel."
                    for i in range(1, 181)
                ),
                encoding="utf-8",
            )
            rendered = subprocess.run(
                [sys.executable, str(RENDER), str(md), str(html), "--kind", "summary", "--course", "Programación I", "--scope", "Unidad 3", "--check"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)

            audited = subprocess.run(
                [sys.executable, str(VISUAL_AUDIT), str(html), "--out", str(audit_dir), "--viewports", "tablet"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)
            report = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
            tablet = report["viewports"]["tablet"]
            reader = tablet["notebook_reader"]
            self.assertNotIn("tablet:horizontal-overflow", report["issues"])
            self.assertFalse(any(issue.startswith("tablet:reader-page-overflow") for issue in report["issues"]))
            self.assertLessEqual(tablet["scrollWidth"], tablet["clientWidth"] + 2)
            self.assertEqual(reader["state"], "ready")
            self.assertGreaterEqual(reader["visibleNeighbours"], 1)
            self.assertGreaterEqual(reader["leaves"], 4)
            self.assertEqual(reader["overflowingPages"], [])
            # Regression guard: an empty fixed-height page must not count as an
            # overflow. The old safety-reserve bug produced roughly one page per
            # top-level paragraph, so this long fixture exploded past 100 pages.
            self.assertLess(reader["pages"], 80)

    def test_reader_assets_participate_in_visual_artifact_fingerprint(self):
        artifact_state = (ROOT / "scripts" / "artifact_state.py").read_text(encoding="utf-8")
        self.assertIn('assets / "study-theme.css"', artifact_state)
        self.assertIn('assets / "notebook-reader.css"', artifact_state)
        self.assertIn('assets / "notebook-reader.js"', artifact_state)
        self.assertIn("digest.update(path.read_bytes())", artifact_state)


if __name__ == "__main__":
    unittest.main()
