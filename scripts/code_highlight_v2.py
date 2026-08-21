#!/usr/bin/env python3
"""Deterministically complete syntax highlighting for study HTML.

The core renderer intentionally has a small dependency-free highlighter.  This
post-render pass extends the same semantic span vocabulary to languages that
showed up in real course material (Java, BASIC and Prolog) without pulling a
browser/highlighter dependency into the pipeline.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

try:
    from . import render_study
except ImportError:
    import render_study  # type: ignore


def _words(value: str) -> frozenset[str]:
    return frozenset(value.split())


EXTRA_PROFILES = {
    "java": {
        "casefold": False,
        "keywords": _words(
            "abstract assert break case catch class const continue default do else enum extends final finally "
            "for goto if implements import instanceof interface native new package private protected public "
            "return static strictfp super switch synchronized this throw throws transient try volatile while "
            "true false null"
        ),
        "types": _words(
            "boolean byte char double float int long short void String Object Integer Double Float Boolean Character"
        ),
        "builtins": _words("System Math Arrays Collections List Map Set Scanner println print printf"),
        "declarations": _words("class enum interface"),
        "line_comments": ("//",),
        "block_comments": True,
    },
    "basic": {
        "casefold": True,
        "keywords": _words(
            "as call case const data dim do each else elseif end endif exit for function get gosub goto if input "
            "let loop next on print read rem return select step sub then to until while wend"
        ),
        "types": _words("boolean byte currency date double integer long single string variant"),
        "builtins": _words("abs chr int left len mid right rnd sgn sqr str val"),
        "declarations": _words("const dim function sub"),
        "line_comments": ("'", "REM", "rem"),
        "block_comments": False,
    },
    "prolog": {
        "casefold": False,
        "keywords": _words("is mod div not true false fail once repeat"),
        "types": frozenset(),
        "builtins": _words("asserta assertz consult findall read retract write writeln nl member append length"),
        "declarations": frozenset(),
        "line_comments": ("%",),
        "block_comments": True,
    },
}

ALIASES = {
    "vb": "basic",
    "visualbasic": "basic",
    "visual-basic": "basic",
    "qbasic": "basic",
    "gprolog": "prolog",
}

_CODE_RE = re.compile(
    r'<code\s+class="(?P<class>[^"]*\blanguage-(?P<lang>[A-Za-z0-9_+.#-]+)[^"]*)">(?P<body>.*?)</code>',
    re.IGNORECASE | re.DOTALL,
)


def install_profiles() -> None:
    for name, profile in EXTRA_PROFILES.items():
        render_study.SYNTAX_PROFILES.setdefault(name, profile)
    render_study.LANGUAGE_ALIASES.update(ALIASES)


def transform(text: str) -> tuple[str, dict]:
    install_profiles()
    highlighted: list[str] = []
    unsupported: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        classes = match.group("class").split()
        language = match.group("lang").lower()
        if "syntax-highlighted" in classes:
            return match.group(0)
        source = html.unescape(match.group("body"))
        rendered, resolved = render_study.highlight_code(source, language)
        if resolved is None:
            unsupported.add(language)
            return match.group(0)
        classes.append("syntax-highlighted")
        highlighted.append(resolved)
        return f'<code class="{html.escape(" ".join(classes), quote=True)}">{rendered}</code>'

    output = _CODE_RE.sub(replace, text)
    report = {
        "version": 1,
        "ok": True,
        "highlighted_blocks": len(highlighted),
        "languages": sorted(set(highlighted)),
        "unsupported_languages": sorted(unsupported),
        "warnings": [f"syntax-highlighting-unsupported:{name}" for name in sorted(unsupported)],
    }
    return output, report


def main() -> int:
    ap = argparse.ArgumentParser(description="Complete deterministic code highlighting in rendered study HTML")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--report")
    args = ap.parse_args()
    inp = Path(args.input).resolve()
    out = Path(args.output).resolve()
    if inp.parent != out.parent:
        raise SystemExit("code highlight transform requires input/output in the same directory")
    try:
        transformed, report = transform(inp.read_text(encoding="utf-8"))
        out.write_text(transformed, encoding="utf-8")
        if args.report:
            Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
