#!/usr/bin/env python3
"""Render the system's student-facing Markdown dialect into a static HTML study document.

The document has no framework/runtime dependency. External webfonts are a progressive
enhancement only: full system fallbacks keep every artifact readable offline.
"""
from __future__ import annotations

import argparse
import html
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "assets" / "study-theme.css"

FONT_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">"""

CALLOUT = {
    "DEFINITION": ("definition", "Definición"),
    "CONCEPT": ("definition", "Concepto"),
    "EXAMPLE": ("example", "Ejemplo"),
    "WARNING": ("warning", "Cuidado"),
    "ERROR": ("danger", "Error típico"),
    "EXAM": ("exam", "Para evaluación"),
    "CONNECTION": ("connection", "Relación"),
    "RECALL": ("recall", "Recuperación"),
    "REMEMBER": ("definition", "Qué retener"),
}


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ]+", "-", text.lower()).strip("-")
    return text or "section"


def inline(text: str) -> str:
    """Escape first, then allow the tiny Markdown subset used inside blocks."""
    s = html.escape(text, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        s,
    )
    return s


def table_block(lines: list[str]) -> str:
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return ""
    head = rows[0]
    body = rows[2:]
    out = ["<table><thead><tr>"] + [f"<th>{inline(c)}</th>" for c in head] + ["</tr></thead><tbody>"]
    for row in body:
        out.append("<tr>")
        out.extend(f"<td>{inline(c)}</td>" for c in row)
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def is_table_sep(line: str) -> bool:
    if "|" not in line:
        return False
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def caption_comment(line: str) -> str | None:
    """Optional portable caption metadata: <!-- caption: ... -->"""
    m = re.fullmatch(r"\s*<!--\s*caption:\s*(.*?)\s*-->\s*", line, re.I)
    return m.group(1).strip() if m else None


def consume_caption(lines: list[str], index: int) -> tuple[str | None, int]:
    """Consume an optional caption after a table/code block, tolerating blank lines."""
    j = index
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j < len(lines):
        cap = caption_comment(lines[j])
        if cap is not None:
            return cap, j + 1
    return None, index


def validate_caption_comments(text: str) -> list[str]:
    """Reject caption metadata that is not attached to a table or fenced code block."""
    lines = text.replace("\r\n", "\n").split("\n")
    issues: list[str] = []
    for idx, line in enumerate(lines):
        if caption_comment(line) is None:
            continue
        j = idx - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        prev = lines[j].strip() if j >= 0 else ""
        if prev.startswith("```") or ("|" in prev and prev.strip().startswith("|")):
            continue
        issues.append(f"orphan-caption:line-{idx + 1}")
    return issues


def _row(body: str, mark: str = "", extra_class: str = "") -> str:
    cls = "row" + (f" {extra_class}" if extra_class else "")
    return f'<div class="{cls}"><div class="mark">{mark}</div><div class="body">{body}</div></div>'


