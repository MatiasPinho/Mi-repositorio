#!/usr/bin/env python3
"""University Study System CLI.

Deterministic console interface for course administration, material scanning,
progress summaries, due reviews, assessment inspection, and validation.
No AI calls are made by this program.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import webbrowser
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
COURSES_DIR = ROOT / "materias"
SCRIPTS_DIR = ROOT / "scripts"
IGNORED_MATERIALS = {"README.md", ".DS_Store", "Thumbs.db"}


def _configure_utf8_stdio() -> None:
    """Keep CLI output stable on Windows consoles and redirected pipes."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError, OSError):
                pass


_configure_utf8_stdio()


class CliError(RuntimeError):
    pass


def slugify(text: str) -> str:
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "materia"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise CliError(f"No se pudo leer JSON valido: {path}") from exc


def course_dirs() -> list[Path]:
    if not COURSES_DIR.exists():
        return []
    return sorted(
        [p for p in COURSES_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")],
        key=lambda p: p.name.lower(),
    )


def course_display_name(course: Path) -> str:
    academic = read_json(course / "academico" / "academic.json", {})
    subject = academic.get("identity", {}).get("subject", "") if isinstance(academic, dict) else ""
    if subject:
        return str(subject)
    context = course / "contexto.md"
    if context.exists():
        try:
            for line in context.read_text(encoding="utf-8").splitlines():
                if line.startswith("- **Materia:**"):
                    name = line.split(":**", 1)[-1].strip() if ":**" in line else line.split(":", 1)[-1].strip()
                    if name:
                        return name
        except OSError:
            pass
    return course.name


def resolve_course(value: str | None, *, interactive: bool = False) -> Path:
    courses = course_dirs()
    if value:
        raw = value.strip()
        # Accept slug, visible name, or an explicit materias/<slug> path.
        path_candidate = Path(raw)
        if not path_candidate.is_absolute():
            path_candidate = ROOT / path_candidate
        try:
            resolved_candidate = path_candidate.resolve()
            resolved_courses = COURSES_DIR.resolve()
            if resolved_candidate.is_dir() and resolved_candidate.is_relative_to(resolved_courses) and not resolved_candidate.name.startswith("_"):
                return resolved_candidate
        except OSError:
            pass
        direct = COURSES_DIR / raw
        if direct.is_dir() and not direct.name.startswith("_"):
            return direct
        target = " ".join(raw.lower().split())
        target_slug = slugify(raw)
        matches = []
        for course in courses:
            if course.name == target_slug or " ".join(course_display_name(course).lower().split()) == target:
                matches.append(course)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise CliError(f"Materia ambigua: {value}. Usa el slug.")
        raise CliError(f"No existe la materia: {value}")

    if not interactive:
        raise CliError("Falta indicar la materia.")
    if not courses:
        raise CliError("Todavia no hay materias. Crea una primero.")
    print("\nMaterias disponibles:")
    for idx, course in enumerate(courses, 1):
        print(f"  {idx}. {course_display_name(course)} [{course.name}]")
    selected = input("Elegir materia: ").strip()
    try:
        number = int(selected)
        if 1 <= number <= len(courses):
            return courses[number - 1]
    except ValueError:
        pass
    return resolve_course(selected, interactive=False)


def run_script(script: str, *args: str) -> tuple[str, str]:
    cmd = [sys.executable, str(SCRIPTS_DIR / script), *args]
    env = os.environ.copy()
    # Child tools frequently emit JSON that is parsed by this process. Force a
    # single encoding regardless of the active Windows code page.
    env["PYTHONIOENCODING"] = "utf-8"
    cp = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if cp.returncode != 0:
        message = (cp.stderr or cp.stdout or f"Fallo {script}").strip()
        raise CliError(message)
    return cp.stdout.strip(), cp.stderr.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def material_kind(relative: Path) -> str:
    parts = [x.lower() for x in relative.parts]
    suffix = relative.suffix.lower()
    if "transcripciones" in parts or suffix in {".srt", ".vtt"}:
        return "transcript"
    if "oficiales" in parts:
        return "official"
    return "unclassified"


def scan_materials(course: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_dir = course / "fuentes"
    current: dict[str, Any] = {}
    if source_dir.exists():
        for p in sorted(source_dir.rglob("*")):
            if p.is_file() and p.name not in IGNORED_MATERIALS:
                stat = p.stat()
                rel = p.relative_to(source_dir)
                current[rel.as_posix()] = {
                    "sha256": sha256(p),
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "kind": material_kind(rel),
                }
    index = read_json(course / ".study" / "materials-index.json", {})
    previous = index.get("files", {}) if isinstance(index, dict) else {}
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(k for k in set(current) & set(previous) if current[k].get("sha256") != previous[k].get("sha256"))
    return current, {"added": added, "changed": changed, "removed": removed, "total": len(current)}


def fmt_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


def cmd_course_add(args: argparse.Namespace) -> None:
    extra = [args.name]
    if args.slug:
        extra += ["--slug", args.slug]
    out, _ = run_script("new_course.py", *extra)
    course = Path(out)
    print(f"Materia creada: {course_display_name(course)}")
    print(f"Slug: {course.name}")
    print(f"Carpeta: {course}")
    print(f"Material oficial: {course / 'fuentes' / 'oficiales'}")
    print(f"Transcripciones: {course / 'fuentes' / 'transcripciones'}")


def cmd_course_list(_: argparse.Namespace) -> None:
    courses = course_dirs()
    if not courses:
        print("No hay materias creadas.")
        return
    print("Materias:")
    for course in courses:
        academic = read_json(course / "academico" / "academic.json", {})
        units = len(academic.get("units", [])) if isinstance(academic, dict) else 0
        assessments = len(academic.get("assessments", [])) if isinstance(academic, dict) else 0
        print(f"  - {course_display_name(course)} [{course.name}]  unidades={units} evaluaciones={assessments}")


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    return sum(1 for item in path.rglob("*") if item.is_file())


def _context_field(text: str, label: str) -> str:
    prefix = f"- **{label}:**"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _set_context_field(text: str, label: str, value: str) -> str:
    prefix = f"- **{label}:**"
    replacement = f"{prefix} {value}".rstrip()
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith(prefix):
            lines[idx] = replacement
            break
    return "\n".join(lines) + "\n"


def reset_course_content(course: Path) -> dict[str, Any]:
    """Return a course to a fresh processing state while preserving raw sources and identity."""
    template = COURSES_DIR / "_plantilla"
    if not template.is_dir():
        raise CliError("No se encontro materias/_plantilla; no se puede resetear de forma segura.")

    current_academic = read_json(course / "academico" / "academic.json", {})
    identity = current_academic.get("identity", {}) if isinstance(current_academic, dict) else {}
    if not isinstance(identity, dict):
        identity = {}
    identity = dict(identity)
    if not str(identity.get("subject", "")).strip():
        identity["subject"] = course_display_name(course)

    old_context = ""
    context_path = course / "contexto.md"
    if context_path.exists():
        try:
            old_context = context_path.read_text(encoding="utf-8")
        except OSError:
            old_context = ""
    personal_goal = _context_field(old_context, "Objetivo personal") or "9-10 con comprensión real"

    reset_names = [
        "academico", "conocimiento", "notas", "preguntas", "progreso",
        "resumenes", "simulacros", "assets",
    ]
    removed_files = sum(_count_files(course / name) for name in reset_names)
    removed_files += _count_files(course / ".study")
    if context_path.exists():
        removed_files += 1

    # Raw course material is deliberately outside this list and is never touched.
    for name in reset_names:
        target = course / name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        source = template / name
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.exists():
            shutil.copy2(source, target)

    study_dir = course / ".study"
    if study_dir.exists():
        shutil.rmtree(study_dir)

    academic_path = course / "academico" / "academic.json"
    academic = read_json(academic_path, {})
    template_identity = academic.get("identity", {}) if isinstance(academic, dict) else {}
    if not isinstance(template_identity, dict):
        template_identity = {}
    merged_identity = dict(template_identity)
    merged_identity.update(identity)
    academic["identity"] = merged_identity
    academic_path.write_text(json.dumps(academic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fresh_context = (template / "contexto.md").read_text(encoding="utf-8")
    professors = identity.get("professors", [])
    if isinstance(professors, list):
        professors_text = ", ".join(str(x) for x in professors if str(x).strip())
    else:
        professors_text = str(professors or "")
    context_values = {
        "Materia": str(identity.get("subject", "") or ""),
        "Institución": str(identity.get("institution", "") or ""),
        "Carrera": str(identity.get("career", "") or ""),
        "Plan de estudios": str(identity.get("study_plan", "") or ""),
        "Cátedra": str(identity.get("chair", "") or ""),
        "Profesor/es": professors_text,
        "Comisión / turno": str(identity.get("commission", "") or ""),
        "Objetivo personal": personal_goal,
    }
    for label, value in context_values.items():
        fresh_context = _set_context_field(fresh_context, label, value)
    context_path.write_text(fresh_context, encoding="utf-8")

    _, source_diff = scan_materials(course)
    return {"removed_files": removed_files, "preserved_source_files": source_diff["total"]}


def cmd_course_reset(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    display = course_display_name(course)
    if not args.yes:
        print(f"\nRESET DE MATERIA: {display} [{course.name}]")
        print("Se conservara fuentes/ y la identidad basica de la materia.")
        print("Se borraran conocimiento procesado, contexto academico derivado, notas, progreso,")
        print("resumenes, guias, repasos, preguntas, simulacros, figuras generadas y cache .study/.")
        typed = input(f"Escribi {course.name} para confirmar: ").strip()
        if typed != course.name:
            print("Cancelado. No se modifico nada.")
            return
    result = reset_course_content(course)
    print(f"Materia reseteada: {display} [{course.name}]")
    print(f"  Fuentes conservadas: {result['preserved_source_files']} archivos")
    print(f"  Archivos de contenido/estado reemplazados o eliminados: {result['removed_files']}")
    print("  Proximo paso recomendado: /procesar (o $procesar en Codex).")


def cmd_materials_scan(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    current, diff = scan_materials(course)
    transcript_count = sum(1 for meta in current.values() if meta.get("kind") == "transcript")

    if args.commit:
        study_dir = course / ".study"
        study_dir.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "files": current}
        (study_dir / "materials-index.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # --json is a machine contract: stdout contains exactly one JSON document.
    # Human narration must never be mixed into it.
    if args.json:
        print(json.dumps(diff, ensure_ascii=False, indent=2))
        return

    print(f"Materiales - {course_display_name(course)}")
    print(f"  Total:       {diff['total']}")
    print(f"  Nuevos:      {len(diff['added'])}")
    print(f"  Modificados: {len(diff['changed'])}")
    print(f"  Eliminados:  {len(diff['removed'])}")
    if transcript_count:
        print(f"  Transcripciones: {transcript_count}")
    for label, key in [("NUEVOS", "added"), ("MODIFICADOS", "changed"), ("ELIMINADOS", "removed")]:
        if diff[key]:
            print(f"\n{label}")
            for item in diff[key]:
                print(f"  - {item}")
    if args.commit:
        print("\nEstado actual de materiales registrado como procesado.")


def cmd_transcripts_inspect(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    cmd = ["inspect", "--course", str(course)]
    if args.file:
        cmd += ["--file", args.file]
    if args.write:
        cmd += ["--write"]
    out, _ = run_script("transcript_tools.py", *cmd)
    rows = json.loads(out or "[]")
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("No hay transcripciones compatibles en fuentes/transcripciones/.")
        return
    print(f"Transcripciones - {course_display_name(course)}")
    for row in rows:
        print(f"  - {row.get('file')} | segmentos={row.get('segments', 0)} | timestamps={row.get('timestamped_segments', 0)} | duracion={row.get('duration') or '-'}")
        cues = row.get("cue_candidates", [])
        if cues:
            print(f"    candidatos de enfasis: {len(cues)}")
            for cue in cues[:8]:
                where = cue.get("start") or "sin timestamp"
                kinds = ",".join(cue.get("cue_types", []))
                text = cue.get("text", "")
                if len(text) > 120:
                    text = text[:117] + "..."
                speaker = (cue.get("speaker") or "").strip()
                prefix = f"{speaker}: " if speaker else ""
                print(f"      {where} [{kinds}] {prefix}{text}")
            if len(cues) > 8:
                print(f"      ... {len(cues)-8} mas")
        else:
            print("    candidatos de enfasis: 0")


def cmd_figures_preflight(args: argparse.Namespace) -> None:
    out, _ = run_script("figure_assets.py", "preflight")
    data = json.loads(out or "{}")
    if getattr(args, "json", False):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if data.get("pdf_visuals"):
        print("Visuales PDF: READY (PyMuPDF disponible)")
    else:
        print("Visuales PDF: DISABLED (falta PyMuPDF)")
        print(f"  Instalar: {data.get('install')}")


def cmd_figures_scan(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    preflight_out, _ = run_script("figure_assets.py", "preflight")
    capabilities = json.loads(preflight_out or "{}")
    if not capabilities.get("pdf_visuals"):
        if getattr(args, "json", False):
            print(json.dumps({"available": False, **capabilities, "files": []}, ensure_ascii=False, indent=2))
        else:
            print("Visuales PDF: DISABLED (falta PyMuPDF). La ingesta textual puede continuar.")
            print(f"  Instalar: {capabilities.get('install')}")
        return
    cmd = ["scan", "--course", str(course)]
    if args.write:
        cmd.append("--write")
    out, _ = run_script("figure_assets.py", *cmd)
    data = json.loads(out or "{}")
    files = data.get("files", []) if isinstance(data, dict) else []
    total_pages = sum(int(x.get("pages", 0)) for x in files)
    candidates = sum(int(x.get("candidates", 0)) for x in files)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(f"Visuales PDF - {course_display_name(course)}")
    print(f"  PDFs: {len(files)} | paginas: {total_pages} | paginas candidatas: {candidates}")
    if args.write:
        print(f"  Catalogo: {course / '.study' / 'figure-pages.json'}")


def cmd_figures_render(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    cmd = ["render-page", "--course", str(course), "--file", args.file, "--page", str(args.page), "--id", args.id]
    if args.dpi:
        cmd += ["--dpi", str(args.dpi)]
    if args.clip:
        cmd += ["--clip", args.clip]
    out, _ = run_script("figure_assets.py", *cmd)
    print(out)


def cmd_figures_verify(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    out, _ = run_script("figure_assets.py", "verify", "--course", str(course))
    print(out)


def cmd_figures_register_derived(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    cmd = [
        "register-derived", "--course", str(course), "--id", args.id, "--unit", args.unit,
        "--asset", args.asset, "--kind", args.kind, "--role", args.role,
        "--description", args.description,
    ]
    for value in args.concept or []:
        cmd += ["--concept", value]
    for value in args.learner_focus or []:
        cmd += ["--learner-focus", value]
    for value in args.based_on or []:
        cmd += ["--based-on", value]
    out, _ = run_script("figure_assets.py", *cmd)
    print(out)


def cmd_figures_scope(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    out, _ = run_script("figure_assets.py", "scope", "--course", str(course), "--unit", args.unit)
    print(out)


def cmd_figures_migrate(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    cmd = ["migrate-registry", "--course", str(course)]
    if args.dry_run:
        cmd.append("--dry-run")
    out, _ = run_script("figure_assets.py", *cmd)
    print(out)


def cmd_open(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    summary_dir = course / "resumenes"
    if not summary_dir.exists():
        raise CliError("No hay carpeta de resumenes.")
    files = [p for p in summary_dir.glob("*.html") if p.is_file()]
    if args.contains:
        q = slugify(args.contains)
        files = [p for p in files if q in slugify(p.stem)]
    if args.type:
        suffix = {"summary": "-resumen", "guide": "-guia", "rapid-review": "-repaso"}[args.type]
        files = [p for p in files if p.stem.endswith(suffix)]
    if not files:
        raise CliError("No se encontro un HTML de estudio con esos filtros.")
    target = max(files, key=lambda p: p.stat().st_mtime)
    webbrowser.open(target.resolve().as_uri())
    print(f"Abierto: {target}")


def academic_data(course: Path) -> dict[str, Any]:
    return read_json(course / "academico" / "academic.json", {})


def assessment_rows(course: Path) -> list[dict[str, Any]]:
    data = academic_data(course)
    return data.get("assessments", []) if isinstance(data, dict) else []


def assessment_scope_text(assessment: dict[str, Any]) -> str:
    confirmed = [s.get("ref", "") for s in assessment.get("scope", []) if s.get("status") == "confirmed"]
    likely = [s.get("ref", "") for s in assessment.get("scope", []) if s.get("status") == "likely"]
    bits = []
    if confirmed:
        bits.append("confirmado: " + ", ".join(confirmed))
    if likely:
        bits.append("probable: " + ", ".join(likely))
    return "; ".join(bits) if bits else "sin alcance confirmado"


def next_assessment(course: Path) -> dict[str, Any] | None:
    today = date.today()
    candidates = []
    for a in assessment_rows(course):
        raw = a.get("date", "")
        try:
            d = date.fromisoformat(raw)
        except (TypeError, ValueError):
            continue
        if d >= today and a.get("status", "unknown") not in {"cancelled", "completed"}:
            candidates.append((d, a))
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1] if candidates else None


def progress_summary(course: Path) -> dict[str, Any]:
    data = read_json(course / "progreso" / "progress.json", {"concepts": {}})
    concepts = list(data.get("concepts", {}).values()) if isinstance(data, dict) else []
    if not concepts:
        return {"count": 0, "avg": None, "due": 0, "untested": 0, "weak": []}
    today = date.today()
    due = 0
    untested = 0
    for item in concepts:
        if int(item.get("attempts", 0)) == 0:
            untested += 1
        raw = item.get("next_review")
        try:
            if not raw or date.fromisoformat(raw) <= today:
                due += 1
        except ValueError:
            due += 1
    avg = sum(float(i.get("mastery", 0)) for i in concepts) / len(concepts)
    weak = sorted(concepts, key=lambda i: (float(i.get("mastery", 0)), i.get("name", "").lower()))[:5]
    return {"count": len(concepts), "avg": avg, "due": due, "untested": untested, "weak": weak}


def artifact_rows(course: Path) -> list[dict[str, Any]]:
    try:
        out, _ = run_script("artifact_state.py", "status", "--course", str(course))
        rows = json.loads(out or "[]")
        return rows if isinstance(rows, list) else []
    except (CliError, json.JSONDecodeError):
        return []


def cmd_artifacts(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    rows = artifact_rows(course)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("No hay artefactos derivados registrados.")
        return
    print(f"Artefactos - {course_display_name(course)}")
    for row in rows:
        state = "STALE" if row.get("stale") else "CURRENT"
        reasons = ", ".join(row.get("reasons", []))
        extra = f" | {reasons}" if reasons else ""
        print(f"  - [{state}] {row.get('file', '?')} | {row.get('type', '?')} | {row.get('scope') or 'scope global'}{extra}")


def cmd_status(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    # Keep the invariant graph concept -> tracked concept without requiring the user to remember a sync command.
    run_script("study_tracker.py", "sync", "--course", str(course))
    _, materials = scan_materials(course)
    graph = read_json(course / "conocimiento" / "concepts.json", {"concepts": {}})
    figure_data = read_json(course / "conocimiento" / "figures.json", {"figures": {}})
    p = progress_summary(course)
    nxt = next_assessment(course)

    print(course_display_name(course))
    print("=" * len(course_display_name(course)))
    print(f"Slug: {course.name}")
    print("\nMateriales")
    print(f"  Registrados ahora: {materials['total']}")
    print(f"  Nuevos: {len(materials['added'])} | Modificados: {len(materials['changed'])} | Eliminados: {len(materials['removed'])}")
    print("\nConocimiento")
    print(f"  Conceptos en grafo: {len(graph.get('concepts', {})) if isinstance(graph, dict) else 0}")
    print(f"  Figuras pedagogicas registradas: {len(figure_data.get('figures', {})) if isinstance(figure_data, dict) else 0}")
    print(f"  Conceptos trackeados: {p['count']}")
    print(f"  Nunca evaluados: {p['untested']}")
    print("\nProgreso")
    print(f"  Dominio medio: {fmt_pct(p['avg'])}")
    print(f"  Repasos pendientes: {p['due']}")
    if p["weak"]:
        print("  Mas debiles:")
        for item in p["weak"]:
            print(f"    - {item.get('name', '?')}: {fmt_pct(item.get('mastery', 0))}")
    artifacts = artifact_rows(course)
    if artifacts:
        stale_count = sum(1 for row in artifacts if row.get("stale"))
        current_count = len(artifacts) - stale_count
        print("\nArtefactos derivados")
        print(f"  Current: {current_count} | Stale/untracked: {stale_count}")
    print("\nProxima evaluacion")
    if nxt:
        print(f"  {nxt.get('name', nxt.get('id', '?'))} ({nxt.get('type', 'evaluacion')}) - {nxt.get('date', '?')}")
        print(f"  Alcance: {assessment_scope_text(nxt)}")
    else:
        print("  No hay una evaluacion futura con fecha registrada.")


def cmd_due(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    run_script("study_tracker.py", "sync", "--course", str(course))
    cmd = ["due", "--course", str(course)]
    if args.on:
        cmd += ["--on", args.on]
    if args.assessment:
        cmd += ["--assessment", args.assessment]
    if args.include_not_due:
        cmd += ["--include-not-due"]
    out, _ = run_script("study_tracker.py", *cmd)
    rows = json.loads(out or "[]")
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("No hay repasos pendientes con esos filtros.")
        return
    print(f"Repasos - {course_display_name(course)}")
    for idx, item in enumerate(rows, 1):
        reasons = ", ".join(item.get("priority_reasons", [])) or "scheduled"
        print(
            f"  {idx:>2}. {item.get('name', '?')} | dominio {fmt_pct(item.get('mastery', 0))} "
            f"| prioridad {item.get('study_priority', 0):.2f} | {reasons}"
        )


def cmd_assessments(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)
    rows = assessment_rows(course)
    if not rows:
        print("No hay evaluaciones registradas.")
        return
    print(f"Evaluaciones - {course_display_name(course)}")
    for a in rows:
        parent = f" | recupera: {a.get('parent_assessment_id')}" if a.get("parent_assessment_id") else ""
        print(f"  - {a.get('name', a.get('id', '?'))} [{a.get('id', '?')}] | {a.get('type', '?')} | fecha: {a.get('date') or 'sin fecha'}{parent}")
        print(f"    alcance: {assessment_scope_text(a)}")


def cmd_validate(args: argparse.Namespace) -> None:
    course = resolve_course(args.course)

    structural: list[str] = []
    required_dirs = [
        "academico", "conocimiento", "fuentes", "notas", "preguntas",
        "progreso", "resumenes", "simulacros",
    ]
    for dirname in required_dirs:
        if not (course / dirname).is_dir():
            structural.append(f"falta carpeta requerida: {dirname}/")
    required_json = [
        course / "academico" / "academic.json",
        course / "conocimiento" / "concepts.json",
        course / "progreso" / "progress.json",
    ]
    for path in required_json:
        if not path.exists():
            structural.append(f"falta archivo requerido: {path.relative_to(course)}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            structural.append(f"JSON invalido: {path.relative_to(course)}")
    if not (course / "contexto.md").exists():
        structural.append("falta archivo requerido: contexto.md")

    issues: list[dict[str, Any]] = []
    stderr = ""
    if (course / "academico" / "academic.json").exists():
        try:
            out, stderr = run_script("academic_context.py", "validate", "--course", str(course))
            data = json.loads(out)
            issues = data.get("issues", []) if isinstance(data, dict) else []
        except CliError as exc:
            structural.append(f"no se pudo validar academic.json: {exc}")

    stale: list[dict[str, Any]] = []
    if (course / "conocimiento" / "concepts.json").exists():
        try:
            stale_out, _ = run_script("concept_graph.py", "stale", "--course", str(course))
            stale = json.loads(stale_out or "[]")
        except CliError as exc:
            structural.append(f"no se pudo validar concepts.json: {exc}")

    figure_issues: list[dict[str, Any]] = []
    if (course / "conocimiento" / "figures.json").exists():
        try:
            fig_out, _ = run_script("figure_assets.py", "verify", "--course", str(course))
            fig_data = json.loads(fig_out or "{}")
            figure_issues = fig_data.get("issues", []) if isinstance(fig_data, dict) else []
        except CliError as exc:
            # Verification itself does not need PyMuPDF unless source hashes are checked; report as structural if it cannot run.
            structural.append(f"no se pudo validar figures.json: {exc}")

    derived = [row for row in artifact_rows(course) if row.get("stale")]

    if not structural and not issues and not stale and not figure_issues and not derived:
        print(f"OK: {course_display_name(course)} no tiene inconsistencias conocidas.")
        return
    if structural:
        print("Problemas estructurales:")
        for message in structural:
            print(f"  - [ERROR] {message}")
    if issues:
        print("Problemas academicos:")
        for issue in issues:
            level = str(issue.get("level", "warning")).upper()
            print(f"  - [{level}] {issue.get('message', issue)}")
    if stale:
        print("Conceptos con fuentes desactualizadas:")
        for item in stale:
            source = item.get('source', item.get('file', '?'))
            print(f"  - {item.get('concept', '?')}: {item.get('reason', 'stale')} ({source})")
    if figure_issues:
        print("Problemas con figuras/visuales:")
        for item in figure_issues:
            print(f"  - {item.get('figure', '?')}: {item.get('reason', 'issue')}")
    if derived:
        print("Artefactos derivados desactualizados/no registrados:")
        for item in derived:
            reasons = ", ".join(item.get("reasons", [])) or "stale"
            print(f"  - {item.get('file', '?')}: {reasons}")
    if stderr:
        print(stderr, file=sys.stderr)


def interactive_menu() -> None:
    while True:
        print("\nUniversity Study System")
        print("1. Crear materia")
        print("2. Listar materias")
        print("3. Ver estado de una materia")
        print("4. Escanear materiales nuevos")
        print("5. Ver repasos pendientes")
        print("6. Ver evaluaciones")
        print("7. Validar materia")
        print("8. Marcar materiales actuales como procesados")
        print("9. Inspeccionar transcripciones")
        print("10. Ver estado de resúmenes/guías/repasos")
        print("11. Escanear paginas visuales de PDFs")
        print("12. Abrir ultimo material de estudio HTML")
        print("13. Resetear contenido de una materia (conservar fuentes)")
        print("0. Salir")
        choice = input("\nOpcion: ").strip()
        try:
            if choice == "0":
                return
            if choice == "1":
                name = input("Nombre de la materia: ").strip()
                if not name:
                    print("El nombre no puede estar vacio.")
                    continue
                cmd_course_add(argparse.Namespace(name=name, slug=None))
            elif choice == "2":
                cmd_course_list(argparse.Namespace())
            elif choice == "3":
                course = resolve_course(None, interactive=True)
                cmd_status(argparse.Namespace(course=course.name))
            elif choice == "4":
                course = resolve_course(None, interactive=True)
                cmd_materials_scan(argparse.Namespace(course=course.name, commit=False, json=False))
            elif choice == "5":
                course = resolve_course(None, interactive=True)
                cmd_due(argparse.Namespace(course=course.name, on=None, assessment=None, include_not_due=False, json=False))
            elif choice == "6":
                course = resolve_course(None, interactive=True)
                cmd_assessments(argparse.Namespace(course=course.name))
            elif choice == "7":
                course = resolve_course(None, interactive=True)
                cmd_validate(argparse.Namespace(course=course.name))
            elif choice == "8":
                course = resolve_course(None, interactive=True)
                confirm = input("Esto marca el estado actual como ya procesado. Escribir SI para confirmar: ").strip().upper()
                if confirm == "SI":
                    cmd_materials_scan(argparse.Namespace(course=course.name, commit=True, json=False))
                else:
                    print("Cancelado.")
            elif choice == "9":
                course = resolve_course(None, interactive=True)
                cmd_transcripts_inspect(argparse.Namespace(course=course.name, file=None, write=False, json=False))
            elif choice == "10":
                course = resolve_course(None, interactive=True)
                cmd_artifacts(argparse.Namespace(course=course.name, json=False))
            elif choice == "11":
                course = resolve_course(None, interactive=True)
                cmd_figures_scan(argparse.Namespace(course=course.name, write=True, json=False))
            elif choice == "12":
                course = resolve_course(None, interactive=True)
                cmd_open(argparse.Namespace(course=course.name, type=None, contains=None))
            elif choice == "13":
                course = resolve_course(None, interactive=True)
                cmd_course_reset(argparse.Namespace(course=course.name, yes=False))
            else:
                print("Opcion invalida.")
        except CliError as exc:
            print(f"ERROR: {exc}")
        except KeyboardInterrupt:
            print("\nCancelado.")



def mcp_capabilities() -> dict[str, Any]:
    """Report whether the optional local MCP adapter can run."""
    try:
        from importlib import metadata
        version = metadata.version("mcp")
    except Exception:
        return {
            "available": False,
            "transport": "stdio",
            "sdk": "missing",
            "install": f"{sys.executable} -m pip install -r requirements-mcp.txt",
        }
    try:
        major = int(version.split(".", 1)[0])
    except ValueError:
        major = -1
    compatible = major == 1
    return {
        "available": compatible,
        "transport": "stdio",
        "sdk": version,
        "compatible": compatible,
        "required": "mcp>=1.28,<2",
        "install": None if compatible else f"{sys.executable} -m pip install -r requirements-mcp.txt --upgrade",
        "reason": None if compatible else "Esta release fija MCP 1.x para compatibilidad Claude Code + Codex stdio.",
    }


def cmd_mcp_preflight(args: argparse.Namespace) -> None:
    data = mcp_capabilities()
    if getattr(args, "json", False):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    state = "READY" if data.get("available") else "DISABLED"
    print(f"Study MCP: {state} | transport=stdio | sdk={data.get('sdk')}")
    if not data.get("available"):
        print(f"  Instalar: {data.get('install')}")
        if data.get("reason"):
            print(f"  Motivo: {data.get('reason')}")


def cmd_mcp_serve(_: argparse.Namespace) -> None:
    data = mcp_capabilities()
    if not data.get("available"):
        raise CliError(
            "Study MCP no está listo. Ejecutá: python -m pip install -r requirements-mcp.txt"
        )
    from study_mcp.server import main as serve
    serve()

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="CLI deterministica de University Study System")
    sub = ap.add_subparsers(dest="group")


    mcp = sub.add_parser("mcp", help="Servidor MCP local para Claude Code/Codex")
    mcpsub = mcp.add_subparsers(dest="mcp_cmd", required=True)
    p = mcpsub.add_parser("preflight", help="Comprobar SDK MCP compatible")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_mcp_preflight)
    p = mcpsub.add_parser("serve", help="Iniciar Study MCP por stdio")
    p.set_defaults(func=cmd_mcp_serve)

    course = sub.add_parser("course", help="Administrar materias")
    csub = course.add_subparsers(dest="course_cmd", required=True)
    p = csub.add_parser("add", help="Crear una materia")
    p.add_argument("name")
    p.add_argument("--slug")
    p.set_defaults(func=cmd_course_add)
    p = csub.add_parser("list", help="Listar materias")
    p.set_defaults(func=cmd_course_list)
    p = csub.add_parser("reset", help="Resetear contenido/estado de una materia conservando fuentes e identidad")
    p.add_argument("course")
    p.add_argument("--yes", action="store_true", help="Confirmar sin prompt interactivo")
    p.set_defaults(func=cmd_course_reset)

    materials = sub.add_parser("materials", help="Administrar materiales")
    msub = materials.add_subparsers(dest="materials_cmd", required=True)
    p = msub.add_parser("scan", help="Detectar material nuevo/modificado/eliminado")
    p.add_argument("course")
    p.add_argument("--commit", action="store_true", help="Registrar el estado actual como procesado")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_materials_scan)

    transcripts = sub.add_parser("transcripts", help="Inspeccionar transcripciones de clase")
    tsub = transcripts.add_subparsers(dest="transcripts_cmd", required=True)
    p = tsub.add_parser("inspect", help="Parsear timestamps y detectar candidatos de enfasis sin IA")
    p.add_argument("course")
    p.add_argument("--file", help="Archivo relativo a fuentes/ o transcripciones/")
    p.add_argument("--write", action="store_true", help="Guardar metadatos normalizados en .study/transcripts/")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_transcripts_inspect)

    figures = sub.add_parser("figures", help="Escanear/renderizar/registrar visuales")
    fsub = figures.add_subparsers(dest="figures_cmd", required=True)
    p = fsub.add_parser("preflight", help="Comprobar capacidad visual PDF sin fallar si falta PyMuPDF")
    p.add_argument("course", nargs="?", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_figures_preflight)
    p = fsub.add_parser("scan", help="Catalogar paginas visualmente densas de PDFs sin IA")
    p.add_argument("course")
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_figures_scan)
    p = fsub.add_parser("render", help="Renderizar una pagina/crop seleccionado como asset local")
    p.add_argument("course")
    p.add_argument("--file", required=True, help="Ruta relativa a fuentes/, ej. oficiales/u2.pdf")
    p.add_argument("--page", required=True, type=int)
    p.add_argument("--id", required=True)
    p.add_argument("--dpi", type=int, default=144)
    p.add_argument("--clip")
    p.set_defaults(func=cmd_figures_render)
    p = fsub.add_parser("register-derived", help="Registrar figura derivada con id/procedencia seguros")
    p.add_argument("course")
    p.add_argument("--id", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--asset", required=True)
    p.add_argument("--kind", default="diagram", choices=["diagram", "table", "chart", "screenshot", "illustration", "other"])
    p.add_argument("--role", default="supporting", choices=["essential", "supporting"])
    p.add_argument("--description", required=True)
    p.add_argument("--concept", action="append")
    p.add_argument("--learner-focus", action="append")
    p.add_argument("--based-on", action="append", required=True)
    p.set_defaults(func=cmd_figures_register_derived)
    p = fsub.add_parser("migrate", help="Normalizar registros legacy de figuras derivadas sin reprocesar fuentes")
    p.add_argument("course")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_figures_migrate)
    p = fsub.add_parser("scope", help="Resolver unit_id y listar figuras de esa unidad")
    p.add_argument("course")
    p.add_argument("--unit", required=True)
    p.set_defaults(func=cmd_figures_scope)
    p = fsub.add_parser("verify", help="Verificar assets, ids, procedencia y colisiones de figures.json")
    p.add_argument("course")
    p.set_defaults(func=cmd_figures_verify)

    p = sub.add_parser("status", help="Resumen de una materia")
    p.add_argument("course")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("due", help="Repasos pendientes")
    p.add_argument("course")
    p.add_argument("--on", help="Fecha YYYY-MM-DD")
    p.add_argument("--assessment", help="Id o nombre de evaluacion")
    p.add_argument("--include-not-due", action="store_true", help="Incluir contenido de la evaluacion aunque aun no venza")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_due)

    p = sub.add_parser("assessments", help="Listar evaluaciones")
    p.add_argument("course")
    p.set_defaults(func=cmd_assessments)

    p = sub.add_parser("artifacts", help="Ver si resumenes/guias/repasos/preguntas estan current o stale")
    p.add_argument("course")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_artifacts)

    p = sub.add_parser("open", help="Abrir el ultimo material HTML en el navegador")
    p.add_argument("course")
    p.add_argument("--type", choices=["summary", "guide", "rapid-review"])
    p.add_argument("--contains", help="Filtrar por unidad/tema en el nombre")
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("validate", help="Validar consistencia academica, fuentes y artefactos derivados")
    p.add_argument("course")
    p.set_defaults(func=cmd_validate)

    return ap


def main() -> None:
    if len(sys.argv) == 1:
        interactive_menu()
        return
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    try:
        args.func(args)
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
