from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC_MATERIALS = ROOT / "scripts" / "sync_materials.py"

sys.path.insert(0, str(ROOT))
from scripts.course_layout import sync_units  # noqa: E402


class MaterialIndexIdempotenceTests(unittest.TestCase):
    def make_course(self, root: Path) -> tuple[Path, Path]:
        course = root / "qa-material-index"
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


if __name__ == "__main__":
    unittest.main()