def render_markdown(
    text: str,
    scope: str = "",
    *,
    wrap_prose: bool = True,
) -> tuple[str, list[tuple[int, str, str]], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []
    title = "Apunte de estudio"
    i = 0
    used_ids: dict[str, int] = {}
    waiting_for_lede = False

    def heading_id(label: str) -> str:
        base = slugify(re.sub(r"[*_`]", "", label))
        n = used_ids.get(base, 0) + 1
        used_ids[base] = n
        return base if n == 1 else f"{base}-{n}"

    def prose_block(inner_html: str, *, mark: str = "", extra_class: str = "") -> str:
        return _row(inner_html, mark=mark, extra_class=extra_class) if wrap_prose else inner_html

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if line.startswith("```"):
            lang = line[3:].strip()
            buf: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1 if i < len(lines) else 0
            cls = f' class="language-{html.escape(lang, quote=True)}"' if lang else ""
            code_html = f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>"
            cap, new_i = consume_caption(lines, i)
            if cap:
                code_html += f'<div class="code-caption"><span>{inline(cap)}</span></div>'
                i = new_i
            out.append(code_html)
            continue

        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            label = m.group(2).strip()
            hid = heading_id(label)
            clean = re.sub(r"[*_`]", "", label)

            if level == 1 and title == "Apunte de estudio":
                title = clean
                display_label = label
                if scope:
                    pat = re.compile(r"^\s*" + re.escape(scope) + r"\s*(?:[:—–-]\s*)?", re.I)
                    stripped = pat.sub("", clean).strip()
                    if stripped:
                        display_label = stripped
                raw_scope = scope.strip()
                if re.match(r"^unidad\s+\d+", raw_scope, re.I):
                    chapter_mark = re.sub(r"^unidad", "Capítulo", raw_scope, flags=re.I)
                else:
                    chapter_mark = raw_scope
                mark = inline(chapter_mark) if chapter_mark else ""
                out.append(
                    '<header class="study-header">'
                    f'<div class="mark">{mark}</div>'
                    '<div class="body">'
                    f'<h1 id="{hid}">{inline(display_label)}</h1>'
                    '</div></header>'
                )
                waiting_for_lede = True
            elif level == 2 and wrap_prose:
                out.append(f'<div class="section-head"><div class="num"></div><h2 id="{hid}">{inline(label)}</h2></div>')
                toc.append((level, hid, clean))
            elif level == 3 and wrap_prose:
                out.append(
                    _row(
                        f'<h3 id="{hid}">{inline(label)}</h3>',
                        extra_class="subsection-head",
                    )
                )
                toc.append((level, hid, clean))
            elif level == 4 and wrap_prose:
                out.append(_row(f'<h4 id="{hid}">{inline(label)}</h4>', extra_class="minor-head"))
            else:
                out.append(f'<h{level} id="{hid}">{inline(label)}</h{level}>')
                if level in (2, 3):
                    toc.append((level, hid, clean))
            i += 1
            continue

        cm = re.match(r"^>\s*\[!([A-Z]+)\](?:\s+(.+))?\s*$", line.strip())
        if cm and cm.group(1) in CALLOUT:
            callout_type = cm.group(1)
            kind, semantic_label = CALLOUT[callout_type]
            custom_title = (cm.group(2) or "").strip()
            buf: list[str] = []
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            body, _toc, _title = render_markdown("\n".join(buf), scope="", wrap_prose=False) if buf else ("", [], "")

            term_types = {"DEFINITION", "CONCEPT", "CONNECTION"}
            redundant_title = custom_title.casefold() == semantic_label.casefold() if custom_title else False
            term = (
                f'<p class="term">{inline(custom_title)}</p>'
                if custom_title and callout_type in term_types and not redundant_title
                else ""
            )

            if callout_type == "RECALL":
                prompt = re.sub(r"^<p>", '<p class="prompt">', body, count=1) if body else ""
                hint = '<p class="hint">Respondé sin mirar antes de seguir leyendo.</p>'
                body = prompt + hint

            out.append(
                f'<aside class="callout {kind}">'
                f'<div class="callout-title">{inline(semantic_label)}</div>'
                f'<div class="callout-body">{term}{body}</div>'
                '</aside>'
            )
            continue

        if line.lstrip().startswith(">"):
            buf: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(prose_block(f"<blockquote>{'<br>'.join(inline(x) for x in buf)}</blockquote>"))
            continue

        im = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)\s*", line.strip())
        if im:
            alt, src, cap = im.group(1), im.group(2), im.group(3) or im.group(1)
            out.append(
                '<figure>'
                '<div class="plate">'
                f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}" loading="lazy">'
                '</div>'
                f'<figcaption><span>{inline(cap)}</span></figcaption>'
                '</figure>'
            )
            i += 1
            continue

        if "|" in line and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            buf = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                buf.append(lines[i])
                i += 1
            table_html = f'<div class="table-scroll">{table_block(buf)}</div>'
            cap, new_i = consume_caption(lines, i)
            if cap:
                table_html += f'<div class="table-caption"><span>{inline(cap)}</span></div>'
                i = new_i
            out.append(table_html)
            continue

        lm = re.match(r"^\s*([-*])\s+(.+)$", line)
        om = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if lm or om:
            ordered = bool(om)
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < len(lines):
                mm = re.match(r"^\s*(\d+)\.\s+(.+)$", lines[i]) if ordered else re.match(r"^\s*[-*]\s+(.+)$", lines[i])
                if not mm:
                    break
                items.append(mm.group(2) if ordered else mm.group(1))
                i += 1
            list_html = f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>"
            out.append(prose_block(list_html))
            continue

        if re.fullmatch(r"\s*---+\s*", line):
            out.append(prose_block("<hr>"))
            i += 1
            continue

        buf = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip():
            nxt = lines[i]
            if (
                re.match(r"^(#{1,4})\s+", nxt)
                or nxt.startswith("```")
                or nxt.lstrip().startswith(">")
                or re.fullmatch(r"!\[[^\]]*\]\([^)]+\)\s*", nxt.strip())
                or re.match(r"^\s*[-*]\s+", nxt)
                or re.match(r"^\s*\d+\.\s+", nxt)
            ):
                break
            if "|" in nxt and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
                break
            buf.append(nxt.strip())
            i += 1
        if waiting_for_lede and wrap_prose:
            lede = f'<p class="study-lede">{inline(" ".join(buf))}</p>'
            if out and out[-1].startswith('<header class="study-header">'):
                out[-1] = out[-1].replace('</div></header>', f'{lede}</div></header>')
            else:
                out.append(prose_block(lede))
            waiting_for_lede = False
        else:
            out.append(prose_block(f"<p>{inline(' '.join(buf))}</p>"))

    return "\n".join(out), toc, title


