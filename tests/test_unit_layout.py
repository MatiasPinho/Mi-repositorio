from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from artifact_state import mark_artifact  # noqa: E402
from course_layout import (  # noqa: E402
    LayoutError,
    UNIT_DIRECTORIES,
    load_registry,
    resolve_source,
    save_registry,
    sync_units,
)
from study_mcp import service  # noqa: E402


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def academic(units: int = 2) -> dict:
    return {
        "version": 2,
        "identity": {"subject": "Layout Test"},
        "units": [
            {"id": f"U{i}", "name": f"Unidad {i}", "topics": [f"Tema {i}"], "status": "planned"}
            for i in range(1, units + 1)
        ],
        "assessments": [],
        "rules": [],
    }


class UnitLayoutTests(unittest.TestCase):
    def make_temp_course(self, td: str, units: int = 2) -> Path:
        course = Path(td) / "course"
        write(course / "academico" / "academic.json", academic(units))
        (course / "fuentes").mkdir(parents=True)
        return course

    def test_sync_materializes_every_unit_contract(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_temp_course(td)
            result = sync_units(course)
            self.assertEqual(result["created"], ["unidad-1", "unidad-2"])
            for unit_id in result["units"]:
                root = course / "unidades" / unit_id
                self.assertTrue((root / "unidad.json").is_file())
                for dirname in UNIT_DIRECTORIES:
                    self.assertTrue((root / dirname).is_dir(), f"missing {unit_id}/{dirname}")
            self.assertEqual(json.loads((course / ".study" / "layout.json").read_text())["version"], 4)

    def test_sync_refuses_to_hide_unmigrated_v3_content(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_temp_course(td, 1)
            write(course / "conocimiento" / "concepts.json", {
                "version": 2,
                "concepts": {"uno": {"name": "Uno", "unit": "U1", "unit_id": "unidad-1"}},
            })
            with self.assertRaisesRegex(LayoutError, "units migrate"):
                sync_units(course)
            self.assertFalse((course / ".study/layout.json").exists())

    def test_merged_reads_and_partitioned_writes_preserve_ownership(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_temp_course(td)
            sync_units(course)
            concepts = {
                "version": 2,
                "concepts": {
                    "uno": {"id": "uno", "name": "Uno", "unit": "U1", "unit_id": "unidad-1"},
                    "dos": {"id": "dos", "name": "Dos", "unit": "U2", "unit_id": "unidad-2"},
                },
            }
            save_registry(course, "concepts", concepts)
            self.assertEqual(set(load_registry(course, "concepts", "U1")["concepts"]), {"uno"})
            self.assertEqual(set(load_registry(course, "concepts", "U2")["concepts"]), {"dos"})
            self.assertEqual(set(load_registry(course, "concepts")["concepts"]), {"uno", "dos"})

            save_registry(course, "progress", {
                "version": 2,
                "concepts": {
                    "uno": {"name": "Uno", "unit": "U1", "mastery": 0.2},
                    "dos": {"name": "Dos", "unit": "U2", "mastery": 0.8},
                },
            })
            self.assertEqual(set(load_registry(course, "progress", "unidad-1")["concepts"]), {"uno"})
            self.assertEqual(set(load_registry(course, "progress", "unidad-2")["concepts"]), {"dos"})

    def test_source_resolution_prefers_the_selected_unit(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_temp_course(td)
            sync_units(course)
            u1 = course / "unidades" / "unidad-1" / "fuentes" / "oficiales" / "tema.pdf"
            u2 = course / "unidades" / "unidad-2" / "fuentes" / "oficiales" / "tema.pdf"
            u1.write_bytes(b"u1")
            u2.write_bytes(b"u2")
            self.assertEqual(resolve_source(course, "oficiales/tema.pdf", "U1").read_bytes(), b"u1")
            self.assertEqual(resolve_source(course, "oficiales/tema.pdf", "U2").read_bytes(), b"u2")

    def test_artifact_write_cannot_escape_its_unit(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_temp_course(td, 1)
            sync_units(course)
            root_artifact = course / "resumenes" / "unidad-1-resumen.html"
            root_artifact.parent.mkdir()
            root_artifact.write_text("legacy", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unidades/unidad-1"):
                mark_artifact(course, "resumenes/unidad-1-resumen.html", "summary", "U1")

            unit_artifact = course / "unidades" / "unidad-1" / "resumenes" / "unidad-1-resumen.html"
            unit_artifact.write_text("canonical", encoding="utf-8")
            result = mark_artifact(
                course,
                "unidades/unidad-1/resumenes/unidad-1-resumen.html",
                "summary",
                "U1",
            )
            self.assertFalse(result["stale"])

    def test_v3_migration_partitions_and_keeps_recovery_copy(self):
        slug = "zz-layout-" + uuid.uuid4().hex[:8]
        course = ROOT / "materias" / slug
        try:
            write(course / "academico" / "academic.json", academic())
            (course / "contexto.md").write_text("# Contexto\n", encoding="utf-8")
            u1_source = course / "fuentes" / "oficiales" / "u1.pdf"
            u2_source = course / "fuentes" / "oficiales" / "u2.pdf"
            shared = course / "fuentes" / "oficiales" / "programa.pdf"
            u1_source.parent.mkdir(parents=True)
            u1_source.write_bytes(b"u1")
            u2_source.write_bytes(b"u2")
            shared.write_bytes(b"shared")
            write(course / "conocimiento" / "concepts.json", {
                "version": 2,
                "concepts": {
                    "uno": {"id": "uno", "name": "Uno", "unit": "U1", "unit_id": "unidad-1", "sources": [{"file": "oficiales/u1.pdf"}]},
                    "dos": {"id": "dos", "name": "Dos", "unit": "U2", "unit_id": "unidad-2", "sources": [{"file": "oficiales/u2.pdf"}]},
                },
            })
            write(course / "conocimiento" / "figures.json", {"version": 2, "figures": {}})
            write(course / "progreso" / "progress.json", {
                "version": 2,
                "concepts": {"uno": {"name": "Uno", "unit": "U1"}, "dos": {"name": "Dos", "unit": "U2"}},
            })
            artifact = course / "resumenes" / "unidad-1-resumen.html"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("<html></html>", encoding="utf-8")
            write(course / ".study" / "artifacts.json", {
                "version": 1,
                "artifacts": {"resumenes/unidad-1-resumen.html": {"type": "summary", "scope": "U1"}},
            })
            write(course / ".study" / "materials-index.json", {
                "files": {"oficiales/u1.pdf": {"sha256": "x"}, "oficiales/programa.pdf": {"sha256": "y"}},
            })
            run = course / ".study" / "runs" / "run-u2"
            write(run / "manifest.json", {"scope": "U2", "pipeline": "resumen"})
            write(run / "01-input.json", {"source": "oficiales/u2.pdf"})

            cp = subprocess.run(
                [sys.executable, str(SCRIPTS / "migrate_unit_layout.py"), "--course", slug, "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            result = json.loads(cp.stdout)
            self.assertTrue(result["ok"])
            self.assertTrue((course / "unidades/unidad-1/fuentes/oficiales/u1.pdf").is_file())
            self.assertTrue((course / "unidades/unidad-2/fuentes/oficiales/u2.pdf").is_file())
            self.assertTrue((course / "fuentes/oficiales/programa.pdf").is_file())
            self.assertTrue((course / ".study/legacy-layout-v3/fuentes/oficiales/u1.pdf").is_file())
            self.assertTrue((course / ".study/legacy-layout-v3/conocimiento/concepts.json").is_file())
            self.assertTrue((course / "unidades/unidad-1/resumenes/unidad-1-resumen.html").is_file())
            self.assertTrue((course / "unidades/unidad-2/.study/runs/run-u2/manifest.json").is_file())
            self.assertFalse((course / ".study/runs/run-u2").exists())
            index = json.loads((course / ".study/materials-index.json").read_text(encoding="utf-8"))
            self.assertIn("unidades/unidad-1/fuentes/oficiales/u1.pdf", index["files"])
            self.assertIn("fuentes/oficiales/programa.pdf", index["files"])
            manifest = json.loads((course / ".study/artifacts.json").read_text(encoding="utf-8"))
            self.assertIn("unidades/unidad-1/resumenes/unidad-1-resumen.html", manifest["artifacts"])
            self.assertEqual(set(load_registry(course, "concepts", "U1")["concepts"]), {"uno"})
            self.assertEqual(set(load_registry(course, "concepts", "U2")["concepts"]), {"dos"})
            units = service.list_units(slug)
            self.assertEqual([row["unit_id"] for row in units["units"]], ["unidad-1", "unidad-2"])
            context = service.get_unit_context(slug, "Unidad 2")
            self.assertEqual(context["paths"]["root"], "unidades/unidad-2")
            self.assertEqual(set(context["concepts"]), {"dos"})
        finally:
            shutil.rmtree(course, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
