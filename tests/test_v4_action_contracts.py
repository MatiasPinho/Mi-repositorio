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

    def test_public_surface_is_exactly_nine_actions(self):
        expected = {
            "procesar": "[materia] [unidad opcional]",
            "aprender": "[materia] [tema o concepto]",
            "estudiar": "[materia] [minutos opcionales]",
            "resumen": "[materia] [unidad] [detallado opcional]",
            "repaso": "[materia] [unidad]",
            "preguntas": "[materia] [unidad] [cantidad opcional]",
            "quiz": "[materia] [unidad] [cantidad opcional]",
            "simulacro": "[materia] [evaluacion] [unidad]",
            "estado": "[materia] [unidad opcional]",
        }
        self.assertEqual({name: spec["hint"] for name, spec in ACTIONS.items()}, expected)
        self.assertEqual(len(ACTIONS), 9)
        self.assertTrue({"guia", "explicar", "auditar"}.isdisjoint(ACTIONS))

    def test_root_readme_matches_public_surface(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("**nueve acciones**", readme)
        self.assertIn("docs/public-actions.md", readme)
        self.assertIn('/resumen Programacion-I "Unidad 1" detallado', readme)
        for name in ACTIONS:
            self.assertIn(f"`/{name}`", readme, name)
            self.assertIn(f"`${name}`", readme, name)
        for retired in ("guia", "explicar", "auditar"):
            self.assertNotIn(f"`/{retired}`", readme, retired)
            self.assertNotIn(f"`${retired}`", readme, retired)

    def test_removed_actions_have_no_public_adapters(self):
        for platform in (".claude", ".agents"):
            for name in ("guia", "explicar", "auditar"):
                self.assertFalse((ROOT / platform / "skills" / name / "SKILL.md").exists(), f"ghost public action {platform}/{name}")

    def test_router_is_v4_and_separates_declared_from_observed_topics(self):
        router = (ROOT / "core" / "ROUTER.md").read_text(encoding="utf-8")
        self.assertTrue(router.startswith("# University Study V4"))
        self.assertIn("academic.json -> units[].topics", router)
        self.assertIn("conocimiento/topics.json", router)
        self.assertIn("Exactly nine student-facing actions", router)
        self.assertIn("maintenance-only", router)
        self.assertIn("Never fuzzy-pick", (ROOT / "actions" / "ARGUMENTS.md").read_text(encoding="utf-8"))

    def test_staged_public_artifacts_are_unit_scoped_topic_aware_and_ingest_safe(self):
        for name in ("resumen", "repaso"):
            text = self.pipeline(name)
            lower = text.lower()
            self.assertIn("unit-only", lower, name)
            self.assertIn("observed topics", lower, name)
            self.assertIn("NEEDS_INGESTION", text, name)
            self.assertIn("source_sha256", text, name)
            self.assertIn("published_sha256", text, name)
            self.assertIn("canonical", lower, name)
            self.assertIn("fingerprint", lower, name)

    def test_resumen_absorbs_detailed_guide_mode(self):
        text = self.pipeline("resumen")
        self.assertIn("single public long-form study-document action", text)
        self.assertIn('depth: "standard"|"detailed"', text)
        self.assertIn("former “guía”", text)
        self.assertIn("published artifact remains", text)
        legacy = self.pipeline("guia")
        self.assertIn("no longer a public action", legacy)
        self.assertIn("pipelines/resumen.md", legacy)

    def test_aprender_resolves_exact_topic_or_concept_and_replaces_explicar(self):
        text = self.pipeline("aprender")
        self.assertIn("observed topic or concept", text)
        self.assertIn("tema:<target>", text)
        self.assertIn("concepto:<target>", text)
        self.assertIn("Never fuzzy-resolve", text)
        self.assertIn("canonical replacement for the former public `explicar` action", text)
        legacy = self.pipeline("explicar")
        self.assertIn("no longer a public action", legacy)
        self.assertIn("pipelines/aprender.md", legacy)

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

    def test_auditar_remains_internal_maintenance_pipeline(self):
        text = self.pipeline("auditar")
        self.assertIn("not a public study action", text)
        self.assertIn("maintenance/debugging only", text)
        self.assertIn("conocimiento/topics.json", text)

    def test_procesar_remains_ingest_only_and_estado_remains_topic_aware(self):
        procesar = self.pipeline("procesar")
        estado = self.pipeline("estado")
        self.assertIn("**Forbidden:**", procesar)
        self.assertIn("topics reconcile", procesar)
        self.assertIn("topic mastery", estado.lower())
        self.assertIn("unassigned", estado.lower())


if __name__ == "__main__":
    unittest.main()