def validate_images(md_path: Path, text: str) -> list[str]:
    issues: list[str] = []
    for alt, src in re.findall(r"!\[([^\]]*)\]\(([^)\s]+)", text):
        if not alt.strip():
            issues.append(f"image-missing-alt:{src}")
        if re.match(r"^[a-z]+://", src):
            continue
        target = (md_path.parent / src).resolve()
        if not target.is_file():
            issues.append(f"image-missing:{src}")
    return issues


def rebase_local_images(text: str, input_dir: Path, output_dir: Path) -> str:
    pattern = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")

    def replace(m: re.Match[str]) -> str:
        alt, src, title = m.group(1), m.group(2), m.group(3)
        if re.match(r"^[a-z]+://", src) or src.startswith("data:"):
            return m.group(0)
        target = (input_dir / src).resolve()
        rel = os.path.relpath(target, output_dir.resolve()).replace(os.sep, "/")
        title_part = f' "{title}"' if title else ""
        return f"![{alt}]({rel}{title_part})"

    return pattern.sub(replace, text)


def _progress_script(enabled: bool) -> str:
    if not enabled:
        return ""
    return """<script>
(() => {
  const bar = document.querySelector('.reading-progress > span');
  if (!bar) return;
  const update = () => {
    const d = document.documentElement;
    const max = Math.max(0, d.scrollHeight - d.clientHeight);
    const pct = max ? Math.min(100, Math.max(0, d.scrollTop / max * 100)) : 0;
    bar.style.width = pct.toFixed(2) + '%';
  };
  addEventListener('scroll', update, {passive: true});
  addEventListener('resize', update);
  update();
})();
</script>"""


def render(input_path: Path, output_path: Path, kind: str, course: str = "", scope: str = "") -> list[str]:
    text = input_path.read_text(encoding="utf-8")
    issues = validate_images(input_path, text) + validate_caption_comments(text)
    rendered_text = rebase_local_images(text, input_path.parent, output_path.parent)
    content, toc, title = render_markdown(rendered_text, scope=scope)
    css = THEME.read_text(encoding="utf-8")

    toc_html = "".join(f'<a class="depth-{d}" href="#{hid}">{html.escape(label)}</a>' for d, hid, label in toc)
    show_toc = kind == "guide" and len(toc) >= 3
    show_progress = kind == "guide" and len(toc) >= 3
    kind_label = {
        "summary": "Resumen",
        "guide": "Guía",
        "rapid-review": "Repaso",
        "learn": "Aprender",
        "explain": "Explicación",
    }[kind]
    running_left = html.escape(course.strip() or "Material de estudio")
    running_scope = f" · {html.escape(scope.strip())}" if scope.strip() else ""
    frontmatter = (
        '<div class="book-frontmatter">'
        f'<div class="book-running-line"><span class="book-course">{running_left}</span>'
        f'<span class="book-kind">{kind_label}{running_scope}</span></div>'
        '</div>'
    )
    toc_block = f'<nav class="toc" aria-label="Índice"><strong>Índice</strong>{toc_html}</nav>' if show_toc else ""
    grid_class = "with-toc" if show_toc else "without-toc"
    progress = '<div class="reading-progress" aria-hidden="true"><span></span></div>' if show_progress else ""

    document = f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>{FONT_LINKS}<style>{css}</style></head>
<body>{progress}<main class="study-shell"><div class="study-grid {grid_class}"><article data-kind="{html.escape(kind)}">{frontmatter}{content}</article>{toc_block}</div></main>{_progress_script(show_progress)}</body></html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return issues


def main() -> None:
    ap = argparse.ArgumentParser(description="Render student Markdown to evidence-informed HTML")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--kind", choices=["summary", "guide", "rapid-review", "learn", "explain"], default="summary")
    ap.add_argument("--course", default="", help="Course/subject name for textbook-style front matter")
    ap.add_argument("--scope", default="", help="Unit/chapter label for textbook-style front matter")
    ap.add_argument("--check", action="store_true", help="Fail if local images are broken/missing alt text")
    args = ap.parse_args()
    inp = Path(args.input).resolve()
    out = Path(args.output).resolve()
    issues = render(inp, out, args.kind, course=args.course, scope=args.scope)
    print(f"Rendered: {out}")
    if issues:
        for x in issues:
            print(f"WARNING: {x}")
        if args.check:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
