from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from scripts.course_layout import LayoutError, load_registry, sync_units
from scripts.migrate_unit_layout import apply_plan, build_plan
from scripts.topic_catalog import (
    TopicCatalogError,
    load_catalog,
    reconcile_topics,
    validate_catalog,
)
from study_mcp import service

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def academic(units: int = 1) -> dict:
    return {
        "version": 2,
        "identity": {"subject": "Topics Test"},
        "units": [
            {
                "id": f"U{index}",
                "name": f"Unidad {index}",
                "topics": ["Expresiones" if index == 1 else "Estructuras"],
                "status": "confirmed",
            }
            for index in range(1, units + 1)
        ],
        "assessments": [],
        "rules": [],
    }


def concept(concept_id: str, unit_id: str, unit: str) -> dict:
    return {"id": concept_id, "name": concept_id.replace("-", " ").title(), "unit_id": unit_id, "unit": unit}


class TopicCatalogTests(unittest.TestCase):
    def make_course(self, root: Path, units: int = 1) -> Path:
        course = root / "course"
        write(course / "academico" / "academic.json", academic(units))
        (course / "fuentes").mkdir(parents=True)
        (course / "contexto.md").write_text("# Topics Test\n", encoding="utf-8")
        sync_units(course)
        return course

    def set_concepts(self, course: Path, unit_id: str, rows: dict[str, dict]) -> None:
        write(course / "unidades" / unit_id / "conocimiento" / "concepts.json", {"version": 2, "concepts": rows})

    def test_sync_creates_topics_json(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            path = course / "unidades/unidad-1/conocimiento/topics.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data, {
                "version": 1,
                "unit_id": "unidad-1",
                "topics": {},
                "unassigned_concept_ids": [],
            })

    def test_sync_upgrades_existing_v4_unit_without_losing_concepts(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            self.set_concepts(course, "unidad-1", {"suma": concept("suma", "unidad-1", "U1")})
            (course / "unidades/unidad-1/conocimiento/topics.json").unlink()
            sync_units(course)
            catalog = load_catalog(course, "U1")
            self.assertEqual(catalog["unassigned_concept_ids"], ["suma"])
            self.assertIn("suma", load_registry(course, "concepts", "U1")["concepts"])
            self.assertTrue(validate_catalog(course, "U1")["ok"])

    def test_topic_ids_are_stable_across_reprocessing(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            self.set_concepts(course, "unidad-1", {"suma": concept("suma", "unidad-1", "U1")})
            first = reconcile_topics(course, "U1", {
                "topics": [{
                    "id": "operadores",
                    "name": "Operadores",
                    "aliases": [],
                    "concept_ids": ["suma"],
                    "declared_matches": ["Expresiones"],
                    "evidence": [{"file": "clase-1.pdf", "page": 2}],
                }],
            }, write=True)
            second = reconcile_topics(course, "U1", {
                "topics": [{
                    "id": "expresiones-con-operadores",
                    "name": "Expresiones con operadores",
                    "aliases": ["Operadores"],
                    "concept_ids": ["suma"],
                }],
            }, write=True)
            self.assertEqual(first["created_topic_ids"], ["operadores"])
            self.assertEqual(second["reused_topic_ids"], ["operadores"])
            catalog = load_catalog(course, "U1")
            self.assertEqual(set(catalog["topics"]), {"operadores"})
            self.assertIn("Operadores", catalog["topics"]["operadores"]["aliases"])

    def test_missing_concept_references_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            self.set_concepts(course, "unidad-1", {"suma": concept("suma", "unidad-1", "U1")})
            with self.assertRaisesRegex(TopicCatalogError, "no existe"):
                reconcile_topics(course, "U1", {
                    "topics": [{"name": "Operadores", "concept_ids": ["fantasma"]}],
                })
            write(course / "unidades/unidad-1/conocimiento/topics.json", {
                "version": 1,
                "unit_id": "unidad-1",
                "topics": {
                    "roto": {
                        "id": "roto", "unit_id": "unidad-1", "name": "Roto", "aliases": [],
                        "concept_ids": ["fantasma"], "declared_matches": [], "evidence": [],
                    }
                },
                "unassigned_concept_ids": ["suma"],
            })
            validation = validate_catalog(course, "U1")
            self.assertFalse(validation["ok"])
            self.assertIn("concept-missing", {row["code"] for row in validation["issues"]})

    def test_unassigned_concepts_are_explicit_and_detectable(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            self.set_concepts(course, "unidad-1", {"suma": concept("suma", "unidad-1", "U1")})
            invalid = validate_catalog(course, "U1")
            self.assertFalse(invalid["ok"])
            self.assertEqual(invalid["missing_assignment_concept_ids"], ["suma"])
            reconciled = reconcile_topics(course, "U1", write=True)
            self.assertEqual(reconciled["catalog"]["unassigned_concept_ids"], ["suma"])
            valid = validate_catalog(course, "U1")
            self.assertTrue(valid["ok"], valid)
            self.assertEqual(valid["unassigned_concept_ids"], ["suma"])

    def test_declared_matches_reference_official_topics_without_mutating_them(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td))
            self.set_concepts(course, "unidad-1", {"suma": concept("suma", "unidad-1", "U1")})
            before = json.loads((course / "academico/academic.json").read_text(encoding="utf-8"))
            result = reconcile_topics(course, "U1", {
                "topics": [{
                    "name": "Operadores aritméticos",
                    "concept_ids": ["suma"],
                    "declared_matches": ["expresiones"],
                }],
            }, write=True)
            topic = next(iter(result["catalog"]["topics"].values()))
            self.assertEqual(topic["declared_matches"], ["Expresiones"])
            after = json.loads((course / "academico/academic.json").read_text(encoding="utf-8"))
            self.assertEqual(after, before)
            with self.assertRaisesRegex(TopicCatalogError, "no declarado"):
                reconcile_topics(course, "U1", {
                    "topics": [{"id": topic["id"], "name": topic["name"], "declared_matches": ["Inventado"]}],
                })

    def test_v4_units_keep_topic_catalogs_isolated(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(Path(td), units=2)
            self.set_concepts(course, "unidad-1", {"base-u1": concept("base-u1", "unidad-1", "U1")})
            self.set_concepts(course, "unidad-2", {"base-u2": concept("base-u2", "unidad-2", "U2")})
            reconcile_topics(course, "U1", {"topics": [{"id": "base", "name": "Base", "concept_ids": ["base-u1"]}]}, write=True)
            reconcile_topics(course, "U2", {"topics": [{"id": "base", "name": "Base", "concept_ids": ["base-u2"]}]}, write=True)
            self.assertEqual(load_registry(course, "topics", "U1")["topics"]["base"]["concept_ids"], ["base-u1"])
            self.assertEqual(load_registry(course, "topics", "U2")["topics"]["base"]["concept_ids"], ["base-u2"])
            with self.assertRaisesRegex(LayoutError, "por unidad"):
                load_registry(course, "topics")

    def test_study_get_unit_context_includes_observed_topics(self):
        slug = "zz-topics-mcp-" + uuid.uuid4().hex[:8]
        course = ROOT / "materias" / slug
        try:
            write(course / "academico" / "academic.json", academic())
            (course / "fuentes").mkdir(parents=True)
            (course / "contexto.md").write_text("# MCP topics\n", encoding="utf-8")
            sync_units(course)
            self.set_concepts(course, "unidad-1", {"suma": concept("suma", "unidad-1", "U1")})
            reconcile_topics(course, "U1", {
                "topics": [{"id": "operadores", "name": "Operadores", "concept_ids": ["suma"]}],
            }, write=True)
            write(course / "unidades/unidad-1/progreso/progress.json", {
                "version": 2,
                "concepts": {"suma": {"id": "suma", "name": "Suma", "mastery": 0.6, "attempts": 1}},
            })
            data = service.get_unit_context(slug, "Unidad 1")
            self.assertEqual(data["unit"]["declared_topics"], ["Expresiones"])
            self.assertIn("operadores", data["topics"]["topics"])
            self.assertEqual(data["paths"]["topics"], "unidades/unidad-1/conocimiento/topics.json")
            self.assertEqual(data["topic_progress"]["topics"]["operadores"]["concept_count"], 1)
            self.assertEqual(data["topic_progress"]["topics"]["operadores"]["tested_coverage"], 1.0)
            self.assertEqual(data["topic_progress"]["topics"]["operadores"]["average_mastery"], 0.6)
            self.assertNotIn("mastery", data["topics"]["topics"]["operadores"])
        finally:
            shutil.rmtree(course, ignore_errors=True)

    def test_v3_migration_preserves_existing_topics_and_assignments(self):
        with tempfile.TemporaryDirectory() as td:
            course = Path(td) / "course"
            write(course / "academico" / "academic.json", academic(units=2))
            (course / "fuentes").mkdir(parents=True)
            (course / "contexto.md").write_text("# Legacy topics\n", encoding="utf-8")
            write(course / "conocimiento" / "concepts.json", {
                "version": 2,
                "concepts": {
                    "suma": concept("suma", "unidad-1", "U1"),
                    "lista": concept("lista", "unidad-2", "U2"),
                    "tupla": concept("tupla", "unidad-2", "U2"),
                },
            })
            write(course / "conocimiento" / "topics.json", {
                "version": 1,
                "topics": {
                    "operadores": {
                        "id": "operadores",
                        "unit_id": "unidad-1",
                        "name": "Operadores",
                        "aliases": ["Aritmética"],
                        "concept_ids": ["suma"],
                        "declared_matches": ["Expresiones"],
                        "evidence": [{"file": "legacy.pdf", "page": 3}],
                    },
                    "colecciones": {
                        "id": "colecciones",
                        "unit_id": "unidad-2",
                        "name": "Colecciones",
                        "aliases": [],
                        "concept_ids": ["lista"],
                        "declared_matches": ["Estructuras"],
                        "evidence": [],
                    },
                },
                "unassigned_concept_ids": ["tupla"],
            })
            write(course / "conocimiento" / "figures.json", {"version": 2, "figures": {}})
            write(course / "progreso" / "progress.json", {"version": 2, "concepts": {}})

            result = apply_plan(course, build_plan(course))
            self.assertTrue(result["ok"])
            u1 = load_catalog(course, "U1")
            u2 = load_catalog(course, "U2")
            self.assertEqual(u1["topics"]["operadores"]["evidence"], [{"file": "legacy.pdf", "page": 3}])
            self.assertEqual(u1["topics"]["operadores"]["aliases"], ["Aritmética"])
            self.assertEqual(u2["topics"]["colecciones"]["concept_ids"], ["lista"])
            self.assertEqual(u2["unassigned_concept_ids"], ["tupla"])
            self.assertTrue((course / ".study/legacy-layout-v3/conocimiento/topics.json").is_file())
            self.assertTrue(validate_catalog(course, "U1")["ok"])
            self.assertTrue(validate_catalog(course, "U2")["ok"])


if __name__ == "__main__":
    unittest.main()
