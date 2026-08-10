import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from scripts.pipeline_run import review_gate

SCRIPT = ROOT / "scripts" / "pipeline_run.py"


def good_review(pass_value=True):
    return {
        "pass": pass_value,
        "scores": {
            "academic_fidelity": 5,
            "clarity": 5,
            "progression": 5,
            "explanation": 5,
            "examples": 4,
            "signal_to_noise": 5,
            "naturalness": 5,
            "coverage": 5,
            "visual_support": 5,
        },
        "fidelity_checks": {
            "definitions_taxonomies": {"status": "pass", "notes": "checked"},
            "conditions_boundaries": {"status": "pass", "notes": "checked"},
            "relations_order": {"status": "pass", "notes": "checked"},
            "certainty_conflicts": {"status": "pass", "notes": "checked"},
            "assessment_rules": {"status": "not_applicable", "notes": "no assessment claims"},
            "internal_consistency": {"status": "pass", "notes": "checked"},
            "example_separation": {"status": "pass", "notes": "checked"},
        },
        "claim_checks": [
            {"claim": "representative claim", "canonical_basis": "canonical concept", "verdict": "supported"}
        ],
        "academic_issues": [],
        "pedagogy_issues": [] if pass_value else ["needs repair"],
        "visual_issues": [],
        "contradiction_issues": [],
        "repair_instructions": [] if pass_value else ["repair it"],
    }


