#!/usr/bin/env python3
"""Autonomous adversarial QA laboratory for the University Study engine."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DEFAULT_QA_ROOT = ROOT / ".study" / "engine-qa"
DEFAULT_COURSES_ROOT = ROOT / "materias"
REPORTS_ROOT = ROOT / "qa" / "reports"

sys.path.insert(0, str(ROOT))
from scripts.course_layout import REGISTRIES, sync_units  # noqa: E402
from scripts.unit_identity import stable_unit_id_from_row  # noqa: E402

PROTECTED_PATHS = (
    "study.py", "core", "rules", "pipelines", "contracts", "vendor", "scripts",
    "study_mcp", "config", "actions", "assets", "design",
)
ALLOWED_SCRIPTS = {
    "study.py", "academic_context.py", "artifact_integrity.py", "artifact_state.py",
    "claim_candidates.py", "concept_graph.py", "figure_assets.py", "pdf_probe.py",
    "pipeline_run.py", "publish_artifact.py", "publish_quiz.py", "quiz_artifact.py",
    "quiz_browser_check.py", "quiz_run.py", "render_study.py", "semantic_claims.py",
    "study_tracker.py", "sync_materials.py", "topic_catalog.py", "transcript_tools.py",
}
SEVERITIES = ("critical", "high", "medium", "low")
QA_COURSE_PREFIX = "qa-engine-"
MAX_CAPTURE = 20000


class QaError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def tree_fingerprint() -> dict[str, str]:
    rows: dict[str, str] = {}
    for rel in PROTECTED_PATHS:
        target = ROOT / rel
        if target.is_file():
            rows[rel] = sha256_file(target)
        elif target.is_dir():
            for file in sorted(p for p in target.rglob("*") if p.is_file()):
                if "__pycache__" in file.parts or file.suffix in {".pyc", ".pyo"}:
                    continue
                rows[safe_relative(ROOT, file)] = sha256_file(file)
    return rows


def fingerprint_digest(rows: dict[str, str]) -> str:
    payload = "\n".join(f"{k}\0{rows[k]}" for k in sorted(rows)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def workspace_snapshot(course: Path) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    if course.exists():
        for file in sorted(p for p in course.rglob("*") if p.is_file()):
            rel = safe_relative(course, file)
            row: dict[str, Any] = {"sha256": sha256_file(file), "bytes": file.stat().st_size}
            if file.suffix.lower() == ".json":
                try:
                    value = json.loads(file.read_text(encoding="utf-8"))
                    row["json_valid"] = True
                    if isinstance(value, dict):
                        row["json_keys"] = sorted(value.keys())
                except (UnicodeDecodeError, json.JSONDecodeError, OSError):
                    row["json_valid"] = False
            files[rel] = row
    payload = "\n".join(f"{k}\0{files[k]['sha256']}" for k in sorted(files)).encode("utf-8")
    return {"course": str(course), "files": files, "digest": hashlib.sha256(payload).hexdigest()}


def snapshot_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    a, b = before.get("files", {}), after.get("files", {})
    return {
        "added": sorted(set(b) - set(a)),
        "removed": sorted(set(a) - set(b)),
        "changed": sorted(k for k in set(a) & set(b) if a[k].get("sha256") != b[k].get("sha256")),
    }


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def qa_root_from_env() -> Path:
    return Path(os.environ.get("STUDY_ENGINE_QA_ROOT", DEFAULT_QA_ROOT)).resolve()


def courses_root_from_env() -> Path:
    return Path(os.environ.get("STUDY_ENGINE_QA_COURSES_ROOT", DEFAULT_COURSES_ROOT)).resolve()


def resolve_run(qa_root: Path, value: str) -> Path:
    if value == "latest":
        data = read_json(qa_root / "latest.json", {}) or {}
        raw = str(data.get("run_dir", "")).strip()
        if not raw:
            raise QaError("No hay un Engine QA run reciente.")
        path = Path(raw)
    else:
        path = qa_root / "runs" / value
    path = path.resolve()
    try:
        path.relative_to((qa_root / "runs").resolve())
    except ValueError as exc:
        raise QaError("El run solicitado queda fuera del QA root.") from exc
    if not (path / "manifest.json").is_file():
        raise QaError(f"Run inexistente o incompleto: {path}")
    return path


def manifest_for(run_dir: Path) -> dict[str, Any]:
    return read_json(run_dir / "manifest.json", {}) or {}


def save_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    write_json(run_dir / "manifest.json", manifest)


def course_for(run_dir: Path) -> Path:
    manifest = manifest_for(run_dir)
    path = Path(str(manifest.get("course_path", ""))).resolve()
    if not path.name.startswith(QA_COURSE_PREFIX):
        raise QaError("El manifest no apunta a una materia sintética QA.")
    return path


def journal(run_dir: Path, kind: str, **payload: Any) -> dict[str, Any]:
    manifest = manifest_for(run_dir)
    manifest["step_count"] = int(manifest.get("step_count", 0)) + 1
    row = {"step": manifest["step_count"], "time": utc_now(), "kind": kind, **payload}
    append_jsonl(run_dir / "journal.jsonl", row)
    save_manifest(run_dir, manifest)
    return row


def academic_template() -> dict[str, Any]:
    return {
        "version": 1,
        "identity": {"subject": "QA Sintética de Programación", "institution": "University Study Engine QA"},
        "units": [
            {"id": "unidad-1", "name": "Algoritmos y datos", "topics": ["Algoritmos", "Variables"], "status": "active"},
            {"id": "unidad-2", "name": "Control", "topics": ["Condicionales", "Iteraciones"], "status": "active"},
            {"id": "unidad-3", "name": "Funciones", "topics": ["Funciones", "Parámetros"], "status": "active"},
        ],
        "assessments": [{
            "id": "parcial-1", "type": "parcial", "name": "Parcial 1", "status": "scheduled",
            "scope": [
                {"type": "unit", "ref": "unidad-1", "status": "confirmed", "evidence": ["qa:programa"]},
                {"type": "unit", "ref": "unidad-2", "status": "likely", "evidence": ["qa:clase"]},
            ],
        }],
        "rules": [], "claims": [], "claim_candidates": [], "official_status": {},
    }


def write_pdf(path: Path, pages: list[str]) -> bool:
    try:
        import fitz
    except Exception:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(56, 64, 539, 780), text, fontsize=12, fontname="helv")
    doc.save(path)
    doc.close()
    return True


def create_synthetic_course(course: Path, seed: int) -> dict[str, Any]:
    if course.exists():
        raise QaError(f"La materia QA ya existe: {course}")
    rng = random.Random(seed)
    (course / "academico").mkdir(parents=True, exist_ok=True)
    (course / "fuentes").mkdir(parents=True, exist_ok=True)
    write_json(course / "academico" / "academic.json", academic_template())
    (course / "contexto.md").write_text("# Contexto QA\n\nMateria sintética. No contiene datos reales.\n", encoding="utf-8")
    sync_units(course)
    sources = {
        "unidades/unidad-1/fuentes/oficiales/fundamentos.txt": "Un algoritmo es una secuencia finita y ordenada de pasos.\nUna variable almacena un valor que puede cambiar.\n",
        "unidades/unidad-1/fuentes/transcripciones/clase-1.srt": "1\n00:00:05,000 --> 00:00:10,000\nProfesor: Ojo, distingan asignación de igualdad.\n\n2\n00:00:12,000 --> 00:00:17,000\nProfesor: Un contador suele aumentar de uno en uno.\n",
        "unidades/unidad-2/fuentes/oficiales/control.txt": "Una condición decide entre caminos.\nUna iteración repite un bloque mientras se cumpla su condición.\n",
        "unidades/unidad-3/fuentes/oficiales/funciones.txt": "Una función encapsula una tarea y puede recibir parámetros.\n",
    }
    for rel, text in sources.items():
        path = course / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    marker = ["ñ", "á", "β", "λ", "漢字"][rng.randrange(5)]
    (course / "fuentes" / "programa-general.txt").write_text(f"Programa QA. Unicode: {marker}.\n", encoding="utf-8")
    pdf_generated = write_pdf(
        course / "unidades/unidad-1/fuentes/oficiales/apunte.pdf",
        ["ENGINE QA — Algoritmos\n\nEntrada, proceso y salida.", "ENGINE QA — Variables\n\nAsignación modifica estado."],
    )
    return {"pdf_generated": pdf_generated, "source_count": len(sources) + 1 + int(pdf_generated)}


def start_run(qa_root: Path, courses_root: Path, budget: int, seed: int, provider: str) -> dict[str, Any]:
    if not 1 <= budget <= 200:
        raise QaError("El presupuesto debe estar entre 1 y 200 experimentos.")
    qa_root.mkdir(parents=True, exist_ok=True)
    courses_root.mkdir(parents=True, exist_ok=True)
    run_id = f"{compact_timestamp()}-s{seed}"
    run_dir = qa_root / "runs" / run_id
    suffix = 1
    while run_dir.exists():
        run_id = f"{compact_timestamp()}-s{seed}-{suffix}"
        run_dir = qa_root / "runs" / run_id
        suffix += 1
    run_dir.mkdir(parents=True)
    course = courses_root / f"{QA_COURSE_PREFIX}{re.sub(r'[^a-z0-9]+', '-', run_id.lower()).strip('-')}"
    generated = create_synthetic_course(course, seed)
    engine_rows = tree_fingerprint()
    initial = workspace_snapshot(course)
    write_json(run_dir / "snapshots/000-initial.json", initial)
    manifest = {
        "version": 1, "run_id": run_id, "created_at": utc_now(), "provider": provider,
        "seed": seed, "budget": budget, "experiments": 0, "step_count": 0, "findings": 0,
        "blocked": False, "course_slug": course.name, "course_path": str(course.resolve()),
        "engine_sha256": fingerprint_digest(engine_rows), "engine_files": engine_rows,
        "initial_workspace_sha256": initial["digest"], "generated": generated, "coverage": [],
    }
    save_manifest(run_dir, manifest)
    write_json(qa_root / "latest.json", {"run_id": run_id, "run_dir": str(run_dir.resolve())})
    journal(run_dir, "start", budget=budget, seed=seed, provider=provider, generated=generated)
    return {"ok": True, "run_id": run_id, "run_dir": str(run_dir), "course": str(course), **generated}


def assert_not_blocked(run_dir: Path) -> dict[str, Any]:
    manifest = manifest_for(run_dir)
    if manifest.get("blocked"):
        raise QaError("El run está bloqueado por una violación previa de seguridad/integridad.")
    return manifest


def verify_engine_unchanged(run_dir: Path) -> tuple[bool, dict[str, list[str]]]:
    before = manifest_for(run_dir).get("engine_files", {})
    now = tree_fingerprint()
    diff = {
        "added": sorted(set(now) - set(before)),
        "removed": sorted(set(before) - set(now)),
        "changed": sorted(k for k in set(now) & set(before) if now[k] != before[k]),
    }
    return not any(diff.values()), diff


def block_for_engine_change(run_dir: Path, diff: dict[str, list[str]]) -> None:
    manifest = manifest_for(run_dir)
    manifest.update({"blocked": True, "block_reason": "engine-mutated-during-qa", "engine_diff": diff})
    save_manifest(run_dir, manifest)
    journal(run_dir, "fatal", reason="engine-mutated-during-qa", diff=diff)


def record_hypothesis(run_dir: Path, text: str, invariant: str, category: str) -> dict[str, Any]:
    manifest = assert_not_blocked(run_dir)
    experiments, budget = int(manifest.get("experiments", 0)), int(manifest.get("budget", 0))
    if experiments >= budget:
        raise QaError(f"Presupuesto agotado: {experiments}/{budget}. Ejecutá finish.")
    manifest["experiments"] = experiments + 1
    coverage = list(manifest.get("coverage", []))
    if category not in coverage:
        coverage.append(category)
    manifest["coverage"] = coverage
    save_manifest(run_dir, manifest)
    row = journal(run_dir, "hypothesis", experiment=manifest["experiments"], invariant=invariant, category=category, text=text)
    return {"ok": True, "experiment": manifest["experiments"], "remaining": budget - manifest["experiments"], "step": row["step"]}


def expand_arg(value: str, run_dir: Path) -> str:
    course = course_for(run_dir)
    return {"@course": str(course), "@slug": course.name, "@run": str(run_dir), "@root": str(ROOT)}.get(value, value)


def validate_exec_args(run_dir: Path, script: str, args: list[str]) -> tuple[Path, list[str]]:
    if script not in ALLOWED_SCRIPTS:
        raise QaError(f"Script no permitido: {script}")
    target = ROOT / script if script == "study.py" else SCRIPTS / script
    if not target.is_file():
        raise QaError(f"Script inexistente: {target}")
    expanded = [expand_arg(v, run_dir) for v in args]
    course = course_for(run_dir).resolve()
    if script == "study.py" and course.name not in " ".join(expanded) and str(course) not in expanded:
        raise QaError("study.py sólo puede apuntar a la materia QA del run.")
    for idx, value in enumerate(expanded):
        if value == "--course" and idx + 1 < len(expanded) and Path(expanded[idx + 1]).resolve() != course:
            raise QaError("--course debe apuntar a la materia QA del run.")
    return target, expanded


def exec_engine(run_dir: Path, script: str, args: list[str], expect_code: int | None, timeout: int) -> dict[str, Any]:
    assert_not_blocked(run_dir)
    target, expanded = validate_exec_args(run_dir, script, args)
    engine_ok, engine_diff = verify_engine_unchanged(run_dir)
    if not engine_ok:
        block_for_engine_change(run_dir, engine_diff)
        raise QaError("El engine cambió desde el inicio del QA run.")
    course = course_for(run_dir)
    before = workspace_snapshot(course)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cp = subprocess.run(
        [sys.executable, str(target), *expanded], cwd=ROOT, text=True, capture_output=True,
        encoding="utf-8", errors="replace", timeout=max(1, min(timeout, 120)), env=env,
    )
    after = workspace_snapshot(course)
    engine_ok, engine_diff = verify_engine_unchanged(run_dir)
    result = {
        "script": script, "args": args, "expanded_args": expanded, "returncode": cp.returncode,
        "expected_returncode": expect_code, "stdout": (cp.stdout or "")[-MAX_CAPTURE:],
        "stderr": (cp.stderr or "")[-MAX_CAPTURE:], "workspace_before": before["digest"],
        "workspace_after": after["digest"], "workspace_diff": snapshot_diff(before, after),
        "engine_unchanged": engine_ok,
    }
    row = journal(run_dir, "exec", **result)
    result["step"] = row["step"]
    write_json(run_dir / "steps" / f"{row['step']:04d}-exec.json", result)
    if not engine_ok:
        block_for_engine_change(run_dir, engine_diff)
        result.update({"ok": False, "fatal": "engine-mutated-during-qa"})
        return result
    result["ok"] = expect_code is None or cp.returncode == expect_code
    return result


def resolve_course_path(course: Path, relative: str) -> Path:
    candidate = (course / relative).resolve()
    try:
        candidate.relative_to(course.resolve())
    except ValueError as exc:
        raise QaError("La mutación intenta salir de la materia QA.") from exc
    return candidate


def mutate_course(run_dir: Path, op: str, path: str, text: str = "", dest: str = "", old: str = "", new: str = "") -> dict[str, Any]:
    assert_not_blocked(run_dir)
    course = course_for(run_dir)
    before = workspace_snapshot(course)
    target = resolve_course_path(course, path)
    if op in {"write", "append"}:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a" if op == "append" else "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    elif op == "delete":
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    elif op in {"move", "copy"}:
        if not dest:
            raise QaError(f"{op} requiere --dest.")
        destination = resolve_course_path(course, dest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if op == "move":
            shutil.move(str(target), str(destination))
        elif target.is_dir():
            shutil.copytree(target, destination)
        else:
            shutil.copy2(target, destination)
    elif op == "replace":
        if not target.is_file():
            raise QaError(f"No existe archivo: {path}")
        raw = target.read_text(encoding="utf-8")
        if old not in raw:
            raise QaError("--old no aparece en el archivo.")
        target.write_text(raw.replace(old, new), encoding="utf-8", newline="\n")
    else:
        raise QaError(f"Mutación no soportada: {op}")
    after = workspace_snapshot(course)
    engine_ok, engine_diff = verify_engine_unchanged(run_dir)
    result = {
        "op": op, "path": path, "dest": dest or None, "workspace_before": before["digest"],
        "workspace_after": after["digest"], "workspace_diff": snapshot_diff(before, after), "engine_unchanged": engine_ok,
    }
    row = journal(run_dir, "mutation", **result)
    result["step"] = row["step"]
    write_json(run_dir / "steps" / f"{row['step']:04d}-mutation.json", result)
    if not engine_ok:
        block_for_engine_change(run_dir, engine_diff)
    result["ok"] = engine_ok
    return result


def checkpoint(run_dir: Path, label: str) -> dict[str, Any]:
    assert_not_blocked(run_dir)
    course = course_for(run_dir)
    current = workspace_snapshot(course)
    shots = sorted((run_dir / "snapshots").glob("*.json"))
    previous = read_json(shots[-1], {"files": {}}) if shots else {"files": {}}
    diff = snapshot_diff(previous, current)
    row = journal(run_dir, "checkpoint", label=label, workspace_sha256=current["digest"], diff=diff)
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "checkpoint"
    out = run_dir / "snapshots" / f"{row['step']:04d}-{slug}.json"
    write_json(out, current)
    return {"ok": True, "step": row["step"], "snapshot": str(out), "diff": diff}


def _issue(rows: list[dict[str, Any]], invariant: str, message: str, path: str = "", severity: str = "high") -> None:
    rows.append({"invariant": invariant, "severity": severity, "message": message, "path": path or None})


def check_invariants(run_dir: Path) -> dict[str, Any]:
    manifest = manifest_for(run_dir)
    course = course_for(run_dir)
    issues: list[dict[str, Any]] = []
    engine_ok, engine_diff = verify_engine_unchanged(run_dir)
    if not engine_ok:
        _issue(issues, "engine-immutable", f"Engine cambió: {engine_diff}", severity="critical")
    academic_path = course / "academico/academic.json"
    try:
        academic = json.loads(academic_path.read_text(encoding="utf-8"))
    except Exception as exc:
        academic = {}
        _issue(issues, "academic-json-valid", f"academic.json inválido: {type(exc).__name__}: {exc}", "academico/academic.json", "critical")
    expected_units = [stable_unit_id_from_row(r) for r in academic.get("units", []) if isinstance(r, dict) and stable_unit_id_from_row(r)] if isinstance(academic, dict) else []
    unit_root = course / "unidades"
    actual_units = sorted(p.name for p in unit_root.iterdir() if p.is_dir()) if unit_root.is_dir() else []
    if sorted(expected_units) != actual_units:
        _issue(issues, "layout-matches-academic", f"Unidades físicas {actual_units} != academic {sorted(expected_units)}", "unidades")
    for json_file in sorted(course.rglob("*.json")):
        try:
            json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as exc:
            _issue(issues, "course-json-valid", f"JSON inválido: {type(exc).__name__}: {exc}", safe_relative(course, json_file), "critical")
    for unit_id in expected_units:
        root = course / "unidades" / unit_id
        values: dict[str, dict[str, Any]] = {}
        for kind, (relative, _key, _version) in REGISTRIES.items():
            path = root / relative
            if not path.is_file():
                _issue(issues, "registry-present", f"Falta registro {kind}", safe_relative(course, path), "critical")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            values[kind] = data if isinstance(data, dict) else {}
        concepts_doc, topics_doc, progress_doc, figures_doc = (values.get(k, {}) for k in ("concepts", "topics", "progress", "figures"))
        concepts = concepts_doc.get("concepts", {}) if isinstance(concepts_doc, dict) else {}
        known = {str(v.get("id") or k).strip() for k, v in concepts.items() if isinstance(v, dict) and str(v.get("id") or k).strip()}
        for key, value in concepts.items() if isinstance(concepts, dict) else []:
            owner = str(value.get("unit_id", "")).strip() if isinstance(value, dict) else ""
            if owner and owner != unit_id:
                _issue(issues, "concept-unit-local", f"Concepto {key} declara unit_id={owner}", f"unidades/{unit_id}/conocimiento/concepts.json")
        assigned: list[str] = []
        topics = topics_doc.get("topics", {}) if isinstance(topics_doc, dict) else {}
        if topics_doc and str(topics_doc.get("unit_id", unit_id)) != unit_id:
            _issue(issues, "topic-document-unit", f"topics.json declara unit_id={topics_doc.get('unit_id')}", f"unidades/{unit_id}/conocimiento/topics.json")
        for topic_key, topic in topics.items() if isinstance(topics, dict) else []:
            if not isinstance(topic, dict):
                _issue(issues, "topic-shape", f"Topic {topic_key} no es objeto", f"unidades/{unit_id}/conocimiento/topics.json")
                continue
            for cid in map(str, topic.get("concept_ids", []) or []):
                assigned.append(cid)
                if cid not in known:
                    _issue(issues, "topic-concept-exists", f"Topic {topic_key} referencia inexistente {cid}", f"unidades/{unit_id}/conocimiento/topics.json")
        dup = sorted({cid for cid in assigned if assigned.count(cid) > 1})
        if dup:
            _issue(issues, "one-primary-topic", f"Conceptos en más de un topic: {dup}", f"unidades/{unit_id}/conocimiento/topics.json")
        unassigned = [str(x) for x in topics_doc.get("unassigned_concept_ids", []) or []] if isinstance(topics_doc, dict) else []
        overlap = sorted(set(assigned) & set(unassigned))
        if overlap:
            _issue(issues, "topic-assignment-exclusive", f"Asignados y unassigned: {overlap}", f"unidades/{unit_id}/conocimiento/topics.json")
        unknown = sorted(set(unassigned) - known)
        if unknown:
            _issue(issues, "unassigned-concept-exists", f"Unassigned inexistentes: {unknown}", f"unidades/{unit_id}/conocimiento/topics.json")
        uncovered = sorted(known - set(assigned) - set(unassigned))
        if uncovered:
            _issue(issues, "topic-coverage-explicit", f"Conceptos sin topic ni unassigned: {uncovered}", f"unidades/{unit_id}/conocimiento/topics.json")
        progress = progress_doc.get("concepts", {}) if isinstance(progress_doc, dict) else {}
        bad_progress = sorted(str(v.get("id") or k) for k, v in progress.items() if isinstance(v, dict) and str(v.get("id") or k) not in known)
        if bad_progress:
            _issue(issues, "progress-concept-exists", f"Progress desconocido: {bad_progress}", f"unidades/{unit_id}/progreso/progress.json")
        figures = figures_doc.get("figures", {}) if isinstance(figures_doc, dict) else {}
        for key, value in figures.items() if isinstance(figures, dict) else []:
            owner = str(value.get("unit_id", "")).strip() if isinstance(value, dict) else ""
            if owner and owner != unit_id:
                _issue(issues, "figure-unit-local", f"Figura {key} declara unit_id={owner}", f"unidades/{unit_id}/conocimiento/figures.json")
    invariants = [
        "engine-immutable", "academic-json-valid", "layout-matches-academic", "course-json-valid", "registry-present",
        "concept-unit-local", "topic-document-unit", "topic-concept-exists", "one-primary-topic", "topic-assignment-exclusive",
        "unassigned-concept-exists", "topic-coverage-explicit", "progress-concept-exists", "figure-unit-local",
    ]
    report = {"ok": not issues, "run_id": manifest.get("run_id"), "checked_at": utc_now(), "issues": issues, "invariants_checked": invariants}
    row = journal(run_dir, "check", ok=report["ok"], issues=issues, invariants_checked=invariants)
    report["step"] = row["step"]
    write_json(run_dir / "checks" / f"{row['step']:04d}.json", report)
    if not engine_ok:
        block_for_engine_change(run_dir, engine_diff)
    return report


def recent_journal(run_dir: Path, count: int = 14) -> list[dict[str, Any]]:
    path = run_dir / "journal.jsonl"
    rows: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows[-max(1, min(count, 50)):]


def record_finding(run_dir: Path, title: str, severity: str, invariant: str, expected: str, actual: str, notes: str, confirmed: bool) -> dict[str, Any]:
    manifest = assert_not_blocked(run_dir)
    if severity not in SEVERITIES:
        raise QaError(f"Severidad inválida: {severity}")
    if not confirmed:
        raise QaError("Un finding debe estar confirmado antes de registrarse.")
    number = int(manifest.get("findings", 0)) + 1
    finding_id = f"QA-{number:03d}"
    evidence = recent_journal(run_dir)
    finding = {
        "version": 1, "id": finding_id, "run_id": manifest.get("run_id"), "created_at": utc_now(), "title": title,
        "severity": severity, "invariant": invariant, "expected": expected, "actual": actual, "notes": notes,
        "confirmed": True, "seed": manifest.get("seed"), "course_slug": manifest.get("course_slug"),
        "evidence_steps": [r.get("step") for r in evidence], "evidence": evidence,
    }
    d = run_dir / "findings" / finding_id
    write_json(d / "finding.json", finding)
    lines = [
        f"# {finding_id} — {title}", "", f"- Severidad: **{severity}**", f"- Invariante: `{invariant}`",
        f"- Run: `{manifest.get('run_id')}`", f"- Seed: `{manifest.get('seed')}`", "", "## Esperado", expected,
        "", "## Actual", actual, "", "## Evidencia reciente",
    ]
    lines += [f"- paso {r.get('step')}: `{r.get('kind')}` {r.get('script') or r.get('op') or r.get('label') or ''}".rstrip() for r in evidence]
    if notes:
        lines += ["", "## Notas", notes]
    (d / "reproduction.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest["findings"] = number
    save_manifest(run_dir, manifest)
    journal(run_dir, "finding", id=finding_id, severity=severity, invariant=invariant, title=title)
    return {"ok": True, "id": finding_id, "path": str(d)}


def finish_run(run_dir: Path, export: bool) -> dict[str, Any]:
    manifest = manifest_for(run_dir)
    check = check_invariants(run_dir) if not manifest.get("blocked") else {
        "ok": False, "issues": [{"invariant": "run-blocked", "severity": "critical", "message": manifest.get("block_reason", "blocked")}]
    }
    manifest = manifest_for(run_dir)
    dirs = sorted((run_dir / "findings").glob("QA-*")) if (run_dir / "findings").is_dir() else []
    findings = [read_json(d / "finding.json", {}) for d in dirs]
    summary = {
        "version": 1, "run_id": manifest.get("run_id"), "provider": manifest.get("provider"), "seed": manifest.get("seed"),
        "budget": manifest.get("budget"), "experiments": manifest.get("experiments"), "steps": manifest.get("step_count"),
        "findings": len(findings), "blocked": bool(manifest.get("blocked")), "coverage": manifest.get("coverage", []),
        "final_invariants_ok": bool(check.get("ok")), "final_issues": check.get("issues", []),
        "finding_rows": [{"id": f.get("id"), "severity": f.get("severity"), "invariant": f.get("invariant"), "title": f.get("title")} for f in findings],
        "finished_at": utc_now(),
    }
    write_json(run_dir / "report.json", summary)
    md = [
        "# Engine QA Report", "", f"- Run: `{summary['run_id']}`", f"- Provider: `{summary['provider']}`", f"- Seed: `{summary['seed']}`",
        f"- Experimentos: **{summary['experiments']}/{summary['budget']}**", f"- Pasos registrados: **{summary['steps']}**",
        f"- Hallazgos confirmados: **{summary['findings']}**", f"- Invariantes finales: **{'PASS' if summary['final_invariants_ok'] else 'FAIL'}**",
        f"- Bloqueado: **{'sí' if summary['blocked'] else 'no'}**", "", "## Cobertura",
    ]
    md += [f"- {x}" for x in summary["coverage"]] or ["- sin categorías registradas"]
    md += ["", "## Hallazgos"]
    md += [f"- **{r['id']} · {r['severity'].upper()}** — {r['title']} (`{r['invariant']}`)" for r in summary["finding_rows"]] or ["- No se registraron hallazgos confirmados."]
    if summary["final_issues"]:
        md += ["", "## Issues de invariantes al cierre"] + [
            f"- **{i.get('severity','high').upper()}** `{i.get('invariant')}` — {i.get('message','')}" for i in summary["final_issues"]
        ]
    (run_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    history_path = run_dir.parent.parent / "history.json"
    hist = read_json(history_path, {"version": 1, "runs": []}) or {"version": 1, "runs": []}
    runs = list(hist.get("runs", []))
    runs.append({
        "run_id": summary["run_id"], "finished_at": summary["finished_at"], "provider": summary["provider"],
        "seed": summary["seed"], "experiments": summary["experiments"], "findings": summary["findings"],
        "coverage": summary["coverage"], "finding_rows": summary["finding_rows"],
    })
    hist["runs"] = runs[-100:]
    write_json(history_path, hist)
    exported = None
    if export:
        destination = REPORTS_ROOT / str(summary["run_id"])
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        shutil.copy2(run_dir / "report.json", destination / "report.json")
        shutil.copy2(run_dir / "report.md", destination / "report.md")
        if (run_dir / "findings").is_dir():
            shutil.copytree(run_dir / "findings", destination / "findings")
        write_json(destination / "replay.json", {
            "version": 1, "run_id": summary["run_id"], "seed": summary["seed"], "course_slug": manifest.get("course_slug"),
            "journal": recent_journal(run_dir, 50),
            "note": "Compact replay context; minimize each bug to deterministic engine operations before fixing.",
        })
        exported = str(destination)
    journal(run_dir, "finish", report=str(run_dir / "report.md"), exported=exported)
    return {"ok": not summary["blocked"], "report": str(run_dir / "report.md"), "exported": exported, **summary}


def history(qa_root: Path) -> dict[str, Any]:
    data = read_json(qa_root / "history.json", {"version": 1, "runs": []}) or {"version": 1, "runs": []}
    runs = data.get("runs", [])
    coverage: dict[str, int] = {}
    findings: dict[str, int] = {}
    for row in runs:
        for c in row.get("coverage", []):
            coverage[c] = coverage.get(c, 0) + 1
        for f in row.get("finding_rows", []):
            inv = str(f.get("invariant", "unknown"))
            findings[inv] = findings.get(inv, 0) + 1
    return {"version": 1, "runs": runs[-20:], "coverage_counts": coverage, "finding_counts": findings}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Autonomous adversarial QA laboratory for the University Study engine")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("start")
    p.add_argument("--budget", type=int, default=25)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--provider", default="unknown")
    p = sub.add_parser("info")
    p.add_argument("--run", default="latest")
    sub.add_parser("history")
    p = sub.add_parser("hypothesis")
    p.add_argument("--run", default="latest")
    p.add_argument("--invariant", required=True)
    p.add_argument("--category", required=True)
    p.add_argument("--text", required=True)
    p = sub.add_parser("exec")
    p.add_argument("--run", default="latest")
    p.add_argument("--script", required=True)
    p.add_argument("--expect-code", type=int, default=0)
    p.add_argument("--any-code", action="store_true")
    p.add_argument("--timeout", type=int, default=45)
    p.add_argument("args", nargs=argparse.REMAINDER)
    p = sub.add_parser("mutate")
    p.add_argument("--run", default="latest")
    p.add_argument("--op", choices=["write", "append", "delete", "move", "copy", "replace"], required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--dest", default="")
    p.add_argument("--text", default="")
    p.add_argument("--old", default="")
    p.add_argument("--new", default="")
    p = sub.add_parser("checkpoint")
    p.add_argument("--run", default="latest")
    p.add_argument("--label", required=True)
    p = sub.add_parser("check")
    p.add_argument("--run", default="latest")
    p = sub.add_parser("finding")
    p.add_argument("--run", default="latest")
    p.add_argument("--title", required=True)
    p.add_argument("--severity", choices=SEVERITIES, required=True)
    p.add_argument("--invariant", required=True)
    p.add_argument("--expected", required=True)
    p.add_argument("--actual", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--confirmed", action="store_true")
    p = sub.add_parser("finish")
    p.add_argument("--run", default="latest")
    p.add_argument("--export", action="store_true")
    return ap


def main() -> int:
    args = parser().parse_args()
    qa_root, courses_root = qa_root_from_env(), courses_root_from_env()
    try:
        if args.command == "start":
            result = start_run(qa_root, courses_root, args.budget, args.seed, args.provider)
        elif args.command == "history":
            result = history(qa_root)
        else:
            run_dir = resolve_run(qa_root, getattr(args, "run", "latest"))
            if args.command == "info":
                m = manifest_for(run_dir)
                result = {
                    "ok": True, "run_id": m.get("run_id"), "course_slug": m.get("course_slug"), "course_path": m.get("course_path"),
                    "budget": m.get("budget"), "experiments": m.get("experiments"), "findings": m.get("findings"),
                    "blocked": m.get("blocked"), "coverage": m.get("coverage", []), "run_dir": str(run_dir),
                }
            elif args.command == "hypothesis":
                result = record_hypothesis(run_dir, args.text, args.invariant, args.category)
            elif args.command == "exec":
                rem = list(args.args)
                rem = rem[1:] if rem and rem[0] == "--" else rem
                result = exec_engine(run_dir, args.script, rem, None if args.any_code else args.expect_code, args.timeout)
            elif args.command == "mutate":
                result = mutate_course(run_dir, args.op, args.path, args.text, args.dest, args.old, args.new)
            elif args.command == "checkpoint":
                result = checkpoint(run_dir, args.label)
            elif args.command == "check":
                result = check_invariants(run_dir)
            elif args.command == "finding":
                result = record_finding(run_dir, args.title, args.severity, args.invariant, args.expected, args.actual, args.notes, args.confirmed)
            elif args.command == "finish":
                result = finish_run(run_dir, args.export)
            else:
                raise QaError(f"Comando desconocido: {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    except (QaError, OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
