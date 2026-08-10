import json
import tempfile
import unittest
from pathlib import Path

from scripts.academic_eval import evaluate_review
from scripts.semantic_claims import load_policy, resolve_claims, run_benchmark, validate_claims

ROOT = Path(__file__).resolve().parents[1]


def good_review():
    return {
        "pass": True,
        "scores": {
            "academic_fidelity": 5,
            "clarity": 5,
            "progression": 5,
            "explanation": 5,
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
            "assessment_rules": {"status": "not_applicable", "notes": "none"},
            "internal_consistency": {"status": "pass", "notes": "checked"},
            "example_separation": {"status": "pass", "notes": "checked"},
        },
        "claim_checks": [
            {"claim": "representative claim", "canonical_basis": "canonical evidence", "verdict": "supported"}
        ],
        "academic_issues": [],
        "pedagogy_issues": [],
        "visual_issues": [],
        "contradiction_issues": [],
    }


class SemanticClaimTests(unittest.TestCase):
    def test_policy_is_versioned(self):
        policy = load_policy()
        self.assertEqual(policy["version"], 1)
        self.assertIn("academic_truth", policy["profiles"])
        self.assertIn("assessment_expectation", policy["profiles"])

    def test_frozen_semantic_benchmark_passes(self):
        result = run_benchmark()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["passed"], result["total"])

    def test_teacher_explicit_can_create_split_view_without_rewriting_truth(self):
        claims = [
            {
                "id": "book",
                "domain": "academic",
                "subject": "cache",
                "predicate": "is-volatile",
                "value": True,
                "source_type": "authoritative_textbook",
                "source": "book.pdf",
            },
            {
                "id": "teacher",
                "domain": "academic",
                "subject": "cache",
                "predicate": "is-volatile",
                "value": False,
                "source_type": "teacher_explicit",
                "source": "teacher-note.md",
            },
        ]
        result = resolve_claims(claims)
        group = result["groups"][0]
        self.assertEqual(group["status"], "split-view")
        self.assertIs(group["academic_truth"]["value"], True)
        self.assertIs(group["assessment_expectation"]["value"], False)

    def test_raw_transcript_cannot_supersede_assessment_notice(self):
        claims = [
            {
                "id": "notice",
                "domain": "assessment",
                "subject": "parcial",
                "predicate": "format",
                "value": "written",
                "source_type": "official_course_notice",
                "source": "campus.md",
            },
            {
                "id": "transcript",
                "domain": "assessment",
                "subject": "parcial",
                "predicate": "format",
                "value": "oral",
                "source_type": "teacher_transcript",
                "source": "class.srt",
                "supersedes": ["notice"],
            },
        ]
        issues = validate_claims(claims)
        self.assertIn("transcript-supersedes-not-authorized", issues)

    def test_equal_authority_conflict_remains_unresolved(self):
        claims = [
            {
                "id": "one",
                "domain": "academic",
                "subject": "stack",
                "predicate": "order",
                "value": "LIFO",
                "source_type": "official_course_material",
                "source": "a.pdf",
            },
            {
                "id": "two",
                "domain": "academic",
                "subject": "stack",
                "predicate": "order",
                "value": "FIFO",
                "source_type": "official_course_material",
                "source": "b.pdf",
            },
        ]
        result = resolve_claims(claims)
        self.assertFalse(result["ok"])
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(result["groups"][0]["status"], "unresolved")

    def test_review_gate_rejects_recorded_unresolved_contradiction(self):
        review = good_review()
        review["contradiction_issues"] = ["unresolved:stack/order"]
        issues = evaluate_review(review)
        self.assertIn("contradiction-issues-present", issues)


if __name__ == "__main__":
    unittest.main()