class PipelineRunTests(unittest.TestCase):
    def setUp(self):
        self.slug = "zz-pipeline-" + uuid.uuid4().hex[:8]
        self.course = ROOT / "materias" / self.slug
        (self.course / "academico").mkdir(parents=True)
        (self.course / "conocimiento").mkdir()
        (self.course / "academico" / "academic.json").write_text(json.dumps({"identity": {"subject": "Pipeline Test"}}), encoding="utf-8")
        (self.course / "conocimiento" / "concepts.json").write_text(json.dumps({"concepts": {}}), encoding="utf-8")
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps({"figures": {}}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.course, ignore_errors=True)

    def run_cmd(self, *args, check=True):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, text=True, capture_output=True, check=check)

    def start(self, executor="portable"):
        cp = self.run_cmd("start", "--course", self.slug, "--pipeline", "resumen", "--scope", "Unidad 1", "--executor", executor)
        data = json.loads(cp.stdout)
        return ROOT / data["run_dir"]

    def write_base_stages(self, run):
        (run / "02-plan.json").write_text(json.dumps({"central_idea": "x"}), encoding="utf-8")
        (run / "03-draft.md").write_text("draft", encoding="utf-8")
        (run / "04-humanized.md").write_text("human", encoding="utf-8")

    def write_visual_gate(self, run, *, ok=True):
        audit = run / "visual-audit"
        audit.mkdir(parents=True, exist_ok=True)
        (audit / "audit.json").write_text(
            json.dumps({"ok": ok, "engine": "chromium-set-content"}),
            encoding="utf-8",
        )
        (audit / "desktop.png").write_bytes(b"png")
        (audit / "mobile.png").write_bytes(b"png")

    def test_start_records_portable_inputs(self):
        run = self.start("codex")
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        inp = json.loads((run / "01-input.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["executor"], "codex")
        self.assertEqual(manifest["pipeline"], "resumen")
        self.assertEqual(inp["scope"], "Unidad 1")
        self.assertEqual(inp["unit_id"], "unidad-1")
        self.assertTrue(inp["academic_sha256"])
        self.assertTrue(inp["concepts_sha256"])
        self.assertTrue(inp["figures_sha256"])

    def test_first_review_pass_path_finishes(self):
        run = self.start()
        self.write_base_stages(run)
        (run / "05-review.json").write_text(json.dumps(good_review()), encoding="utf-8")
        (run / "06-final.md").write_text("final", encoding="utf-8")
        (run / "09-rendered.html").write_text("<html>ok</html>", encoding="utf-8")
        (run / "10-integrity.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        self.write_visual_gate(run)
        cp = self.run_cmd("validate", "--run", str(run))
        self.assertTrue(json.loads(cp.stdout)["ok"])
        self.run_cmd("finish", "--run", str(run))
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "finished")
        self.assertEqual(manifest["stages"]["visual-audit/audit.json"], "present")

    def test_failed_first_review_requires_repair_and_second_review(self):
        run = self.start("claude")
        self.write_base_stages(run)
        (run / "05-review.json").write_text(json.dumps(good_review(False)), encoding="utf-8")
        cp = self.run_cmd("validate", "--run", str(run), check=False)
        self.assertNotEqual(cp.returncode, 0)
        errors = json.loads(cp.stdout)["errors"]
        self.assertIn("missing-06-repair.md", errors)
        self.assertIn("missing-07-review.json", errors)
        self.assertIn("missing-08-final.md", errors)
        (run / "06-repair.md").write_text("repair", encoding="utf-8")
        (run / "07-review.json").write_text(json.dumps(good_review()), encoding="utf-8")
        (run / "08-final.md").write_text("fixed final", encoding="utf-8")
        (run / "09-rendered.html").write_text("<html>ok</html>", encoding="utf-8")
        (run / "10-integrity.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        self.write_visual_gate(run)
        cp = self.run_cmd("validate", "--run", str(run))
        self.assertTrue(json.loads(cp.stdout)["ok"])

    def test_low_score_fails_gate_even_if_pass_true(self):
        run = self.start()
        self.write_base_stages(run)
        review = good_review(True)
        review["scores"]["clarity"] = 3
        (run / "05-review.json").write_text(json.dumps(review), encoding="utf-8")
        (run / "06-final.md").write_text("not enough", encoding="utf-8")
        cp = self.run_cmd("validate", "--run", str(run), check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("missing-06-repair.md", json.loads(cp.stdout)["errors"])

    def test_missing_fidelity_checks_fail_gate(self):
        run = self.start()
        review = good_review(True)
        review.pop("fidelity_checks")
        path = run / "05-review.json"
        path.write_text(json.dumps(review), encoding="utf-8")
        self.assertIn("fidelity-checks-missing", review_gate(path))

    def test_unsupported_claim_fails_gate_even_if_pass_true(self):
        run = self.start()
        review = good_review(True)
        review["claim_checks"][0]["verdict"] = "unsupported"
        path = run / "05-review.json"
        path.write_text(json.dumps(review), encoding="utf-8")
        self.assertIn("claim-check-0-not-supported", review_gate(path))

    def test_internal_consistency_failure_fails_gate(self):
        run = self.start()
        review = good_review(True)
        review["fidelity_checks"]["internal_consistency"] = {"status": "fail", "notes": "taxonomy changed in conclusion"}
        path = run / "05-review.json"
        path.write_text(json.dumps(review), encoding="utf-8")
        self.assertIn("fidelity-internal_consistency-failed", review_gate(path))

    def test_recorded_pedagogy_issue_fails_even_if_pass_true(self):
        run = self.start()
        review = good_review(True)
        review["pedagogy_issues"] = ["taxonomy wording is misleading"]
        path = run / "05-review.json"
        path.write_text(json.dumps(review), encoding="utf-8")
        self.assertIn("pedagogy-issues-present", review_gate(path))

    def test_integrity_file_is_required_before_finish(self):
        run = self.start()
        self.write_base_stages(run)
        (run / "05-review.json").write_text(json.dumps(good_review()), encoding="utf-8")
        (run / "06-final.md").write_text("final", encoding="utf-8")
        (run / "09-rendered.html").write_text("<html>ok</html>", encoding="utf-8")
        self.write_visual_gate(run)
        cp = self.run_cmd("validate", "--run", str(run), check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("missing-10-integrity.json", json.loads(cp.stdout)["errors"])

    def test_visual_audit_is_required_before_finish(self):
        run = self.start()
        self.write_base_stages(run)
        (run / "05-review.json").write_text(json.dumps(good_review()), encoding="utf-8")
        (run / "06-final.md").write_text("final", encoding="utf-8")
        (run / "09-rendered.html").write_text("<html>ok</html>", encoding="utf-8")
        (run / "10-integrity.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        cp = self.run_cmd("validate", "--run", str(run), check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("missing-visual-audit.json", json.loads(cp.stdout)["errors"])

    def test_failed_visual_audit_blocks_finish(self):
        run = self.start()
        self.write_base_stages(run)
        (run / "05-review.json").write_text(json.dumps(good_review()), encoding="utf-8")
        (run / "06-final.md").write_text("final", encoding="utf-8")
        (run / "09-rendered.html").write_text("<html>ok</html>", encoding="utf-8")
        (run / "10-integrity.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        self.write_visual_gate(run, ok=False)
        cp = self.run_cmd("finish", "--run", str(run), check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("visual-audit-failed", json.loads(cp.stdout)["errors"])

    def test_persistent_ad_hoc_course_script_is_rejected(self):
        run = self.start()
        self.write_base_stages(run)
        (run / "05-review.json").write_text(json.dumps(good_review()), encoding="utf-8")
        (run / "06-final.md").write_text("final", encoding="utf-8")
        (run / "09-rendered.html").write_text("<html>ok</html>", encoding="utf-8")
        (run / "10-integrity.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        self.write_visual_gate(run)
        (self.course / "fix_unit_scope.py").write_text("print('repair')", encoding="utf-8")
        cp = self.run_cmd("validate", "--run", str(run), check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("unexpected-course-script:fix_unit_scope.py", json.loads(cp.stdout)["errors"])


if __name__ == "__main__":
    unittest.main()
