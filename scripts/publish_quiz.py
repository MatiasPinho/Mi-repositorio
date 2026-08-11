#!/usr/bin/env python3
"""Atomically publish an immutable quiz JSON/HTML pair."""
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
        return resolved.as_posix()


def _stage(destination: Path, payload: bytes) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=".study-quiz-", suffix=".tmp", dir=destination.parent)
    temp_path = Path(raw)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if temp_path.read_bytes() != payload:
            raise OSError(f"staged-bytes-mismatch:{destination}")
        return temp_path
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _restore(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
        return
    staged = _stage(path, previous)
    os.replace(staged, path)


def publish_quiz(
    source_json: Path,
    source_html: Path,
    destination_json: Path,
    destination_html: Path,
    report_path: Path,
) -> dict[str, Any]:
    sources = {"json": source_json.resolve(), "html": source_html.resolve()}
    destinations = {"json": destination_json.resolve(), "html": destination_html.resolve()}
    for role, path in sources.items():
        if not path.is_file():
            raise SystemExit(f"Missing {role} source: {path}")

    payloads = {role: path.read_bytes() for role, path in sources.items()}
    previous = {
        role: (path.read_bytes() if path.is_file() else None)
        for role, path in destinations.items()
    }
    staged: dict[str, Path] = {}

    try:
        for role, destination in destinations.items():
            staged[role] = _stage(destination, payloads[role])
        replaced: list[str] = []
        try:
            for role in ("json", "html"):
                os.replace(staged[role], destinations[role])
                replaced.append(role)
            for role, destination in destinations.items():
                if destination.read_bytes() != payloads[role]:
                    raise OSError(f"published-bytes-mismatch:{role}")
            for role, source in sources.items():
                if source.read_bytes() != payloads[role]:
                    raise OSError(f"publication-source-mutated:{role}")
        except Exception:
            for role in reversed(replaced):
                _restore(destinations[role], previous[role])
            raise
    finally:
        for temp_path in staged.values():
            temp_path.unlink(missing_ok=True)

    files = []
    for role in ("json", "html"):
        source_digest = sha256_bytes(payloads[role])
        destination_digest = sha256_file(destinations[role])
        files.append({
            "role": role,
            "source": display_path(sources[role]),
            "destination": display_path(destinations[role]),
            "source_sha256": source_digest,
            "published_sha256": destination_digest,
            "destination_sha256": destination_digest,
            "source_bytes": len(payloads[role]),
            "bytes": destinations[role].stat().st_size,
            "transform": "identity",
            "resource_rewrites": [],
        })

    report = {
        "version": 3,
        "ok": all(row["source_sha256"] == row["destination_sha256"] for row in files),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    if not report["ok"]:
        raise OSError("quiz-publication-hash-mismatch")
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Atomically publish validated quiz JSON and HTML")
    ap.add_argument("--json", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--dest-json", required=True)
    ap.add_argument("--dest-html", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    report = publish_quiz(
        Path(args.json),
        Path(args.html),
        Path(args.dest_json),
        Path(args.dest_html),
        Path(args.report),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
