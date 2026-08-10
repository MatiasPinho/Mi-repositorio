import copy
import json
import unittest
from pathlib import Path

from scripts.academic_eval import DEFAULT_CASES, DEFAULT_POLICY, evaluate_review, load_policy, run_benchmark

ROOT = Path(__file__).resolve().parents[1]


def good_review():
    return {
        "pass": True,
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
        "pedagogy_issues": [],
        "visual_issues": [],
    }


class AcademicEvalTests(unittest.TestCase):
    def test_policy_is_versioned_and_loadable(self):
        policy = load_policy(DEFAULT_POLICY)
        self.assertEqual(policy["version"], 1)
        self.assertEqual(policy["score_minimum"], 4)
        self.assertIn("academic_fidelity", policy["score_gates"])

    def test_good_review_passes(self):
        self.assertEqual(evaluate_review(good_review()), [])

    def test_policy_rejects_low_score(self):
        review = good_review()
        review["scores"]["clarity"] = 3
        self.assertIn("score-clarity-below-4", evaluate_review(review))

    def test_policy_rejects_unsupported_claim(self):
        review = good_review()
        review["claim_checks"][0]["verdict"] = "unsupported"
        self.assertIn("claim-check-0-not-supported", evaluate_review(review))

    def test_frozen_benchmark_matches_policy(self):
        result = run_benchmark(DEFAULT_CASES)
        self.assertTrue(result["ok"], json.dumps(result, ensure_ascii=False, indent=2))
        self.assertEqual(result["false_accepts"], 0)
        self.assertEqual(result["false_rejects"], 0)

    def test_regressive_policy_is_detected_by_frozen_benchmark(self):
        policy = copy.deepcopy(load_policy(DEFAULT_POLICY))
        policy["score_minimum"] = 6
        result = run_benchmark(DEFAULT_CASES, policy)
        self.assertFalse(result["ok"])
        self.assertGreater(result["false_rejects"], 0)


if __name__ == "__main__":
    unittest.main()
