#!/usr/bin/env python3
"""Generate thin Claude/Codex adapters from the shared portable core.

The generated files are runtime adapters, not methodological sources of truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS_PATH = ROOT / "config" / "actions.json"
PLATFORMS = (".claude", ".agents")
ACTION_MARKER = "# Acción portable:"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def action_body(name: str, mode: str) -> str:
    return f"""# Acción portable: {name}\n\n**Modo fijo:** `{mode}`\n\nEste archivo es un adaptador fino. No contiene metodología propia.\n\n1. Leé `../../../core/ROUTER.md`.\n2. Leé `../../../actions/ARGUMENTS.md`.\n3. Ejecutá exactamente `../../../pipelines/{name}.md`.\n4. Usá `rules/`, `contracts/` y `vendor/` sólo cuando el pipeline los indique.\n5. No reemplaces el pipeline con comportamiento específico del proveedor. Las optimizaciones de `providers/` son opcionales y deben conservar los mismos handoffs.\n"""


def core_body() -> str:
    return """# University Study — adaptador portable\n\nLeé `../../../core/ROUTER.md` y usalo como fuente de verdad. Determiná la acción adecuada a partir del pedido natural y seguí el archivo correspondiente en `../../../pipelines/`. No dupliques metodología en este adaptador.\n"""


def write_skill(platform: str, name: str, spec: dict) -> None:
    d = ROOT / platform / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    if platform == ".claude":
        front = (
            "---\n"
            f"name: {name}\n"
            f"description: {spec['description']}\n"
            f"argument-hint: \"{spec['hint']}\"\n"
            "disable-model-invocation: true\n"
            "---\n"
        )
    else:
        front = (
            "---\n"
            f"name: {name}\n"
            f"description: {spec['description']}\n"
            "---\n"
        )
    (d / "SKILL.md").write_text(front + action_body(name, spec["mode"]), encoding="utf-8")
    if platform == ".agents":
        policy = d / "agents" / "openai.yaml"
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text("policy:\n  allow_implicit_invocation: false\n", encoding="utf-8")


def write_core(platform: str) -> None:
    d = ROOT / platform / "skills" / "university-study"
    d.mkdir(parents=True, exist_ok=True)
    front = """---
name: university-study
description: Portable university study workflow. Uses the shared project core to ingest sources, learn topics or concepts, summarize, review, quiz, simulate assessments and track progress. Maintenance audits stay internal.
---
"""
    (d / "SKILL.md").write_text(front + core_body(), encoding="utf-8")


def sync_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def sync_portable_skills(platform: str) -> None:
    sync_tree(ROOT / "vendor" / "humanizer", ROOT / platform / "skills" / "humanizer")
    sync_tree(ROOT / "vendor" / "frontend-design", ROOT / platform / "skills" / "frontend-design")
    for name in ("study-design", "study-design-reviewer"):
        sync_tree(ROOT / "skills-src" / name, ROOT / platform / "skills" / name)


def managed_action_dirs(platform: str) -> list[Path]:
    skills = ROOT / platform / "skills"
    if not skills.is_dir():
        return []
    result: list[Path] = []
    for d in skills.iterdir():
        p = d / "SKILL.md"
        if d.is_dir() and p.is_file() and ACTION_MARKER in p.read_text(encoding="utf-8"):
            result.append(d)
    return result


def prune_stale_action_skills(platform: str, actions: dict) -> None:
    for d in managed_action_dirs(platform):
        if d.name not in actions:
            shutil.rmtree(d)


def generate() -> None:
    actions = json.loads(ACTIONS_PATH.read_text(encoding="utf-8"))
    for platform in PLATFORMS:
        skills = ROOT / platform / "skills"
        skills.mkdir(parents=True, exist_ok=True)
        prune_stale_action_skills(platform, actions)
        write_core(platform)
        for name, spec in actions.items():
            write_skill(platform, name, spec)
        sync_portable_skills(platform)


def verify() -> list[str]:
    errors: list[str] = []
    actions = json.loads(ACTIONS_PATH.read_text(encoding="utf-8"))
    for platform in PLATFORMS:
        for d in managed_action_dirs(platform):
            if d.name not in actions:
                errors.append(f"stale public action adapter: {d.relative_to(ROOT)}")
        for name, spec in actions.items():
            p = ROOT / platform / "skills" / name / "SKILL.md"
            if not p.exists():
                errors.append(f"missing {p.relative_to(ROOT)}")
                continue
            text = p.read_text(encoding="utf-8")
            for needle in (f"`{spec['mode']}`", f"../../../pipelines/{name}.md", "../../../core/ROUTER.md"):
                if needle not in text:
                    errors.append(f"{p.relative_to(ROOT)} missing {needle}")
        for source_root, name in ((ROOT / "vendor", "humanizer"), (ROOT / "vendor", "frontend-design"), (ROOT / "skills-src", "study-design"), (ROOT / "skills-src", "study-design-reviewer")):
            src = source_root / name / "SKILL.md"
            dst = ROOT / platform / "skills" / name / "SKILL.md"
            if not dst.exists() or sha256(dst) != sha256(src):
                errors.append(f"{name} drift in {platform}")
    for name in actions:
        c = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[-1].strip()
        a = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[-1].strip()
        if c != a:
            errors.append(f"adapter body drift for {name}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["generate", "verify"], nargs="?", default="generate")
    args = ap.parse_args()
    if args.command == "generate":
        generate()
        errors = verify()
    else:
        errors = verify()
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
