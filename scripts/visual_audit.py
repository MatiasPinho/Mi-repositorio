#!/usr/bin/env python3
"""Screenshot and mechanically audit rendered study HTML.

The complete study environment includes Playwright Chromium because rendered study
artifacts must receive a real browser audit before publication. The tool injects the
rendered HTML into Chromium without navigating away from the local artifact, forces
lazy images to load, captures multiple viewports, and performs objective layout/
readability checks before publication.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1100},
    "tablet": {"width": 900, "height": 1050},
    "mobile": {"width": 390, "height": 844},
    "print": {"width": 1240, "height": 1000},
}


def _lum(hex_color: str) -> float:
    rgb = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]

    def f(v: float) -> float:
        return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4

    r, g, b = map(f, rgb)
    return .2126 * r + .7152 * g + .0722 * b


def contrast(a: str, b: str) -> float:
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + .05) / (y + .05)


def token_contrast_checks() -> dict[str, float]:
    css = (ROOT / "design" / "tokens.css").read_text(encoding="utf-8")
    light = css.split('html[data-study-theme="dark"]', 1)[0]
    tokens = dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", light))
    pairs = {
        "body": ("--study-ink", "--study-paper"),
        "muted": ("--study-ink-muted", "--study-paper"),
        "link": ("--study-link", "--study-paper"),
        "concept": ("--study-concept", "--study-paper"),
        "example": ("--study-example", "--study-paper"),
        "warning": ("--study-warning", "--study-paper"),
        "danger": ("--study-danger", "--study-paper"),
        "connection": ("--study-connection", "--study-paper"),
        "code_keyword": ("--notebook-code-keyword", "--study-paper"),
        "code_type": ("--notebook-code-type", "--study-paper"),
        "code_string": ("--notebook-code-string", "--study-paper"),
        "code_number": ("--notebook-code-number", "--study-paper"),
        "code_comment": ("--notebook-code-comment", "--study-paper"),
        "code_builtin": ("--notebook-code-builtin", "--study-paper"),
        "code_operator": ("--notebook-code-operator", "--study-paper"),
    }
    return {name: round(contrast(tokens[a], tokens[b]), 2) for name, (a, b) in pairs.items()}


def inline_local_images(html_text: str, base_dir: Path) -> str:
    pat = re.compile(r'(<img\b[^>]*\bsrc=")([^"]+)(")', re.I)

    def repl(m: re.Match[str]) -> str:
        src = m.group(2)
        if re.match(r"^(?:data:|https?:)", src):
            return m.group(0)
        path = (base_dir / src).resolve()
        if not path.is_file():
            return m.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'{m.group(1)}data:{mime};base64,{data}{m.group(3)}'

    return pat.sub(repl, html_text)


def _pdf_to_vertical_png(pdf_path: Path, out_png: Path) -> dict:
    import fitz
    from PIL import Image
    import io

    doc = fitz.open(pdf_path)
    images = []
    scale = 110 / 72
    for pg in doc:
        pix = pg.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        images.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
    canvas = Image.new("RGB", (max(im.width for im in images), sum(im.height for im in images)), "white")
    y = 0
    for im in images:
        canvas.paste(im, (0, y))
        y += im.height
    canvas.save(out_png)
    return {"pages": len(images), "width": canvas.width, "height": canvas.height}


def _selected_viewports(names: tuple[str, ...] | None) -> tuple[str, ...]:
    selected = names or tuple(VIEWPORTS)
    invalid = [name for name in selected if name not in VIEWPORTS]
    if invalid:
        raise SystemExit(f"Unknown visual-audit viewport(s): {', '.join(invalid)}")
    if not selected:
        raise SystemExit("At least one visual-audit viewport is required")
    return selected


def _force_images_ready(page) -> list[dict]:
    """Force lazy images through the viewport and wait until each resolves or fails."""
    return page.evaluate(
        """async () => {
          const images = Array.from(document.images);
          for (const img of images) img.loading = 'eager';

          const maxY = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
          const step = Math.max(320, Math.floor(window.innerHeight * 0.75));
          for (let y = 0; y <= maxY; y += step) {
            window.scrollTo(0, y);
            await new Promise(resolve => setTimeout(resolve, 35));
          }
          window.scrollTo(0, 0);

          await Promise.all(images.map(img => {
            if (img.complete) return Promise.resolve();
            return new Promise(resolve => {
              const done = () => resolve();
              img.addEventListener('load', done, {once: true});
              img.addEventListener('error', done, {once: true});
              setTimeout(done, 3000);
            });
          }));

          await Promise.all(images.map(img => {
            if (typeof img.decode !== 'function') return Promise.resolve();
            return img.decode().catch(() => undefined);
          }));

          return images.map(img => ({
            src: img.currentSrc || img.src,
            complete: Boolean(img.complete),
            naturalWidth: Number(img.naturalWidth || 0),
            naturalHeight: Number(img.naturalHeight || 0)
          }));
        }"""
    )


def _wait_for_notebook_reader(page) -> str:
    """Let the optional desktop reader finish pagination before measuring."""
    try:
        page.wait_for_function(
            """() => {
              const kind = document.querySelector('.study-grid > article')?.dataset.kind || '';
              const desktop = matchMedia('(min-width: 48.01rem)').matches;
              const printable = matchMedia('print').matches;
              const eligible = ['summary', 'rapid-review', 'learn', 'explain'].includes(kind);
              if (!desktop || printable || !eligible) return true;
              const state = document.documentElement.dataset.notebookReader || '';
              return state === 'ready' || state === 'continuous-fallback';
            }""",
            timeout=4500,
        )
    except Exception:
        # The following metrics turn an unfinished eligible reader into an issue.
        pass
    return page.evaluate(
        "() => document.documentElement.dataset.notebookReader || 'continuous'"
    )


def _reader_metrics(page) -> dict:
    return page.evaluate(
        """() => {
          const root = document.documentElement;
          const state = root.dataset.notebookReader || 'continuous';
          const reader = document.querySelector('.notebook-reader');
          if (!reader) {
            return {
              state,
              pages: 0,
              leaves: 0,
              activeLeaf: null,
              activeSide: null,
              overflowingPages: [],
              visibleNeighbours: 0
            };
          }
          const pages = Array.from(reader.querySelectorAll('article.notebook-page'));
          const leaves = Array.from(reader.querySelectorAll('.notebook-leaf'));
          const overflowingPages = pages
            .filter(node => node.scrollHeight > node.clientHeight + 1)
            .map(node => ({
              page: Number(node.dataset.page || 0),
              scrollHeight: node.scrollHeight,
              clientHeight: node.clientHeight
            }));
          return {
            state,
            pages: pages.length,
            leaves: leaves.length,
            activeLeaf: Number(reader.dataset.activeLeaf || 0) || null,
            activeSide: reader.dataset.activeSide || null,
            overflowingPages,
            visibleNeighbours: reader.querySelectorAll('.notebook-leaf.is-neighbor').length
          };
        }"""
    )


def _exercise_notebook_reader(page, metrics: dict) -> list[str]:
    """Smoke-test neighbour navigation and front/back flipping without touching prose."""
    if metrics.get("state") != "ready":
        return []
    issues: list[str] = []

    leaves = int(metrics.get("leaves") or 0)
    if leaves > 1:
        changed = page.evaluate(
            """() => {
              const reader = document.querySelector('.notebook-reader');
              const target = reader?.querySelector('.notebook-leaf[data-leaf="2"]');
              if (!reader || !target) return false;
              target.dispatchEvent(new PointerEvent('pointerdown', {
                bubbles: true, cancelable: true, clientX: 0, clientY: 0, button: 0
              }));
              return reader.dataset.activeLeaf === '2';
            }"""
        )
        if not changed:
            issues.append("reader:neighbor-navigation-failed")

    flipped = page.evaluate(
        """() => {
          const reader = document.querySelector('.notebook-reader');
          const corner = reader?.querySelector('.notebook-leaf.is-active .notebook-front .notebook-turn-corner');
          if (!reader || !corner) return false;
          corner.click();
          return reader.dataset.activeSide === 'back';
        }"""
    )
    if not flipped:
        issues.append("reader:page-flip-failed")

    return issues


def audit(html_path: Path, out_dir: Path, viewport_names: tuple[str, ...] | None = None) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise SystemExit(
            "Visual audit environment is incomplete. Run INSTALAR-STUDY.bat "
            "or install the isolated environment documented in docs/setup.md"
        ) from exc

    selected = _selected_viewports(viewport_names)
    html_text = inline_local_images(html_path.read_text(encoding="utf-8"), html_path.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "file": str(html_path),
        "engine": "chromium-set-content",
        "selected_viewports": list(selected),
        "contrast": token_contrast_checks(),
        "screenshots": {},
        "viewports": {},
        "issues": [],
    }

    for name, ratio in report["contrast"].items():
        if ratio < 4.5:
            report["issues"].append(f"contrast:{name}:{ratio}")

    with sync_playwright() as pw:
        executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable:
            kwargs["executable_path"] = executable
        try:
            browser = pw.chromium.launch(**kwargs)
        except Exception as exc:
            raise SystemExit(
                "Playwright Chromium is missing or cannot launch. Run INSTALAR-STUDY.bat "
                "or install the isolated environment documented in docs/setup.md"
            ) from exc

        for name in selected:
            vp = VIEWPORTS[name]
            page = browser.new_page(viewport=vp)
            if name == "print":
                page.emulate_media(media="print", color_scheme="light")
            else:
                page.emulate_media(media="screen", color_scheme="light")
            page.set_content(html_text, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(250)

            image_states = _force_images_ready(page)
            broken_images = [
                row for row in image_states
                if not row["complete"] or row["naturalWidth"] <= 0 or row["naturalHeight"] <= 0
            ]
            if broken_images:
                report["issues"].append(f"{name}:images-not-loaded:{len(broken_images)}/{len(image_states)}")

            reader_state = _wait_for_notebook_reader(page) if name != "print" else "print-continuous"
            reader = _reader_metrics(page) if name != "print" else {
                "state": reader_state,
                "pages": 0,
                "leaves": 0,
                "activeLeaf": None,
                "activeSide": None,
                "overflowingPages": [],
                "visibleNeighbours": 0,
            }

            metrics = page.evaluate(
                """() => {
                  const article = document.querySelector('article');
                  const p = document.querySelector('article p');
                  const body = getComputedStyle(document.body);
                  const ps = p ? getComputedStyle(p) : body;
                  const rect = article ? article.getBoundingClientRect() : {width: 0};
                  const images = Array.from(document.images);
                  return {
                    clientWidth: document.documentElement.clientWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    articleWidth: Math.round(rect.width),
                    bodyFontSize: parseFloat(body.fontSize),
                    paragraphLineHeight: parseFloat(ps.lineHeight),
                    paragraphFontSize: parseFloat(ps.fontSize),
                    headings: document.querySelectorAll('h1,h2,h3').length,
                    figures: document.querySelectorAll('figure img').length,
                    images: images.length,
                    loadedImages: images.filter(img => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0).length,
                    callouts: document.querySelectorAll('.callout').length,
                    cards: document.querySelectorAll('[class*=card]').length
                  };
                }"""
            )
            metrics["image_states"] = image_states
            metrics["notebook_reader"] = reader

            if metrics["scrollWidth"] > metrics["clientWidth"] + 2:
                report["issues"].append(f"{name}:horizontal-overflow")
            if name == "desktop" and metrics["bodyFontSize"] < 18:
                report["issues"].append("desktop:body-font-too-small")
            if name != "print" and metrics["paragraphFontSize"]:
                if metrics["paragraphLineHeight"] / metrics["paragraphFontSize"] < 1.45:
                    report["issues"].append(f"{name}:line-height-too-tight")

            if reader.get("state") == "ready":
                overflowing = reader.get("overflowingPages") or []
                if overflowing:
                    report["issues"].append(f"{name}:reader-page-overflow:{len(overflowing)}")
                if int(reader.get("pages") or 0) < 2:
                    report["issues"].append(f"{name}:reader-too-few-pages")
            elif (
                name in {"desktop", "tablet"}
                and reader.get("state") not in {"continuous", "continuous-fallback"}
            ):
                report["issues"].append(f"{name}:reader-incomplete:{reader.get('state')}")

            shot = out_dir / f"{name}.png"
            if name == "print":
                pdf_path = out_dir / "print.pdf"
                page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=False)
                metrics["print_capture"] = _pdf_to_vertical_png(pdf_path, shot)
            elif reader.get("state") == "ready":
                # A viewport capture is the faithful representation of a 3D leaf stack.
                # Chromium full-page capture can flatten/omit transformed backfaces.
                page.screenshot(path=str(shot), full_page=False)
                metrics["screen_capture"] = {
                    "mode": "reader-viewport",
                    "active_leaf": page.evaluate(
                        "() => document.querySelector('.notebook-reader')?.dataset.activeLeaf || null"
                    ),
                    "active_side": page.evaluate(
                        "() => document.querySelector('.notebook-reader')?.dataset.activeSide || null"
                    ),
                }
            else:
                page.screenshot(path=str(shot), full_page=True)
                metrics["screen_capture"] = {"mode": "continuous-full-page"}

            if reader.get("state") == "ready":
                report["issues"].extend(
                    f"{name}:{issue}" for issue in _exercise_notebook_reader(page, reader)
                )

            report["screenshots"][name] = str(shot)
            report["viewports"][name] = metrics
            page.close()
        browser.close()

    report["ok"] = not report["issues"]
    (out_dir / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture and mechanically audit a rendered study document")
    ap.add_argument("html")
    ap.add_argument("--out", default="visual-tests/latest")
    ap.add_argument(
        "--viewports",
        default="",
        help="Optional comma-separated subset for smoke tests; normal publication omits this and audits all viewports",
    )
    args = ap.parse_args()
    names = tuple(x.strip() for x in args.viewports.split(",") if x.strip()) or None
    report = audit(Path(args.html), Path(args.out), names)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
