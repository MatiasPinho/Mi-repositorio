#!/usr/bin/env python3
"""Atomically publish validated study Markdown/HTML with relocation-safe local assets.

The staged run lives deeper than the published artifact. Relative image URLs that
are valid inside ``.study/runs/<run-id>/`` therefore cannot be copied verbatim to
``resumenes/``. Publication deterministically rebases only local image references
for the destination while keeping the validated run sources byte-for-byte
immutable. Responsive Visual System V2 ``<source srcset>`` resources participate in
the same relocation contract as ordinary ``<img src>`` assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
_HTML_IMAGE_RE = re.compile(r'(<img\b[^>]*\bsrc=")([^"]+)(")', re.I)
_HTML_SRCSET_RE = re.compile(r'(<source\b[^>]*\bsrcset=")([^"]+)(")', re.I)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def atomic_write_bytes(destination: Path, data: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=".study-publish-", suffix=".tmp", dir=destination.parent)
    temp_path = Path(raw)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if sha256_file(temp_path) != sha256_bytes(data):
            raise OSError(f"staged-hash-mismatch:{destination}")
        os.replace(temp_path, destination)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _stage(destination: Path, data: bytes) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=".study-publish-", suffix=".tmp", dir=destination.parent)
    temp_path = Path(raw)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    if sha256_file(temp_path) != sha256_bytes(data):
        temp_path.unlink(missing_ok=True)
        raise OSError(f"staged-hash-mismatch:{destination}")
    return temp_path


def _restore(destination: Path, previous: bytes | None) -> None:
    if previous is None:
        destination.unlink(missing_ok=True)
    else:
        atomic_write_bytes(destination, previous)


def _is_remote_or_embedded(src: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://", src, re.I)) or src.startswith(("data:", "#"))


def _rebase_local_ref(src: str, source_parent: Path, destination_parent: Path) -> tuple[str, Path] | None:
    if _is_remote_or_embedded(src):
        return None
    target = (source_parent / src).resolve()
    if not target.is_file():
        raise OSError(f"publication-resource-missing:{src}:{target}")
    rebased = os.path.relpath(target, destination_parent.resolve()).replace(os.sep, "/")
    return rebased, target


def _rewrite_markdown_images(
    data: bytes,
    source: Path,
    destination: Path,
) -> tuple[bytes, list[dict[str, str]]]:
    text = data.decode("utf-8")
    rewrites: list[dict[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        alt, src, title = match.group(1), match.group(2), match.group(3)
        resolved = _rebase_local_ref(src, source.parent, destination.parent)
        if resolved is None:
            return match.group(0)
        rebased, target = resolved
        rewrites.append({
            "original": src,
            "published": rebased,
            "target": display_path(target),
        })
        title_part = f' "{title}"' if title else ""
        return f"![{alt}]({rebased}{title_part})"

    return _MD_IMAGE_RE.sub(replace, text).encode("utf-8"), rewrites


def _rewrite_html_images(
    data: bytes,
    source: Path,
    destination: Path,
) -> tuple[bytes, list[dict[str, str]]]:
    text = data.decode("utf-8")
    rewrites: list[dict[str, str]] = []

    def rewrite_one(src: str) -> str:
        resolved = _rebase_local_ref(src, source.parent, destination.parent)
        if resolved is None:
            return src
        rebased, target = resolved
        rewrites.append({
            "original": src,
            "published": rebased,
            "target": display_path(target),
        })
        return rebased

    def replace_img(match: re.Match[str]) -> str:
        return f"{match.group(1)}{rewrite_one(match.group(2))}{match.group(3)}"

    def replace_srcset(match: re.Match[str]) -> str:
        candidates = []
        for raw in match.group(2).split(","):
            candidate = raw.strip()
            if not candidate:
                continue
            parts = candidate.split()
            src = parts[0]
            descriptor = " " + " ".join(parts[1:]) if len(parts) > 1 else ""
            candidates.append(rewrite_one(src) + descriptor)
        return f"{match.group(1)}{', '.join(candidates)}{match.group(3)}"

    text = _HTML_IMAGE_RE.sub(replace_img, text)
    text = _HTML_SRCSET_RE.sub(replace_srcset, text)
    return text.encode("utf-8"), rewrites


def _verify_published_resources(destination: Path, rewrites: list[dict[str, str]]) -> None:
    for row in rewrites:
        published = str(row["published"])
        target_value = Path(row["target"])
        expected = (ROOT / target_value).resolve() if not target_value.is_absolute() else target_value.resolve()
        actual = (destination.parent / published).resolve()
        if actual != expected:
            raise OSError(f"publication-resource-target-changed:{published}:{actual}!={expected}")
        if not actual.is_file():
            raise OSError(f"publication-resource-missing-after-write:{published}:{actual}")


def publish_pair(
    markdown_source: Path,
    html_source: Path,
    markdown_destination: Path,
    html_destination: Path,
    report_path: Path,
) -> dict[str, Any]:
    sources = {
        "markdown": markdown_source.resolve(),
        "html": html_source.resolve(),
    }
    destinations = {
        "markdown": markdown_destination.resolve(),
        "html": html_destination.resolve(),
    }
    for role, path in sources.items():
        if not path.is_file():
            raise SystemExit(f"Missing {role} source: {path}")

    source_payloads = {role: path.read_bytes() for role, path in sources.items()}
    markdown_payload, markdown_rewrites = _rewrite_markdown_images(
        source_payloads["markdown"], sources["markdown"], destinations["markdown"]
    )
    html_payload, html_rewrites = _rewrite_html_images(
        source_payloads["html"], sources["html"], destinations["html"]
    )
    published_payloads = {"markdown": markdown_payload, "html": html_payload}
    rewrites = {"markdown": markdown_rewrites, "html": html_rewrites}

    previous = {
        role: (path.read_bytes() if path.is_file() else None)
        for role, path in destinations.items()
    }
    staged: dict[str, Path] = {}

    try:
        for role, path in destinations.items():
            staged[role] = _stage(path, published_payloads[role])

        replaced: list[str] = []
        try:
            for role in ("markdown", "html"):
                os.replace(staged[role], destinations[role])
                replaced.append(role)
            for role, path in destinations.items():
                expected = sha256_bytes(published_payloads[role])
                actual = sha256_file(path)
                if actual != expected:
                    raise OSError(f"published-hash-mismatch:{role}")
            _verify_published_resources(destinations["markdown"], rewrites["markdown"])
            _verify_published_resources(destinations["html"], rewrites["html"])
            for role, source in sources.items():
                if source.read_bytes() != source_payloads[role]:
                    raise OSError(f"publication-source-mutated:{role}")
        except Exception:
            for role in reversed(replaced):
                _restore(destinations[role], previous[role])
            raise
    finally:
        for temp_path in staged.values():
            temp_path.unlink(missing_ok=True)

    files = []
    for role in ("markdown", "html"):
        source_digest = sha256_bytes(source_payloads[role])
        published_digest = sha256_bytes(published_payloads[role])
        files.append({
            "role": role,
            "source": display_path(sources[role]),
            "destination": display_path(destinations[role]),
            "source_sha256": source_digest,
            "published_sha256": published_digest,
            "destination_sha256": sha256_file(destinations[role]),
            "source_bytes": len(source_payloads[role]),
            "bytes": len(published_payloads[role]),
            "transform": "rebase-local-image-refs-v1" if rewrites[role] else "identity",
            "resource_rewrites": rewrites[role],
        })

    report = {
        "version": 3,
        "ok": all(
            row["published_sha256"] == row["destination_sha256"]
            and row["source_sha256"] == sha256_file(_resolve_source_from_row(row, sources))
            for row in files
        ),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    atomic_write_bytes(report_path.resolve(), (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return report


def _resolve_source_from_row(row: dict[str, Any], sources: dict[str, Path]) -> Path:
    role = str(row.get("role", ""))
    if role not in sources:
        raise OSError(f"publication-role-invalid:{role}")
    return sources[role]


def main() -> int:
    ap = argparse.ArgumentParser(description="Atomically publish validated study Markdown and HTML")
    ap.add_argument("--markdown", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--dest-markdown", required=True)
    ap.add_argument("--dest-html", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    try:
        report = publish_pair(
            Path(args.markdown),
            Path(args.html),
            Path(args.dest_markdown),
            Path(args.dest_html),
            Path(args.report),
        )
    except OSError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), flush=True)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
