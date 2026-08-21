import json
import shutil
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

        turn_rule = css.split("\n.notebook-turn-corner {", 1)[1].split("}", 1)[0]
        self.assertIn("top: 0", turn_rule)
        self.assertIn("bottom: 0", turn_rule)
        self.assertIn("width: 2.5rem", turn_rule)
        self.assertIn("height: auto", turn_rule)
        self.assertIn("background: transparent", turn_rule)
        self.assertIn(".notebook-turn-corner::after", css)
        self.assertIn(".notebook-back-face .notebook-turn-corner", css)

    def test_sheet_turns_on_its_own_axis_from_either_paper_edge(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")

        leaf_rule = css.split(".notebook-leaf {", 1)[1].split("}", 1)[0]
        self.assertIn("transform-origin: 50% 50%", leaf_rule)
        self.assertNotIn("left center", leaf_rule)

        self.assertIn('.notebook-turn-corner[data-edge="start"]', css)
        self.assertIn('.notebook-turn-corner[data-edge="end"]', css)
        self.assertIn('.notebook-turn-corner[data-edge="start"]::after', css)
        self.assertIn('.notebook-turn-corner[data-edge="end"]::after', css)
        self.assertIn("button.dataset.edge = edge", js)
        self.assertIn("for (const edge of ['start', 'end'])", js)
        self.assertIn("makeTurnCorner(frontFace, 'front', edge", js)
        self.assertIn("makeTurnCorner(backFace, 'back', edge", js)

        self.assertIn(
            "const screenSign = (side === 'back' ? -1 : 1) * (edge === 'end' ? 1 : -1)",
            js,
        )
        self.assertIn("setRotation(getRotation() + screenSign * 180)", js)
        self.assertNotIn("% 360", js)
        self.assertNotIn("transitionend", js)

    def test_peeking_sheet_is_clickable_instead_of_its_own_turn_handle(self):
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")
        self.assertIn(
            ".notebook-leaf:not(.is-active) .notebook-turn-corner { pointer-events: none; }",
            css,
        )

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

    def test_view_shortcut_opens_pencil_selector_and_persists_state(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")
        self.assertIn("university-study:reader-mode", js)
        self.assertIn("event.key?.toLowerCase() !== 'v'", js)
        self.assertIn("createViewPanel", js)
        self.assertIn("chooseViewMode", js)
        self.assertIn("setViewPanel(viewPanel.hidden)", js)
        self.assertIn("showModeToast", js)
        self.assertIn("localStorage", js)
        self.assertIn("restoreContinuous", js)
        self.assertIn("setViewMode", js)
        self.assertIn(".notebook-view-switch { display: none; }", css)
        self.assertIn(".notebook-view-panel", css)
        self.assertIn(".notebook-view-sketch-sheet", css)
        self.assertIn(".notebook-view-sketch-strip", css)
        self.assertIn(".notebook-view-sketch-flow", css)
        self.assertIn(".notebook-mode-toast", css)
        self.assertIn("Vista de lectura", js)
        self.assertIn("Pasá hojas físicas, frente y dorso.", js)
        self.assertIn("Leé todo seguido desplazándote hacia abajo.", js)
        self.assertIn("Vista Hojas", js)
        self.assertIn("Vista Continua", js)
        self.assertIn("pageModeUnavailable", js)
        self.assertIn("restoreScrollPosition", js)
        self.assertIn("data-notebook-figure-number", css)

    def test_topic_tabs_are_semantic_keyboard_navigation(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        css = (ROOT / "assets" / "notebook-reader.css").read_text(encoding="utf-8")
        self.assertIn(":scope > .section-head > h2[id]", js)
        self.assertIn("Índice de temas", js)
        self.assertIn("event.key?.toLowerCase()", js)
        self.assertIn("setTopicPanel", js)
        self.assertIn("navigateToTopic", js)
        self.assertIn("readerNavigatePage", js)
        self.assertIn("aria-current", js)
        self.assertIn("data-notebook-topic-number", css)
        self.assertIn(".section-head.notebook-section-tab", css)
        self.assertIn(".notebook-topic-panel", css)
        self.assertIn("margin-inline-start: calc(-1 * var(--notebook-section-tab-overhang))", css)
        self.assertIn("background: transparent", css)
        self.assertIn("--notebook-section-tab-pencil-fill", css)
        self.assertIn("--notebook-section-tab-outline", css)
        self.assertIn("margin-block: var(--notebook-line-pitch)", css)
        self.assertIn("h2:focus-visible", css)
        self.assertIn("repeating-linear-gradient", css)
        self.assertIn("transparent 0 .34rem", css)
        self.assertNotIn("notebook-topic-index-trigger", js)
        self.assertNotIn("makeTopicButton(topic, 'notebook-topic-tab'", js)
        self.assertIn("@media print", css)

    def test_right_rail_stays_reserved_without_persistent_reading_guide(self):
        js = (ROOT / "assets" / "notebook-reader.js").read_text(encoding="utf-8")
        theme = (ROOT / "assets" / "study-theme.css").read_text(encoding="utf-8")

        init = js.split("const init = () => {", 1)[1].split("init();", 1)[0]
        self.assertNotIn("createContextNote();", init)
        self.assertIn("--notebook-measure: 66rem", theme)
        self.assertIn("--notebook-wide: 48rem", theme)
        self.assertIn("--notebook-paper-width: 76rem", theme)

    def test_browser_topic_index_jumps_to_exact_topic_and_survives_view_switch(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment contract catches this elsewhere
            self.skipTest(f"Playwright unavailable: {exc}")

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            md = td / "summary.md"
            html = td / "summary.html"
            blocks = []
            for topic in range(1, 4):
                blocks.append(f"## Tema extenso {topic}")
                blocks.append(f"### Concepto central {topic}")
                blocks.extend(
                    f"Párrafo {topic}.{i} con **concepto {topic}** y contenido suficiente para distribuir cada tema entre hojas físicas."
                    for i in range(1, 22)
                )
            md.write_text(
                "# Unidad con índice\n\nIntroducción.\n\n" + "\n\n".join(blocks),
                encoding="utf-8",
            )
            rendered = subprocess.run(
                [sys.executable, str(RENDER), str(md), str(html), "--kind", "summary", "--check"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
            html_text = html.read_text(encoding="utf-8")

            with sync_playwright() as pw:
                executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
                kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
                if executable:
                    kwargs["executable_path"] = executable
                browser = pw.chromium.launch(**kwargs)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.set_content(html_text, wait_until="domcontentloaded", timeout=10000)
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'ready'",
                    timeout=6000,
                )

                self.assertEqual(page.locator(".notebook-context-note").count(), 0)

                tabs = page.locator(".section-head.notebook-section-tab")
                self.assertEqual(tabs.count(), 3)
                self.assertEqual(
                    tabs.locator("h2").all_inner_texts(),
                    ["Tema extenso 1", "Tema extenso 2", "Tema extenso 3"],
                )
                self.assertEqual(page.locator(".notebook-topic-tab").count(), 0)
                self.assertEqual(page.locator(".notebook-topic-index-trigger").count(), 0)
                self.assertEqual(page.locator(".notebook-section-tab.is-current-topic").count(), 1)
                self.assertFalse(tabs.first.locator(":scope > .num").is_visible())
                self.assertTrue(
                    tabs.first.evaluate(
                        "node => { const style = getComputedStyle(node); "
                        "const title = node.querySelector(':scope > h2').getBoundingClientRect(); "
                        "const tab = node.getBoundingClientRect(); "
                        "const inset = parseFloat(style.marginInlineStart) + parseFloat(style.paddingInlineStart); "
                        "return tab.left < title.left - 16 && Math.abs(inset) <= 1.5; }"
                    ),
                )
                self.assertTrue(
                    tabs.evaluate_all(
                        "nodes => nodes.every(node => "
                        "getComputedStyle(node).backgroundImage.includes('linear-gradient'))"
                    )
                )
                self.assertTrue(
                    tabs.evaluate_all(
                        "nodes => nodes.every(node => { "
                        "const style = getComputedStyle(node); "
                        "const heading = node.querySelector(':scope > h2'); "
                        "const pitch = parseFloat(getComputedStyle(heading).lineHeight); "
                        "return Math.abs(parseFloat(style.marginTop) - pitch) <= .75 "
                        "&& Math.abs(parseFloat(style.marginBottom) - pitch) <= .75; })"
                    )
                )

                page.keyboard.press("t")
                panel = page.locator("#notebook-topic-index-panel")
                self.assertTrue(panel.is_visible())
                page.wait_for_function(
                    "() => document.activeElement?.dataset.topicIndex === '0'",
                    timeout=1000,
                )
                self.assertEqual(
                    page.evaluate("document.activeElement?.dataset.topicIndex"),
                    "0",
                )
                page.keyboard.press("Home")
                page.keyboard.press("ArrowDown")
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookTopic === '2' "
                    "&& document.activeElement?.id",
                    timeout=2000,
                )
                second_heading_id = page.locator(".notebook-page .section-head > h2[id]").nth(1).get_attribute("id")
                self.assertEqual(page.evaluate("document.activeElement?.id"), second_heading_id)
                self.assertEqual(
                    page.locator(f"#{second_heading_id}").evaluate(
                        "node => getComputedStyle(node).outlineStyle"
                    ),
                    "none",
                )
                self.assertFalse(panel.is_visible())
                self.assertTrue(tabs.nth(1).evaluate("node => node.classList.contains('is-current-topic')"))
                self.assertFalse(tabs.nth(1).locator(":scope > .num").is_visible())
                self.assertEqual(
                    page.locator('.notebook-topic-list-button[aria-current="location"]').count(),
                    1,
                )
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth"),
                    page.evaluate("document.documentElement.clientWidth") + 2,
                )

                page.keyboard.press("v")
                page.wait_for_selector("#notebook-view-panel:not([hidden])")
                page.keyboard.press("End")
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'continuous'",
                    timeout=3000,
                )
                self.assertEqual(page.locator(".notebook-topic-tabs.is-continuous").count(), 1)
                self.assertEqual(page.locator(".notebook-context-note").count(), 0)
                self.assertEqual(page.locator(".section-head.notebook-section-tab").count(), 3)
                self.assertEqual(page.locator(".notebook-topic-tab").count(), 0)
                self.assertEqual(page.locator(".notebook-topic-index-trigger").count(), 0)
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookTopic === '3'",
                    timeout=2000,
                )
                page.keyboard.press("t")
                self.assertTrue(panel.is_visible())
                page.keyboard.press("Escape")
                self.assertFalse(panel.is_visible())

                mobile = browser.new_page(viewport={"width": 390, "height": 844})
                mobile.set_content(html_text, wait_until="domcontentloaded", timeout=10000)
                mobile.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'continuous'",
                    timeout=3000,
                )
                self.assertEqual(mobile.locator(".notebook-topic-index-trigger").count(), 0)
                self.assertEqual(mobile.locator(".notebook-context-note").count(), 0)
                self.assertTrue(mobile.locator(".section-head.notebook-section-tab").first.is_visible())
                self.assertEqual(mobile.locator(".notebook-topic-tab").count(), 0)
                running_parts = mobile.locator(".book-running-line > span").evaluate_all(
                    "nodes => nodes.map(node => node.getBoundingClientRect())"
                )
                self.assertLessEqual(running_parts[0]["bottom"], running_parts[1]["top"] + 1)
                self.assertLessEqual(
                    mobile.evaluate("document.documentElement.scrollWidth"),
                    mobile.evaluate("document.documentElement.clientWidth") + 2,
                )
                mobile.keyboard.press("t")
                self.assertTrue(mobile.locator("#notebook-topic-index-panel").is_visible())
                mobile.keyboard.press("v")
                self.assertFalse(mobile.locator("#notebook-topic-index-panel").is_visible())
                self.assertTrue(mobile.locator("#notebook-view-panel").is_visible())
                self.assertEqual(mobile.locator(".notebook-view-sketch").count(), 2)
                self.assertTrue(mobile.locator('[data-view-mode="pages"]').is_disabled())
                mobile.keyboard.press("Escape")
                self.assertFalse(mobile.locator("#notebook-view-panel").is_visible())
                mobile.close()
                browser.close()

    def test_browser_can_switch_continuous_and_pages_with_v_without_regenerating_content(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment contract catches this elsewhere
            self.skipTest(f"Playwright unavailable: {exc}")

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            md = td / "summary.md"
            html = td / "summary.html"
            md.write_text(
                "# Unidad 3\n\nIntroducción del resumen.\n\n## Algoritmos\n\n" + "\n\n".join(
                    f"Párrafo {i} con suficiente contenido para repartir el mismo documento entre hojas físicas."
                    for i in range(1, 90)
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
            html_text = html.read_text(encoding="utf-8")

            with sync_playwright() as pw:
                executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
                kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
                if executable:
                    kwargs["executable_path"] = executable
                browser = pw.chromium.launch(**kwargs)
                page = browser.new_page(viewport={"width": 1200, "height": 1000})
                page.set_content(html_text, wait_until="domcontentloaded", timeout=10000)
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'ready'",
                    timeout=6000,
                )
                self.assertEqual(page.locator(".notebook-view-switch").count(), 1)
                self.assertFalse(page.locator(".notebook-view-switch").is_visible())
                view_panel = page.locator("#notebook-view-panel")
                self.assertEqual(view_panel.count(), 1)
                self.assertFalse(view_panel.is_visible())
                original_text = page.locator("body").inner_text()

                page.keyboard.press("v")
                self.assertTrue(view_panel.is_visible())
                self.assertEqual(view_panel.locator("[data-view-mode]").count(), 2)
                self.assertEqual(
                    view_panel.locator(".notebook-view-option-label").all_inner_texts(),
                    ["Hojas", "Continua"],
                )
                self.assertEqual(view_panel.locator(".notebook-view-sketch").count(), 2)
                self.assertEqual(view_panel.locator(".notebook-view-sketch-sheet").count(), 3)
                self.assertEqual(view_panel.locator(".notebook-view-sketch-strip").count(), 1)
                page.wait_for_function(
                    "() => document.activeElement?.dataset.viewMode === 'pages'",
                    timeout=1000,
                )
                self.assertEqual(
                    page.evaluate("document.activeElement?.dataset.viewMode"),
                    "pages",
                )
                page.keyboard.press("End")
                self.assertEqual(
                    page.evaluate("document.activeElement?.dataset.viewMode"),
                    "continuous",
                )
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'continuous'",
                    timeout=3000,
                )
                self.assertFalse(view_panel.is_visible())
                self.assertEqual(page.locator(".notebook-reader").count(), 0)
                self.assertEqual(page.locator(".study-grid > article").count(), 1)
                self.assertIn("Párrafo 89", page.locator("body").inner_text())
                self.assertEqual(page.locator(".notebook-mode-toast").count(), 1)
                self.assertIn("Vista Continua", page.locator(".notebook-mode-toast").inner_text())

                page.keyboard.press("v")
                self.assertTrue(view_panel.is_visible())
                page.wait_for_function(
                    "() => document.activeElement?.dataset.viewMode === 'continuous'",
                    timeout=1000,
                )
                self.assertEqual(
                    page.evaluate("document.activeElement?.dataset.viewMode"),
                    "continuous",
                )
                page.keyboard.press("Home")
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'ready'",
                    timeout=6000,
                )
                self.assertEqual(page.locator(".notebook-reader").count(), 1)
                self.assertIn("Párrafo 89", page.locator("body").inner_text())
                self.assertIn("Vista Hojas", page.locator(".notebook-mode-toast").inner_text())
                self.assertIn("Unidad 3", original_text)
                page.keyboard.press("v")
                self.assertTrue(view_panel.is_visible())
                page.keyboard.press("Escape")
                self.assertFalse(view_panel.is_visible())
                browser.close()

    def test_tall_study_sketch_fits_a_leaf_and_v_reports_the_actual_mode(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment contract catches this elsewhere
            self.skipTest(f"Playwright unavailable: {exc}")

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            md = td / "summary.md"
            svg = td / "tall-sketch.svg"
            html = td / "summary.html"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="680" height="1408" '
                'viewBox="0 0 680 1408" data-study-sketch="1" data-transparent-canvas="1">'
                '<title>Figura vertical</title><desc>Prueba de paginación</desc>'
                '<rect x="20" y="20" width="640" height="1368" fill="none" stroke="black"/>'
                '<text x="340" y="704" text-anchor="middle">Contenido legible</text></svg>',
                encoding="utf-8",
            )
            md.write_text(
                "# Unidad 1\n\nIntroducción.\n\n## Tema\n\n"
                + "\n\n".join(f"Párrafo previo {i} con contenido de prueba." for i in range(1, 12))
                + '\n\n![Figura vertical](tall-sketch.svg "Debe caber completa en una hoja física.")\n\n'
                + "\n\n".join(f"Párrafo posterior {i} con contenido de prueba." for i in range(1, 45)),
                encoding="utf-8",
            )
            rendered = subprocess.run(
                [sys.executable, str(RENDER), str(md), str(html), "--kind", "summary", "--check"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
            html_text = html.read_text(encoding="utf-8")

            with sync_playwright() as pw:
                executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
                kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
                if executable:
                    kwargs["executable_path"] = executable
                browser = pw.chromium.launch(**kwargs)
                page = browser.new_page(viewport={"width": 1200, "height": 1000})
                page.set_content(html_text, wait_until="domcontentloaded", timeout=10000)
                page.wait_for_function(
                    "() => ['ready', 'continuous-fallback'].includes(document.documentElement.dataset.notebookReader)",
                    timeout=6000,
                )
                reader_state = page.evaluate(
                    "() => ({state: document.documentElement.dataset.notebookReader, "
                    "reason: document.querySelector('.study-grid > article')?.dataset.notebookReaderFallback || null})"
                )
                self.assertEqual(reader_state["state"], "ready", reader_state)
                self.assertEqual(page.locator(".notebook-fit-page").count(), 1)
                self.assertEqual(
                    page.locator("figure.study-sketch").get_attribute("data-notebook-figure-number"),
                    "1",
                )
                caption = page.locator("figure.study-sketch figcaption")
                self.assertEqual(caption.get_attribute("data-notebook-figure-number"), "1")
                self.assertIn(
                    "1",
                    caption.evaluate("node => getComputedStyle(node, '::before').content"),
                )
                self.assertEqual(
                    page.locator(".notebook-page").evaluate_all(
                        "nodes => nodes.filter(node => node.scrollHeight > node.clientHeight + 1).length"
                    ),
                    0,
                )

                page.keyboard.press("v")
                page.wait_for_selector("#notebook-view-panel:not([hidden])")
                page.keyboard.press("End")
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'continuous'",
                    timeout=3000,
                )
                self.assertIn("Vista Continua", page.locator(".notebook-mode-toast").inner_text())
                self.assertEqual(page.locator("h1").inner_text(), "Unidad 1")

                page.keyboard.press("v")
                page.wait_for_selector("#notebook-view-panel:not([hidden])")
                page.keyboard.press("Home")
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'ready'",
                    timeout=6000,
                )
                self.assertIn("Vista Hojas", page.locator(".notebook-mode-toast").inner_text())
                self.assertEqual(page.locator(".notebook-fit-page").count(), 1)
                browser.close()

    def test_impossible_page_fallback_keeps_scroll_and_reports_continuous_mode(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment contract catches this elsewhere
            self.skipTest(f"Playwright unavailable: {exc}")

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            md = td / "summary.md"
            html = td / "summary.html"
            oversized_code = "\n".join(f"línea_{i} = {i}" for i in range(1, 180))
            md.write_text(
                "# Unidad 1\n\nIntroducción.\n\n## Bloque indivisible\n\n"
                + "\n\n".join(f"Párrafo {i} para habilitar desplazamiento." for i in range(1, 24))
                + f"\n\n```text\n{oversized_code}\n```\n",
                encoding="utf-8",
            )
            rendered = subprocess.run(
                [sys.executable, str(RENDER), str(md), str(html), "--kind", "summary", "--check"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)

            with sync_playwright() as pw:
                executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
                kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
                if executable:
                    kwargs["executable_path"] = executable
                browser = pw.chromium.launch(**kwargs)
                context = browser.new_context(viewport={"width": 1200, "height": 900})
                context.add_init_script(
                    "localStorage.setItem('university-study:reader-mode', 'continuous')"
                )
                page = context.new_page()
                page.goto(html.resolve().as_uri(), wait_until="domcontentloaded", timeout=10000)
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'continuous'",
                    timeout=3000,
                )
                page.evaluate("window.scrollTo(0, 700)")
                before = page.evaluate("window.scrollY")

                page.keyboard.press("v")
                page.wait_for_selector("#notebook-view-panel:not([hidden])")
                page.wait_for_function(
                    "() => document.activeElement?.dataset.viewMode === 'continuous'",
                    timeout=1000,
                )
                self.assertEqual(
                    page.evaluate("document.activeElement?.dataset.viewMode"),
                    "continuous",
                )
                page.keyboard.press("Home")
                page.keyboard.press("Enter")
                page.wait_for_function(
                    "() => document.documentElement.dataset.notebookReader === 'continuous-fallback'",
                    timeout=6000,
                )
                page.wait_for_timeout(100)
                after = page.evaluate("window.scrollY")
                self.assertLessEqual(abs(after - before), 2)
                self.assertEqual(page.locator(".notebook-reader").count(), 0)
                self.assertIn("Vista Continua", page.locator(".notebook-mode-toast").inner_text())

                page.keyboard.press("v")
                page.wait_for_selector("#notebook-view-panel:not([hidden])")
                self.assertTrue(
                    page.locator('[data-view-mode="pages"]').is_disabled()
                )
                self.assertEqual(
                    page.locator('[data-view-mode="continuous"]').get_attribute("aria-checked"),
                    "true",
                )
                page.keyboard.press("Escape")
                self.assertEqual(
                    page.evaluate("document.documentElement.dataset.notebookReader"),
                    "continuous-fallback",
                )
                self.assertEqual(page.locator(".notebook-reader").count(), 0)
                browser.close()

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
            self.assertLess(reader["pages"], 80)

    def test_reader_assets_participate_in_visual_artifact_fingerprint(self):
        artifact_state = (ROOT / "scripts" / "artifact_state.py").read_text(encoding="utf-8")
        self.assertIn('assets / "study-theme.css"', artifact_state)
        self.assertIn('assets / "notebook-reader.css"', artifact_state)
        self.assertIn('assets / "notebook-reader.js"', artifact_state)
        self.assertIn("digest.update(path.read_bytes())", artifact_state)


if __name__ == "__main__":
    unittest.main()
