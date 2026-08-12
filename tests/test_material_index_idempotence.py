from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC_MATERIALS = ROOT / "scripts" / "sync_materials.py"
STUDY = ROOT / "study.py"
CLI_COURSE = ROOT / "materias" / "material-index-unittest"

sys.path.insert(0, str(ROOT))
from scripts.course_layout import sync_units  # noqa: E402


class MaterialIndexIdempotenceTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(CLI_COURSE, ignore_errors=True)

    def make_course_at(self, course: Path) -> tuple[Path, Path]:
        shutil.rmtree(course, ignore_errors=True)
        (course / "academico").mkdir(parents=True)
        academic = {
            "version": 1,
            "identity": {"subject": "QA Material Index"},
            "units": [{"id": "unidad-1", "name": "Unidad 1", "topics": ["Algoritmos"]}],
            "assessments": [],
            "rules": [],
            "claims": [],
            "claim_candidates": [],
            "official_status": {},
        }
        (course / "academico" / "academic.json").write_text(
            json.dumps(academic, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (course / "fuentes").mkdir(parents=True)
        (course / "contexto.md").write_text("# QA\n", encoding="utf-8")
        sync_units(course)
        source = course / "unidades" / "unidad-1" / "fuentes" / "oficiales" / "material.txt"
        source.write_text("contenido estable\n", encoding="utf-8")
        return course, source

    def make_course(self, root: Path) -> tuple[Path, Path]:
        return self.make_course_at(root / "qa-material-index")

    def run_sync(self, course: Path) -> dict:
        cp = subprocess.run(
            [
                sys.executable,
                str(SYNC_MATERIALS),
                "--course",
                str(course),
                "--unit",
                "unidad-1",
                "--write",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="strict",
            check=True,
            timeout=20,
        )
        self.assertEqual(cp.stderr, "")
        return json.loads(cp.stdout)

    def run_cli(self, *args: str) -> dict:
        cp = subprocess.run(
            [sys.executable, str(STUDY), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="strict",
            check=True,
            timeout=20,
        )
        self.assertEqual(cp.stderr, "")
        return json.loads(cp.stdout)

    def test_repeated_unchanged_write_preserves_index_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            course, source = self.make_course(Path(td))
            first = self.run_sync(course)
            self.assertEqual(len(first["added"]), 1)

            index = course / "unidades" / "unidad-1" / ".study" / "materials-index.json"
            before = index.read_bytes()

            second = self.run_sync(course)
            self.assertEqual(second["added"], [])
            self.assertEqual(second["changed"], [])
            self.assertEqual(second["removed"], [])
            self.assertEqual(index.read_bytes(), before)

            stat = source.stat()
            os.utime(source, (stat.st_atime + 5, stat.st_mtime + 5))
            third = self.run_sync(course)
            self.assertEqual(third["added"], [])
            self.assertEqual(third["changed"], [])
            self.assertEqual(third["removed"], [])
            self.assertEqual(index.read_bytes(), before)

    def test_cli_and_direct_script_share_index_bytes_and_semantics(self):
        course, source = self.make_course_at(CLI_COURSE)
        first = self.run_sync(course)
        self.assertEqual(first["added"], ["unidades/unidad-1/fuentes/oficiales/material.txt"])

        index = course / "unidades" / "unidad-1" / ".study" / "materials-index.json"
        payload = json.loads(index.read_text(encoding="utf-8"))
        row = payload["files"]["unidades/unidad-1/fuentes/oficiales/material.txt"]
        self.assertEqual(row["kind"], "official")
        self.assertEqual(row["unit_id"], "unidad-1")
        before = index.read_bytes()

        cli_noop = self.run_cli(
            "materials",
            "scan",
            course.name,
            "--unit",
            "unidad-1",
            "--commit",
            "--json",
        )
        self.assertEqual(cli_noop["added"], [])
        self.assertEqual(cli_noop["changed"], [])
        self.assertEqual(cli_noop["removed"], [])
        self.assertEqual(index.read_bytes(), before)

        source.write_text("contenido cambiado\n", encoding="utf-8")
        cli_changed = self.run_cli(
            "materials",
            "scan",
            course.name,
            "--unit",
            "unidad-1",
            "--commit",
            "--json",
        )
        self.assertEqual(cli_changed["changed"], ["unidades/unidad-1/fuentes/oficiales/material.txt"])
        changed_bytes = index.read_bytes()
        self.assertNotEqual(changed_bytes, before)

        direct_noop = self.run_sync(course)
        self.assertEqual(direct_noop["changed"], [])
        self.assertEqual(index.read_bytes(), changed_bytes)

    def test_study_entrypoint_patches_all_material_callers_to_canonical_functions(self):
        import study
        from scripts import _study_cli_impl

        self.assertEqual(study.ROOT, ROOT)
        self.assertEqual(study.COURSES_DIR, ROOT / "materias")
        self.assertEqual(study.SCRIPTS_DIR, ROOT / "scripts")
        self.assertEqual(_study_cli_impl.ROOT, ROOT)
        self.assertEqual(_study_cli_impl.COURSES_DIR, ROOT / "materias")
        self.assertEqual(_study_cli_impl.SCRIPTS_DIR, ROOT / "scripts")
        self.assertIs(_study_cli_impl.scan_materials, study.scan_materials)
        self.assertIs(_study_cli_impl.materials_index_path, study.materials_index_path)
        self.assertIs(_study_cli_impl.material_kind, study.material_kind)
        self.assertIs(_study_cli_impl.cmd_materials_scan, study.cmd_materials_scan)


if __name__ == "__main__":
    unittest.main()
