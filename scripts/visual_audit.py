#!/usr/bin/env python3
"""Screenshot and mechanically audit rendered study HTML.

The complete study environment includes Playwright Chromium because rendered study
artifacts must receive a real browser audit before publication. The tool injects the
rendered HTML into Chromium without navigating away from the local artifact, captures
multiple viewports, and performs objective layout/readability checks before publication.
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
    light = css.split("@media", 1)[0]
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
        canvas.paste(im, (0, y)); y += im.height
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


def audit(html_path: Path, out_dir: Path, viewport_names: tuple[str, ...] | None = None) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise SystemExit(
            "Visual audit environment is incomplete. Run INSTALAR-STUDY.bat "
            "or: python -m pip install -r requirements.txt"
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
                "or: python -m playwright install chromium"
            ) from exc
        for name in selected:
            vp = VIEWPORTS[name]
            page = browser.new_page(viewport=vp)
            if name == "print":
                page.emulate_media(media="print", color_scheme="light")
            else:
                page.emulate_media(media="screen", color_scheme="light")
            page.set_content(html_text, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(300)
            metrics = page.evaluate("""() => {
              const article = document.querySelector('article');
              const p = document.querySelector('article p');
              const body = getComputedStyle(document.body);
              const ps = p ? getComputedStyle(p) : body;
              const rect = article.getBoundingClientRect();
              return {
                clientWidth: document.documentElement.clientWidth,
                scrollWidth: document.documentElement.scrollWidth,
                articleWidth: Math.round(rect.width),
                bodyFontSize: parseFloat(body.fontSize),
                paragraphLineHeight: parseFloat(ps.lineHeight),
                paragraphFontSize: parseFloat(ps.fontSize),
                headings: document.querySelectorAll('h1,h2,h3').length,
                figures: document.querySelectorAll('figure img').length,
                callouts: document.querySelectorAll('.callout').length,
                cards: document.querySelectorAll('[class*=card]').length
              };
            }""")
            if metrics["scrollWidth"] > metrics["clientWidth"] + 2:
                report["issues"].append(f"{name}:horizontal-overflow")
            if name == "desktop" and metrics["bodyFontSize"] < 18:
                report["issues"].append("desktop:body-font-too-small")
            if name != "print" and metrics["paragraphFontSize"]:
                if metrics["paragraphLineHeight"] / metrics["paragraphFontSize"] < 1.45:
                    report["issues"].append(f"{name}:line-height-too-tight")
            shot = out_dir / f"{name}.png"
            if name == "print":
                pdf_path = out_dir / "print.pdf"
                page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=False)
                metrics["print_capture"] = _pdf_to_vertical_png(pdf_path, shot)
            else:
                page.screenshot(path=str(shot), full_page=True)
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
