#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil
from pathlib import Path


REQUIRED_DIRECTORIES = (
    "academico",
    "conocimiento",
    "fuentes",
    "fuentes/oficiales",
    "fuentes/transcripciones",
    "notas",
    "preguntas",
    "progreso",
    "resumenes",
    "simulacros",
    "assets",
    "assets/figures",
)


def slugify(s: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "materia"


def ensure_course_directories(target: Path) -> None:
    """Create structural directories explicitly because Git does not preserve empty folders."""
    for relative in REQUIRED_DIRECTORIES:
        (target / relative).mkdir(parents=True, exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--slug")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    template = root / "materias" / "_plantilla"
    target = root / "materias" / (args.slug or slugify(args.name))
    if target.exists():
        raise SystemExit(f"Already exists: {target}")
    shutil.copytree(template, target)
    ensure_course_directories(target)
    context = target / "contexto.md"
    text = context.read_text(encoding="utf-8").replace("- **Materia:**", f"- **Materia:** {args.name}")
    context.write_text(text, encoding="utf-8")
    academic = target / "academico" / "academic.json"
    if academic.exists():
        import json
        data = json.loads(academic.read_text(encoding="utf-8"))
        data.setdefault("identity", {})["subject"] = args.name
        academic.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)

if __name__ == "__main__":
    main()
