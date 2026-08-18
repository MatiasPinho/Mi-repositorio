#!/usr/bin/env python3
"""Bounded Cloudflare image generation for non-authoritative study illustrations."""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from study import resolve_course  # noqa: E402
from scripts.course_layout import has_unit_layout, unit_root  # noqa: E402
from scripts.figure_assets import derived_key, load_registry, registry_issues, save_registry, sha256  # noqa: E402
from scripts.unit_identity import record_unit_id, resolve_unit  # noqa: E402

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
GENERATOR = "carpeta-cloudflare-illustration"
VERSION = 1
STYLE_VERSION = 1
TIMEOUT_SECONDS = 20
WIDTH = 1024
HEIGHT = 768
VIEWS = {"top-down", "front", "side", "isometric", "generic"}

STYLE = (
    "Educational pencil sketch for a university notebook. "
    "Simple graphite hand drawing with visible pencil texture and light shading. "
    "One isolated recognizable subject, centered, filling most of the canvas. "
    "Plain white background. No text, letters, numbers, labels, arrows, logos, "
    "watermarks, border or frame. Not photorealistic. "
    "Do not invent internal technical details that were not requested."
)


class IllustrationError(ValueError):
    pass


class IllustrationUnavailable(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IllustrationError(f"{name} must be a non-empty string")
    text = value.strip()
    if text != value or len(text) > limit or any(ord(c) < 32 for c in text):
        raise IllustrationError(f"{name} is invalid")
    return text


def _items(value: Any, name: str, *, required: bool = False) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value) or len(value) > 8:
        raise IllustrationError(
            f"{name} must be an array with 1-8 items"
            if required
            else f"{name} must be an array with at most 8 items"
        )
    out: list[str] = []
    for index, item in enumerate(value):
        text = _text(item, f"{name}[{index}]", 180)
        if text in out:
            raise IllustrationError(f"{name} contains a duplicate")
        out.append(text)
    return out


