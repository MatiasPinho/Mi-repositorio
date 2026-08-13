from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

sys.path.insert(0, str(ROOT))
from scripts.course_layout import sync_units  # noqa: E402
from scripts.engine_qa_rpc_policy import _qualifying_steps  # noqa: E402


def run(script: str, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        timeout=30,
    )
    if cp.returncode != expect:
        raise AssertionError(
            f"{script} returned {cp.returncode}, expected {expect}\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}"
        )
    return cp


class EngineQaV6FindingRegressions(unittest.TestCase):
    def make_course(self, td: str) -> Path:
        course = Path(td) / "course"
        (course / "academico").mkdir(parents=True)
        academic = {
            "version": 1,
            "identity": {"subject": "QA V6"},
            "units": [
                {"id": "unidad-1", "name": "Algoritmos y datos", "topics": ["Árboles"]},
                {"id": "unidad-2", "name": "Control", "topics": ["Bucles"]},
            ],
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
        return course

    def concepts(self, course: Path, unit: str = "unidad-1") -> dict:
        path = course / "unidades" / unit / "conocimiento" / "concepts.json"
        return json.loads(path.read_text(encoding="utf-8"))["concepts"]

    def progress(self, course: Path, unit: str = "unidad-1") -> dict:
        path = course / "unidades" / unit / "progreso" / "progress.json"
        return json.loads(path.read_text(encoding="utf-8"))["concepts"]

    def test_nfc_and_nfd_concept_names_share_one_stable_record(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            nfc = "Árbol β"
            nfd = unicodedata.normalize("NFD", nfc)
            self.assertNotEqual(nfc, nfd)

            run(
                "concept_graph.py", "upsert", "--course", str(course),
                "--concept", nfc, "--unit", "unidad-1",
            )
            run(
                "concept_graph.py", "upsert", "--course", str(course),
                "--concept", nfd, "--unit", "unidad-1",
            )

            concepts = self.concepts(course)
            self.assertEqual(len(concepts), 1, concepts)
            row = next(iter(concepts.values()))
            self.assertEqual(row["id"], "arbol")
            self.assertEqual(row["name"], nfc)
            self.assertEqual(unicodedata.normalize("NFC", row["name"]), row["name"])

            run("topic_catalog.py", "reconcile", "--course", str(course), "--unit", "unidad-1", "--write")
            validated = run("topic_catalog.py", "validate", "--course", str(course), "--unit", "unidad-1")
            self.assertTrue(json.loads(validated.stdout)["ok"])

    def test_equivalent_unit_aliases_are_byte_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            registry = course / "unidades" / "unidad-1" / "conocimiento" / "concepts.json"

            first = run(
                "concept_graph.py", "upsert", "--course", str(course),
                "--concept", "Árbol β", "--unit", "Algoritmos y datos",
            )
            first_row = json.loads(first.stdout)
            before = registry.read_bytes()

            second = run(
                "concept_graph.py", "upsert", "--course", str(course),
                "--concept", "Árbol β", "--unit", "unidad-1",
            )
            second_row = json.loads(second.stdout)
            after = registry.read_bytes()

            self.assertEqual(before, after)
            self.assertEqual(first_row, second_row)
            self.assertEqual(second_row["unit_id"], "unidad-1")
            self.assertEqual(second_row["unit"], "Algoritmos y datos")

    def test_tracker_sync_persists_canonical_concept_id_and_unicode_identity(self):
        with tempfile.TemporaryDirectory() as td:
            course = self.make_course(td)
            run(
                "concept_graph.py", "upsert", "--course", str(course),
                "--concept", "Bucle λ", "--unit", "unidad-2",
            )
            run(
                "concept_graph.py", "upsert", "--course", str(course),
                "--concept", "Árbol β", "--unit", "unidad-1",
            )
            synced = run("study_tracker.py", "sync", "--course", str(course))
            self.assertEqual(json.loads(synced.stdout)["tracked"], 2)

            u1 = self.progress(course, "unidad-1")
            u2 = self.progress(course, "unidad-2")
            self.assertEqual(next(iter(u1.values()))["id"], "arbol")
            self.assertEqual(next(iter(u2.values()))["id"], "bucle")

            nfd = unicodedata.normalize("NFD", "Árbol β")
            run(
                "study_tracker.py", "record", "--course", str(course),
                "--concept", nfd, "--rating", "4",
            )
            u1_after = self.progress(course, "unidad-1")
            self.assertEqual(len(u1_after), 1, u1_after)
            row = next(iter(u1_after.values()))
            self.assertEqual(row["id"], "arbol")
            self.assertEqual(row["name"], "Árbol β")
            self.assertEqual(row["attempts"], 1)

    def test_state_evidence_requires_declared_check_outcome(self):
        failed_check = [{"step": 1, "kind": "check", "ok": False}]
        passed_check = [{"step": 2, "kind": "check", "ok": True}]
        mutation_then_failed = [
            {"step": 1, "kind": "mutation", "op": "write"},
            {"step": 2, "kind": "check", "ok": False},
        ]
        mutation_only = [{"step": 3, "kind": "mutation", "op": "write"}]

        self.assertEqual(_qualifying_steps("state", failed_check), [])
        self.assertEqual(_qualifying_steps("state", passed_check), [2])
        self.assertEqual(_qualifying_steps("state", mutation_then_failed), [])
        self.assertEqual(
            _qualifying_steps("state", failed_check, expected_check_ok=False),
            [1],
        )
        self.assertEqual(_qualifying_steps("state", mutation_only), [3])


if __name__ == "__main__":
    unittest.main()
