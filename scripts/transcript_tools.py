#!/usr/bin/env python3
"""Deterministic transcript helpers.

Parses TXT/MD/SRT/VTT transcripts, preserves timestamps when present, and
surfaces *candidate* teacher-emphasis cues. It never upgrades those cues to
confirmed academic rules; semantic interpretation is left to the study agent.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SUPPORTED = {".txt", ".md", ".srt", ".vtt"}
IGNORED = {"README.md", ".DS_Store", "Thumbs.db"}

CUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("exam-cue", re.compile(r"\b(esto\s+entra|entra\s+en|para\s+el\s+(parcial|final|examen)|lo\s+(pueden|podemos)\s+tomar|se\s+(toma|eval[uú]a)|preguntar\s+en\s+el\s+(parcial|final|examen))\b", re.I)),
    ("excluded-cue", re.compile(r"\b(no\s+entra|esto\s+no\s+entra|no\s+se\s+toma|no\s+lo\s+voy\s+a\s+tomar|queda\s+afuera)\b", re.I)),
    ("important", re.compile(r"\b(importante|muy\s+importante|presten\s+atenci[oó]n|ojo\s+con|recuerden|clave|fundamental)\b", re.I)),
    ("common-error", re.compile(r"\b(error\s+t[ií]pico|error\s+com[uú]n|se\s+suelen\s+equivocar|no\s+confundan|cuidado\s+con)\b", re.I)),
    ("question-pattern", re.compile(r"\b(suelen\s+preguntar|les\s+puedo\s+preguntar|una\s+pregunta\s+t[ií]pica|esto\s+se\s+pregunta)\b", re.I)),
]


def parse_time(value: str) -> float | None:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    except ValueError:
        return None
    return None


def fmt_time(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    millis = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if millis:
        return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def read_transcript_text(path: Path) -> str:
    """Decode common transcript exports without silently mangling Windows files."""
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def extract_vtt_speaker(text: str) -> str | None:
    match = re.search(r"<v(?:\.[^ >]+)?\s+([^>]+)>", text, re.I)
    return match.group(1).strip() if match else None


def parse_srt_vtt(text: str) -> list[dict[str, Any]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    segments: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.upper() == "WEBVTT" or line.startswith("NOTE"):
            i += 1
            continue
        if line.isdigit() and i + 1 < len(lines) and "-->" in lines[i + 1]:
            i += 1
            line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        left, right = [x.strip().split()[0] for x in line.split("-->", 1)]
        start, end = parse_time(left), parse_time(right)
        i += 1
        body: list[str] = []
        while i < len(lines) and lines[i].strip():
            body.append(lines[i].strip())
            i += 1
        raw_content = " ".join(body)
        speaker = extract_vtt_speaker(raw_content)
        content = clean_text(raw_content)
        if content:
            segment = {"start": fmt_time(start), "end": fmt_time(end), "start_seconds": start, "end_seconds": end, "text": content}
            if speaker:
                segment["speaker"] = speaker
            segments.append(segment)
    return segments


def parse_plain(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        # Common exported transcript forms: [00:12:34] text / 00:12:34 text
        m = re.match(r"^\[?(\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d{1,3})?)\]?\s*[-–—:]?\s*(.*)$", line)
        start = None
        body = line
        if m:
            start = parse_time(m.group(1))
            body = m.group(2).strip()
        body = clean_text(body)
        if body:
            segments.append({"start": fmt_time(start), "end": None, "start_seconds": start, "end_seconds": None, "text": body})
    return segments


def parse_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() not in SUPPORTED:
        raise SystemExit(f"Unsupported transcript extension: {path.suffix}. Supported: {', '.join(sorted(SUPPORTED))}")
    text = read_transcript_text(path)
    return parse_srt_vtt(text) if path.suffix.lower() in {".srt", ".vtt"} else parse_plain(text)


def cue_candidates(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seg in segments:
        cue_types = [name for name, pattern in CUE_PATTERNS if pattern.search(seg.get("text", ""))]
        if cue_types:
            rows.append({
                "start": seg.get("start"),
                "end": seg.get("end"),
                "cue_types": cue_types,
                "text": seg.get("text", ""),
                "speaker": seg.get("speaker"),
                "status": "candidate-only",
            })
    return rows


def resolve(course: Path, value: str | None) -> list[Path]:
    base = course / "fuentes" / "transcripciones"
    if value:
        candidate = course / "fuentes" / value
        if not candidate.exists():
            candidate = base / value
        if not candidate.exists() or not candidate.is_file():
            raise SystemExit(f"Transcript not found: {value}")
        return [candidate]
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file() and p.name not in IGNORED and p.suffix.lower() in SUPPORTED)


def inspect(path: Path, course: Path) -> dict[str, Any]:
    segments = parse_file(path)
    timed = [s for s in segments if s.get("start_seconds") is not None]
    duration = None
    if timed:
        candidates = [s.get("end_seconds") for s in timed if s.get("end_seconds") is not None]
        if candidates:
            duration = max(candidates)
        else:
            duration = max(s.get("start_seconds") or 0 for s in timed)
    return {
        "file": path.relative_to(course / "fuentes").as_posix(),
        "format": path.suffix.lower().lstrip("."),
        "segments": len(segments),
        "timestamped_segments": len(timed),
        "duration": fmt_time(duration),
        "cue_candidates": cue_candidates(segments),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("--course", required=True)
    p.add_argument("--file", help="Path relative to fuentes/ or transcripciones/")
    p.add_argument("--write", action="store_true", help="Persist normalized transcript metadata under .study/transcripts/")
    args = ap.parse_args()

    course = Path(args.course)
    paths = resolve(course, args.file)
    rows = [inspect(path, course) for path in paths]
    if args.write:
        out_dir = course / ".study" / "transcripts"
        out_dir.mkdir(parents=True, exist_ok=True)
        for path, row in zip(paths, rows):
            rel = path.relative_to(course / "fuentes").as_posix()
            safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", rel) + ".json"
            (out_dir / safe).write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
