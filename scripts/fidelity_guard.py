#!/usr/bin/env python3
"""Deterministic prose guard for unresolved canonical conflicts.

The canonical resolver may intentionally leave competing evidence unresolved.
This guard prevents common winner-selection phrasing from slipping into a
summary before academic review. It is deliberately narrow: it catches explicit
resolution language around source disagreements and leaves nuanced semantic
judgment to the independent academic reviewer.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

CONFLICT_CONTEXT = re.compile(
    r"\b(fuente|fuentes|apunte|apuntes|diapositiva|clase|c[aá]tedra|profesor|material|materiales|oficial|conflicto|discrepancia|versi[oó]n|formulaci[oó]n|evidencia|source|sources|slide|notes|class|teacher|official|material|materials|conflict|discrepancy|version|formulation|evidence)\b",
    re.I,
)
WINNER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("source-majority", re.compile(r"\b(?:aparece|aparecen)\s+en\s+(?:m[aá]s|la\s+mayor[ií]a\s+de)\s+(?:las\s+)?fuentes\b", re.I)),
    ("source-majority", re.compile(r"\b(?:more|most)\s+sources\b|\bmajority\s+of\s+(?:the\s+)?sources\b", re.I)),
    ("follow-this-version", re.compile(r"\b(?:la|el)\s+que\s+se\s+(?:sigue|usa)\s+(?:aqu[ií]|en\s+la\s+materia)\b", re.I)),
    ("follow-this-version", re.compile(r"\b(?:versi[oó]n|formulaci[oó]n|opci[oó]n)\b.{0,100}\b(?:se\s+sigue|se\s+usa|usamos|preferida|correcta)\b", re.I)),
    ("follow-this-version", re.compile(r"\b(?:version|formulation|option)\b.{0,100}\b(?:we\s+follow|we\s+use|preferred|correct)\b", re.I)),
    ("pick-winner", re.compile(r"\b(?:nos\s+quedamos|tomamos)\s+con\b|\b(?:prevalece|gana)\b", re.I)),
    ("pick-winner", re.compile(r"\b(?:we\s+choose|we\s+go\s+with|prevails|wins)\b", re.I)),
    (
        "dismiss-competing-evidence",
        re.compile(
            r"\b(?:es|ser[ií]a|se\s+trata\s+de)\s+(?:un\s+)?(?:error(?:\s+de\s+edici[oó]n)?|errata)\b"
            r"|\b(?:es|resulta|queda)\s+(?:incorrect[oa]|equivocad[oa]|inv[aá]lid[oa])\b"
            r"|\b(?:debe|hay\s+que)\s+(?:ignorarse|descartarse)\b",
            re.I,
        ),
    ),
    (
        "dismiss-competing-evidence",
        re.compile(
            r"\b(?:is|would\s+be)\s+(?:an?\s+)?(?:editing\s+error|erratum|mistake)\b"
            r"|\b(?:is|becomes)\s+(?:incorrect|wrong|invalid)\b"
            r"|\b(?:must|should)\s+be\s+(?:ignored|discarded)\b",
            re.I,
        ),
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _blocks(text: str) -> list[tuple[int, str]]:
    rows = text.splitlines()
    blocks: list[tuple[int, str]] = []
    start = 1
    current: list[str] = []
    for idx, line in enumerate(rows, 1):
        if line.strip():
            if not current:
                start = idx
            current.append(line.strip())
            continue
        if current:
            blocks.append((start, " ".join(current)))
            current = []
    if current:
        blocks.append((start, " ".join(current)))
    return blocks


def check(markdown: str, ledger: dict[str, Any]) -> dict[str, Any]:
    constraints = ledger.get("constraints", []) if isinstance(ledger, dict) else []
    unresolved = [
        row for row in constraints
        if isinstance(row, dict) and str(row.get("status") or "") == "unresolved"
    ]
    issues: list[dict[str, Any]] = []
    if unresolved:
        for line, block in _blocks(markdown):
            if not CONFLICT_CONTEXT.search(block):
                continue
            for code, pattern in WINNER_PATTERNS:
                match = pattern.search(block)
                if not match:
                    continue
                issues.append({
                    "code": f"unresolved-conflict-{code}",
                    "line": line,
                    "match": match.group(0),
                    "message": "Unresolved canonical evidence cannot be resolved by prose/source majority; attribute competing evidence without picking a winner.",
                    "snippet": block[:320],
                })
                break
    return {
        "version": 1,
        "ok": not issues,
        "unresolved_constraints": len(unresolved),
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Hard-fail explicit winner language for unresolved summary conflicts")
    ap.add_argument("--markdown", required=True)
    ap.add_argument("--constraints", required=True)
    ap.add_argument("--write")
    args = ap.parse_args()
    try:
        markdown = Path(args.markdown).read_text(encoding="utf-8")
        ledger = _load_json(Path(args.constraints))
        report = check(markdown, ledger)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {"version": 1, "ok": False, "issues": [{"code": "guard-input-invalid", "message": str(exc)}]}
    if args.write:
        out = Path(args.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
