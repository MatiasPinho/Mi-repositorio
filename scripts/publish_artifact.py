#!/usr/bin/env python3
"""Atomically publish validated study Markdown/HTML with byte-for-byte verification."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


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

    payloads = {role: path.read_bytes() for role, path in sources.items()}
    staged: dict[str, Path] = {}
    previous: dict[str, bytes | None] = {
        role: (path.read_bytes() if path.is_file() else None)
        for role, path in destinations.items()
    }

    try:
        for role in ("markdown", "html"):
            staged[role] = _stage(destinations[role], payloads[role])

        replaced: list[str] = []
        try:
            for role in ("markdown", "html"):
                os.replace(staged[role], destinations[role])
                replaced.append(role)
            for role in ("markdown", "html"):
                expected = sha256_bytes(payloads[role])
                actual = sha256_file(destinations[role])
                if actual != expected:
                    raise OSError(f"published-hash-mismatch:{role}")
        except Exception:
            for role in reversed(replaced):
                _restore(destinations[role], previous[role])
            raise
    finally:
        for temp_path in staged.values():
            temp_path.unlink(missing_ok=True)

    files = []
    for role in ("markdown", "html"):
        digest = sha256_bytes(payloads[role])
        files.append({
            "role": role,
            "source": display_path(sources[role]),
            "destination": display_path(destinations[role]),
            "source_sha256": digest,
            "destination_sha256": sha256_file(destinations[role]),
            "bytes": len(payloads[role]),
        })

    report = {
        "version": 1,
        "ok": all(row["source_sha256"] == row["destination_sha256"] for row in files),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    atomic_write_bytes(report_path.resolve(), (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Atomically publish validated study Markdown and HTML")
    ap.add_argument("--markdown", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--dest-markdown", required=True)
    ap.add_argument("--dest-html", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    report = publish_pair(
        Path(args.markdown),
        Path(args.html),
        Path(args.dest_markdown),
        Path(args.dest_html),
        Path(args.report),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
