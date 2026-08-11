from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = json.loads((ROOT / "config" / "actions.json").read_text(encoding="utf-8"))


class V4ActionContractTests(unittest.TestCase):
    def pipeline(self, name: str) -> str:
        return (ROOT / "pipelines" / f"{name}.md").read_text(encoding="utf-8")

    def test_generated_action_metadata_matches_config_exactly(self):
        for name, spec in ACTIONS.items():
            claude = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            codex = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"description: {spec['description']}", claude, name)
            self.assertIn(f"description: {spec['description']}", codex, name)
            self.assertIn(f'argument-hint: "{spec["hint"]}"', claude, name)

    def test_public_hints_follow_v4_scope_contracts(self):
        expected = {
            "procesar": "[materia] [unidad opcional]",
            "aprender": "[materia] [tema]",
            "estudiar": "[materia] [minutos opcionales]",
            "resumen": "[materia] [unidad]",
            "guia": "[materia] [unidad]",
            "repaso": "[materia] [unidad]",
            "preguntas": "[materia] [unidad] [cantidad opcional]",
            "quiz": "[materia] [unidad] [cantidad opcional]",
            "simulacro": "[materia] [evaluacion] [unidad]",
            "explicar": "[materia] [concepto]",
            "auditar": "[materia] [unidad]",
            "estado": "[materia] [unidad opcional]",
        }
        self.assertEqual({name: spec["hint"] for name, spec in ACTIONS.items()}, expected)

    def test_router_is_v4_and_separates_declared_from_observed_topics(self):
        router = (ROOT / "core" / "ROUTER.md").read_text(encoding="utf-8")
        self.assertTrue(router.startswith("# University Study V4"))
        self.assertIn("academic.json -> units[].topics", router)
        self.assertIn("conocimiento/topics.json", router)
        self.assertIn("`quiz`", router)
        self.assertIn("Never fuzzy-pick", (ROOT / "actions" / "ARGUMENTS.md").read_text(encoding="utf-8"))

    def test_staged_artifacts_are_unit_scoped_topic_aware_and_ingest_safe(self):
        for name in ("resumen", "guia", "repaso"):
            text = self.pipeline(name)
            lower = text.lower()
            self.assertIn("unit-only", lower, name)
            self.assertIn("observed topics", lower, name)
            self.assertIn("NEEDS_INGESTION", text, name)
            self.assertIn("source_sha256", text, name)
            self.assertIn("published_sha256", text, name)
            self.assertIn("canonical", lower, name)
            self.assertIn("fingerprint", lower, name)

    def test_aprender_resolves_exact_observed_topic_and_never_fuzzy_picks(self):
        text = self.pipeline("aprender")
        self.assertIn("exactly one observed topic", text)
        self.assertIn("Never fuzzy-resolve", text)
        self.assertIn("concept_ids", text)
        self.assertIn("NEEDS_INGESTION", text)

    def test_explicar_resolves_exact_concept_and_never_fuzzy_picks(self):
        text = self.pipeline("explicar")
        self.assertIn("exactly one canonical concept", text)
        self.assertIn("Never fuzzy-resolve", text)
        self.assertIn("NEEDS_INGESTION", text)

    def test_estudiar_uses_topics_as_coverage_guard_not_quota(self):
        text = self.pipeline("estudiar")
        self.assertIn("observed-topic coverage", text)
        self.assertIn("coverage guard", text)
        self.assertIn("do not create fixed topic quotas", text)
        self.assertIn("NEEDS_INGESTION", text)

    def test_preguntas_is_strictly_unit_scoped_and_topic_aware(self):
        text = self.pipeline("preguntas")
        self.assertIn("exactly one stable `unit_id`", text)
        self.assertIn("does not accept a topic as a substitute", text)
        self.assertIn("observed topics", text)
        self.assertIn("NEEDS_INGESTION", text)

    def test_quiz_is_persistent_offline_unit_scoped_and_progress_safe(self):
        text = self.pipeline("quiz")
        self.assertIn("self-contained", text)
        self.assertIn("quiz scope is unit-only", text)
        self.assertIn("Default to **15**", text)
        self.assertIn("rules/evaluation/multiple-choice.md", text)
        self.assertIn("Práctica", text)
        self.assertIn("Examen", text)
        self.assertIn("quiz_artifact.py", text)
        self.assertIn("visual_audit.py", text)
        self.assertIn("publish_quiz.py", text)
        self.assertIn("must not update canonical mastery automatically", text)
        self.assertIn("NEEDS_INGESTION", text)

    def test_simulacro_requires_assessment_and_unit(self):
        text = self.pipeline("simulacro")
        self.assertIn("exactly one registered assessment record", text)
        self.assertIn("exactly one target stable `unit_id`", text)
        self.assertIn("Both are required inputs", text)
        self.assertIn("observed topics", text)

    def test_auditar_checks_topics_as_canonical_structure(self):
        text = self.pipeline("auditar")
        self.assertIn("conocimiento/topics.json", text)
        self.assertIn("declared_matches", text)
        self.assertIn("unassigned", text)
        self.assertIn("NEEDS_INGESTION", text)

    def test_procesar_remains_ingest_only_and_estado_remains_topic_aware(self):
        procesar = self.pipeline("procesar")
        estado = self.pipeline("estado")
        self.assertIn("**Forbidden:**", procesar)
        self.assertIn("topics reconcile", procesar)
        self.assertIn("topic mastery", estado.lower())
        self.assertIn("unassigned", estado.lower())


if __name__ == "__main__":
    unittest.main()