def validate_spec(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise IllustrationError("illustration spec must be an object")
    allowed = {
        "schema_version", "id", "subject", "view", "must_show", "alt", "caption", "based_on"
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise IllustrationError(f"unknown illustration fields: {', '.join(unknown)}")
    if raw.get("schema_version") != 1:
        raise IllustrationError("schema_version must be 1")
    figure_id = _text(raw.get("id"), "id", 64)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", figure_id):
        raise IllustrationError("id must use lowercase letters, digits, hyphens or underscores")
    view = _text(raw.get("view", "generic"), "view", 20)
    if view not in VIEWS:
        raise IllustrationError(f"view must be one of {sorted(VIEWS)}")
    refs = _items(raw.get("based_on"), "based_on", required=True)
    if any(not re.fullmatch(r"[a-z][a-z0-9_-]*:.+", ref) for ref in refs):
        raise IllustrationError("based_on values must be namespaced references")
    return {
        "schema_version": 1,
        "id": figure_id,
        "subject": _text(raw.get("subject"), "subject", 260),
        "view": view,
        "must_show": _items(raw.get("must_show"), "must_show", required=True),
        "alt": _text(raw.get("alt"), "alt", 320),
        "caption": _text(raw.get("caption"), "caption", 320),
        "based_on": refs,
    }


def build_prompt(spec_value: Any) -> str:
    spec = validate_spec(spec_value)
    return (
        f"{STYLE} Subject: {spec['subject']}. View: {spec['view']}. "
        f"Supported visual cues that must be visible: {'; '.join(spec['must_show'])}."
    )


def _multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----carpeta-{uuid.uuid4().hex}"
    body = b""
    for key, value in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        body += value.encode("utf-8") + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _cloudflare(spec: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        raise IllustrationUnavailable("Cloudflare Workers AI credentials are not loaded")
    prompt = build_prompt(spec)
    seed = int(hashlib.sha256(f"{STYLE_VERSION}:{canonical(spec)}".encode()).hexdigest()[:8], 16)
    body, content_type = _multipart({
        "prompt": prompt,
        "width": str(WIDTH),
        "height": str(HEIGHT),
        "seed": str(seed),
    })
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            "User-Agent": "Carpeta/illustration-v1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        if exc.code in {408, 429, 500, 502, 503, 504}:
            raise IllustrationUnavailable(
                f"Cloudflare temporarily unavailable ({exc.code}): {detail}"
            ) from exc
        raise IllustrationError(f"Cloudflare rejected the request ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IllustrationUnavailable(f"Cloudflare request failed: {exc}") from exc
    try:
        data = json.loads(payload.decode("utf-8"))
        encoded = data["result"]["image"]
        if data.get("success") is not True or not isinstance(encoded, str):
            raise KeyError
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise IllustrationUnavailable("Cloudflare returned an invalid image response") from exc
    return raw, {
        "provider": "cloudflare-workers-ai",
        "model": MODEL,
        "seed": seed,
        "prompt_sha256": digest(prompt.encode("utf-8")),
    }


def _prepare_overlay(raw: bytes, alt: str) -> tuple[bytes, dict[str, Any]]:
    """Crop the white canvas, key it to alpha, and wrap the raster as a transparent SVG overlay."""
    try:
        from PIL import Image, ImageChops, ImageStat  # type: ignore
    except Exception as exc:
        raise IllustrationError("Pillow is required; install requirements-visual.txt") from exc
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise IllustrationUnavailable("Generated image could not be decoded") from exc
    white = Image.new("RGB", image.size, "white")
    mask = ImageChops.difference(image, white).convert("L").point(lambda p: 255 if p > 7 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise IllustrationUnavailable("Generated image is blank")
    left, top, right, bottom = bbox
    pad = max(18, int(max(right - left, bottom - top) * 0.06))
    box = (
        max(0, left - pad), max(0, top - pad),
        min(image.width, right + pad), min(image.height, bottom + pad),
    )
    cropped = image.crop(box)
    if ImageStat.Stat(cropped.convert("L")).stddev[0] < 2:
        raise IllustrationUnavailable("Generated image has insufficient contrast")

    gray = cropped.convert("L")
    alpha = gray.point(lambda p: max(0, min(255, (250 - p) * 6)))
    rgba = cropped.convert("RGBA")
    rgba.putalpha(alpha)
    png_out = io.BytesIO()
    rgba.save(png_out, "PNG", optimize=True)
    png = png_out.getvalue()
    encoded = base64.b64encode(png).decode("ascii")
    width, height = cropped.size
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" data-study-sketch="1" '
        'data-transparent-canvas="1" data-generated-illustration="1">\n'
        f'<title>{html.escape(alt)}</title>\n'
        f'<image width="{width}" height="{height}" href="data:image/png;base64,{encoded}"/>\n'
        '</svg>\n'
    ).encode("utf-8")
    return svg, {
        "crop_box": list(box),
        "output_size": [width, height],
        "embedded_png_sha256": digest(png),
        "transparent_overlay": True,
    }


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def _existing(
    course: Path, unit_id: str, spec: dict[str, Any], asset_rel: str,
    spec_rel: str, asset_path: Path, spec_path: Path, spec_sha: str,
) -> dict[str, Any] | None:
    key = derived_key(spec["id"])
    record = load_registry(course).get("figures", {}).get(key)
    if not isinstance(record, dict):
        return None
    meta = record.get("illustration_generation")
    exact = (
        isinstance(meta, dict)
        and meta.get("generator") == GENERATOR
        and meta.get("version") == VERSION
        and meta.get("style_version") == STYLE_VERSION
        and meta.get("spec") == spec_rel
        and meta.get("spec_sha256") == spec_sha
        and record.get("unit_id") == unit_id
        and record.get("asset") == asset_rel
        and record.get("kind") == "illustration"
        and asset_path.is_file()
        and spec_path.is_file()
        and record.get("asset_sha256") == sha256(asset_path)
        and sha256(spec_path) == spec_sha
    )
    if not exact:
        raise IllustrationError(f"Figure id already exists with different content: {key}")
    return {"ok": True, "created": False, "key": key, "record": record}


def generate_and_register(
    course: Path, unit_value: str, spec_value: Any, *, concept_id: str,
) -> dict[str, Any]:
    spec = validate_spec(spec_value)
    unit = resolve_unit(course, unit_value)
    unit_id = str(unit.get("unit_id") or "")
    if not unit_id:
        raise IllustrationError(f"Could not resolve unit: {unit_value}")
    base = unit_root(course, unit_id) if has_unit_layout(course) else course
    asset_rel = f"assets/figures/{spec['id']}.illustration.svg"
    spec_rel = f"assets/figures/{spec['id']}.illustration.json"
    asset_path, spec_path = (base / asset_rel).resolve(), (base / spec_rel).resolve()
    spec_bytes = (json.dumps(spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    spec_sha = digest(spec_bytes)
    existing = _existing(course, unit_id, spec, asset_rel, spec_rel, asset_path, spec_path, spec_sha)
    if existing:
        return existing
    if asset_path.exists() or spec_path.exists():
        raise IllustrationError("Illustration path already exists with unregistered content")

    raw, provider = _cloudflare(spec)
    overlay, preparation = _prepare_overlay(raw, spec["alt"])
    _atomic(spec_path, spec_bytes)
    _atomic(asset_path, overlay)
    try:
        data = load_registry(course)
        figures = data["figures"]
        key = derived_key(spec["id"])
        if key in figures:
            raise IllustrationError(f"Figure id collision: {key}")
        if any(
            isinstance(row, dict)
            and row.get("asset") == asset_rel
            and (not has_unit_layout(course) or record_unit_id(course, row) == unit_id)
            for row in figures.values()
        ):
            raise IllustrationError(f"Figure asset collision: {asset_rel}")
        record = {
            "id": key,
            "unit_id": unit_id,
            "unit": unit.get("label") or unit_value,
            "concepts": [concept_id],
            "kind": "illustration",
            "role": "supporting",
            "description": spec["caption"],
            "learner_focus": [],
            "asset": asset_rel,
            "asset_sha256": sha256(asset_path),
            "origin": "derived",
            "based_on": spec["based_on"],
            "visual_treatment": "reinterpret",
            "illustration_generation": {
                "method": "generated-illustration",
                "generator": GENERATOR,
                "version": VERSION,
                "style_version": STYLE_VERSION,
                "spec": spec_rel,
                "spec_sha256": spec_sha,
                **provider,
                **preparation,
            },
        }
        figures[key] = record
        issues = registry_issues(course, data)
        if issues:
            figures.pop(key, None)
            raise IllustrationError(json.dumps({"issues": issues}, ensure_ascii=False))
        save_registry(course, data)
    except Exception:
        for path in (asset_path, spec_path):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return {"ok": True, "created": True, "key": key, "record": record}
