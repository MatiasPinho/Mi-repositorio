import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = json.loads((ROOT / "config" / "actions.json").read_text(encoding="utf-8"))


class PortableActionTests(unittest.TestCase):
    def test_shared_core_structure_exists(self):
        required = [
            "core/ROUTER.md",
            "contracts/handoffs.md",
            "rules/academic/source-truth.md",
            "rules/academic/uncertainty.md",
            "rules/ingestion/material-processing.md",
            "rules/ingestion/transcripts.md",
            "rules/pedagogy/learning-principles.md",
            "rules/pedagogy/concept-ordering.md",
            "rules/visual/study-document.md",
            "rules/visual/figures.md",
            "rules/visual/active-reading.md",
            "rules/evaluation/visual-rubric.md",
            "rules/writing/student-prose.md",
            "rules/evaluation/academic-fidelity.md",
            "rules/evaluation/pedagogy-rubric.md",
            "rules/evaluation/quality-gates.md",
        ]
        for rel in required:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_all_actions_have_shared_pipelines(self):
        for name in ACTIONS:
            self.assertTrue((ROOT / "pipelines" / f"{name}.md").is_file(), name)

    def test_both_platforms_have_thin_adapters(self):
        for platform in (".claude", ".agents"):
            for name, spec in ACTIONS.items():
                p = ROOT / platform / "skills" / name / "SKILL.md"
                self.assertTrue(p.is_file(), f"missing {platform}/{name}")
                text = p.read_text(encoding="utf-8")
                self.assertIn(f"`{spec['mode']}`", text)
                self.assertIn(f"../../../pipelines/{name}.md", text)
                self.assertIn("../../../core/ROUTER.md", text)
                self.assertLess(len(text.splitlines()), 35, f"adapter too large: {platform}/{name}")

    def test_generated_adapter_bodies_match(self):
        for name in ACTIONS:
            c = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[-1].strip()
            a = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[-1].strip()
            self.assertEqual(c, a, name)

    def test_claude_actions_manual_codex_policy_manual(self):
        for name in ACTIONS:
            c = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("disable-model-invocation: true", c)
            self.assertIn("argument-hint:", c)
            policy = ROOT / ".agents" / "skills" / name / "agents" / "openai.yaml"
            self.assertTrue(policy.is_file())
            self.assertIn("allow_implicit_invocation: false", policy.read_text(encoding="utf-8"))

    def test_codex_frontmatter_stays_simple(self):
        allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
        for name in ACTIONS:
            text = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            front = text.split("---", 2)[1]
            keys = {m.group(1) for line in front.splitlines() if (m := re.match(r"^([A-Za-z0-9_-]+):", line))}
            self.assertTrue(keys <= allowed, (name, keys - allowed))

    def test_university_skill_is_adapter_not_duplicate_core(self):
        for platform in (".claude", ".agents"):
            p = ROOT / platform / "skills" / "university-study" / "SKILL.md"
            text = p.read_text(encoding="utf-8")
            self.assertIn("../../../core/ROUTER.md", text)
            self.assertLess(len(text.splitlines()), 20)
            self.assertFalse((p.parent / "references").exists())

    def test_humanizer_has_one_canonical_source_and_synced_copies(self):
        canonical = (ROOT / "vendor" / "humanizer" / "SKILL.md").read_bytes()
        self.assertIn(b'version: "2.9.1"', canonical)
        for platform in (".claude", ".agents"):
            self.assertEqual(canonical, (ROOT / platform / "skills" / "humanizer" / "SKILL.md").read_bytes())
            self.assertEqual(
                (ROOT / "vendor" / "humanizer" / "LICENSE").read_bytes(),
                (ROOT / platform / "skills" / "humanizer" / "LICENSE").read_bytes(),
            )

    def test_design_skills_and_frontend_design_are_synced_for_both_providers(self):
        for name, source in (
            ("frontend-design", ROOT / "vendor" / "frontend-design" / "SKILL.md"),
            ("study-design", ROOT / "skills-src" / "study-design" / "SKILL.md"),
            ("study-design-reviewer", ROOT / "skills-src" / "study-design-reviewer" / "SKILL.md"),
        ):
            canonical = source.read_bytes()
            for platform in (".claude", ".agents"):
                self.assertEqual(canonical, (ROOT / platform / "skills" / name / "SKILL.md").read_bytes(), f"{platform}/{name}")
        self.assertIn(b"Apache License", (ROOT / "vendor" / "frontend-design" / "LICENSE.txt").read_bytes())

    def test_summary_pipeline_does_not_load_design_time_skills(self):
        text = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        self.assertNotIn("frontend-design", text)
        self.assertNotIn("study-design-reviewer", text)
        self.assertNotIn("skills-src/study-design", text)

    def test_sync_script_verifies_no_drift(self):
        cp = subprocess.run([sys.executable, "scripts/sync_agent_assets.py", "verify"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_process_pipeline_is_ingest_only(self):
        text = (ROOT / "pipelines" / "procesar.md").read_text(encoding="utf-8")
        self.assertIn("Forbidden", text)
        self.assertIn("Do not generate summaries", (ROOT / "rules" / "ingestion" / "material-processing.md").read_text(encoding="utf-8"))
        self.assertNotIn("humanizer", text.lower())

    def test_summary_pipeline_has_distinct_stages(self):
        text = (ROOT / "pipelines" / "resumen.md").read_text(encoding="utf-8")
        for token in ("02-plan.json", "03-draft.md", "04-humanized.md", "05-review.json", "06-repair.md", "07-review.json", "08-final.md"):
            self.assertIn(token, text)
        self.assertIn("vendor/humanizer/SKILL.md", text)
        self.assertIn("independent critic", text)
        self.assertIn("09-rendered.html", text)
        self.assertIn("render_study.py", text)

    def test_core_is_provider_neutral(self):
        checked = list((ROOT / "rules").rglob("*.md")) + list((ROOT / "pipelines").rglob("*.md")) + [ROOT / "core" / "ROUTER.md"]
        for p in checked:
            text = p.read_text(encoding="utf-8").lower()
            # Provider names may be mentioned only in the portable router's explanation, never as required execution syntax.
            self.assertNotIn("context: fork", text, p)
            self.assertNotIn("/resumen", text, p)
            self.assertNotIn("$resumen", text, p)


if __name__ == "__main__":
    unittest.main()
