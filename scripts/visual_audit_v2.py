#!/usr/bin/env python3
"""Browser audit adapter for responsive Visual System V2 scenes.

The proven document-level visual_audit.py remains unchanged. This adapter
inlines both <img src> and <source srcset> assets, runs that audit, then captures
every responsive V2 scene independently at desktop and mobile widths. The final
audit.json therefore proves that a scene hidden on another physical notebook
leaf was still rendered and available for inspection.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import shutil
import tempfile
from pathlib import Path

try:
    from . import visual_audit
except ImportError:
    import visual_audit  # type: ignore

_IMG_RE = re.compile(r'(<img\b[^>]*\bsrc=")([^"]+)(")', re.I)
_SRCSET_RE = re.compile(r'(<source\b[^>]*\bsrcset=")([^"]+)(")', re.I)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _remote(value: str) -> bool:
    return bool(re.match(r"^(?:data:|https?:|#)", value, re.I))


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def inline_responsive_assets(html_text: str, base_dir: Path) -> str:
    """Inline local img/srcset resources so Chromium set_content can select either variant."""
    cache: dict[Path, str] = {}

    def inline_one(src: str) -> str:
        if _remote(src):
            return src
        path = (base_dir / src).resolve()
        if not path.is_file():
            return src
        if path not in cache:
            cache[path] = _data_uri(path)
        return cache[path]

    def img_replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{inline_one(match.group(2))}{match.group(3)}"

    def srcset_replace(match: re.Match[str]) -> str:
        candidates = []
        for raw in match.group(2).split(","):
            candidate = raw.strip()
            if not candidate:
                continue
            parts = candidate.split()
            descriptor = " " + " ".join(parts[1:]) if len(parts) > 1 else ""
            candidates.append(inline_one(parts[0]) + descriptor)
        return f"{match.group(1)}{', '.join(candidates)}{match.group(3)}"

    text = _IMG_RE.sub(img_replace, html_text)
    return _SRCSET_RE.sub(srcset_replace, text)


def _capture_scene_crops(html_text: str, out_dir: Path) -> tuple[list[dict], list[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise SystemExit(
            "Visual System V2 audit needs Playwright Chromium. Run the project setup first."
        ) from exc

    crops: list[dict] = []
    issues: list[str] = []
    crop_dir = out_dir / "figures"
    crop_dir.mkdir(parents=True, exist_ok=True)
    viewports = {
        "desktop": {"width": 900, "height": 900, "max_width": 720},
        "mobile": {"width": 390, "height": 900, "max_width": 340},
    }

    with sync_playwright() as pw:
        executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable:
            kwargs["executable_path"] = executable
        browser = pw.chromium.launch(**kwargs)
        discover = browser.new_page(viewport={"width": 900, "height": 900})
        discover.set_content(html_text, wait_until="domcontentloaded", timeout=10000)
        pictures = discover.locator("picture.study-scene-picture[data-scene-id]")
        rows = pictures.evaluate_all(
            """nodes => nodes.map(node => ({
              id: node.dataset.sceneId || '',
              html: node.outerHTML
            }))"""
        )
        discover.close()
        ids = [str(row.get("id") or "") for row in rows]
        if len(ids) != len(set(ids)):
            issues.append("scene-duplicate-id-in-final-html")

        for viewport_name, viewport in viewports.items():
            for row in rows:
                scene_id = str(row.get("id") or "")
                if not scene_id:
                    issues.append(f"{viewport_name}:scene-missing-id")
                    continue
                page = browser.new_page(viewport={"width": viewport["width"], "height": viewport["height"]})
                document = f'''<!doctype html><html><head><meta charset="utf-8"><style>
                *{{box-sizing:border-box}}html,body{{margin:0;background:#fbf9f4}}
                body{{padding:16px}}#stage{{width:min({viewport["max_width"]}px,calc(100vw - 32px));margin:auto}}
                picture,img{{display:block;width:100%;height:auto;max-width:100%}}
                </style></head><body><div id="stage">{row["html"]}</div></body></html>'''
                page.set_content(document, wait_until="load", timeout=10000)
                image = page.locator("#stage img")
                try:
                    image.evaluate("img => img.decode ? img.decode() : Promise.resolve()")
                except Exception:
                    pass
                state = image.evaluate(
                    """img => ({
                      complete: Boolean(img.complete),
                      naturalWidth: Number(img.naturalWidth || 0),
                      naturalHeight: Number(img.naturalHeight || 0),
                      currentSrc: img.currentSrc || img.src,
                      width: img.getBoundingClientRect().width,
                      height: img.getBoundingClientRect().height
                    })"""
                )
                if not state["complete"] or state["naturalWidth"] <= 0 or state["naturalHeight"] <= 0:
                    issues.append(f"{viewport_name}:scene-image-not-loaded:{scene_id}")
                min_width = 260 if viewport_name == "mobile" else 420
                if state["width"] < min_width:
                    issues.append(f"{viewport_name}:scene-too-small:{scene_id}:{round(state['width'])}")
                path = crop_dir / f"{scene_id}.{viewport_name}.png"
                page.locator("#stage").screenshot(path=str(path))
                crops.append({
                    "id": scene_id,
                    "viewport": viewport_name,
                    "file": str(path),
                    "sha256": sha256(path),
                    "rendered_width": round(float(state["width"]), 2),
                    "rendered_height": round(float(state["height"]), 2),
                    "natural_width": state["naturalWidth"],
                    "natural_height": state["naturalHeight"],
                    "loaded": bool(state["complete"] and state["naturalWidth"] > 0 and state["naturalHeight"] > 0),
                })
                page.close()
        browser.close()

    expected = {(scene_id, viewport) for scene_id in set(ids) if scene_id for viewport in viewports}
    actual = {(row["id"], row["viewport"]) for row in crops}
    for scene_id, viewport in sorted(expected - actual):
        issues.append(f"{viewport}:scene-crop-missing:{scene_id}")
    return crops, issues


def audit(html_path: Path, out_dir: Path) -> dict:
    source = html_path.resolve()
    inlined = inline_responsive_assets(source.read_text(encoding="utf-8"), source.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".html", prefix="scene-audit-", dir=source.parent, delete=False
    ) as stream:
        stream.write(inlined)
        temp_path = Path(stream.name)
    try:
        report = visual_audit.audit(temp_path, out_dir)
        crops, crop_issues = _capture_scene_crops(inlined, out_dir)
    finally:
        temp_path.unlink(missing_ok=True)
    report["file"] = str(source)
    report["visual_system_v2"] = True
    report["figure_crops"] = crops
    report["issues"].extend(crop_issues)
    report["issues"] = list(dict.fromkeys(report["issues"]))
    report["ok"] = not report["issues"]
    (out_dir / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Browser audit with per-scene Visual System V2 evidence")
    ap.add_argument("html")
    ap.add_argument("--out", default="visual-tests/latest")
    args = ap.parse_args()
    report = audit(Path(args.html), Path(args.out))
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
