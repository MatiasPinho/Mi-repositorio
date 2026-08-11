from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from scripts.quiz_run import _accepted_json, _validate_review

CHECKS = (
    "canonical_fidelity",
    "single_best_answer",
    "distractor_quality",
    "no_answer_cues",
    "feedback_quality",
    "topic_coverage",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(path: Path, candidate: Path, *, passed: bool, issue: str = "") -> None:
    checks = {name: True for name in CHECKS}
    if not passed:
        checks["single_best_answer"] = False
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "candidate_sha256": digest(candidate),
                "pass": passed,
                "issues": [] if passed else [issue or "ambiguous-answer"],
                "checks": checks,
            }
        ),
        encoding="utf-8",
    )


class QuizReviewChainTests(unittest.TestCase):
    def test_first_pass_keeps_candidate_immutable_and_accepts_04_final(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            run = Path(td)
            candidate = run / "02-quiz.json"
            candidate.write_text('{"candidate":1}', encoding="utf-8")
            review(run / "03-review.json", candidate, passed=True)
            (run / "04-final.json").write_bytes(candidate.read_bytes())

            errors: list[str] = []
            _validate_review(run, errors)

            self.assertEqual(errors, [])
            self.assertEqual(_accepted_json(run), run / "04-final.json")

    def test_failed_first_review_preserves_evidence_and_allows_one_repair(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            run = Path(td)
            candidate = run / "02-quiz.json"
            candidate.write_text('{"candidate":1}', encoding="utf-8")
            original = candidate.read_bytes()
            review(run / "03-review.json", candidate, passed=False, issue="two-defensible-options")

            repair = run / "04-repair.json"
            repair.write_text('{"candidate":2}', encoding="utf-8")
            review(run / "05-review.json", repair, passed=True)
            (run / "06-final.json").write_bytes(repair.read_bytes())

            errors: list[str] = []
            _validate_review(run, errors)

            self.assertEqual(errors, [])
            self.assertEqual(candidate.read_bytes(), original)
            self.assertEqual(_accepted_json(run), run / "06-final.json")

    def test_third_review_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            run = Path(td)
            candidate = run / "02-quiz.json"
            candidate.write_text('{"candidate":1}', encoding="utf-8")
            review(run / "03-review.json", candidate, passed=False)
            repair = run / "04-repair.json"
            repair.write_text('{"candidate":2}', encoding="utf-8")
            review(run / "05-review.json", repair, passed=True)
            (run / "06-final.json").write_bytes(repair.read_bytes())
            (run / "07-review.json").write_text("{}", encoding="utf-8")

            errors: list[str] = []
            _validate_review(run, errors)

            self.assertIn("quiz-third-review-cycle-forbidden:07-review.json", errors)


if __name__ == "__main__":
    unittest.main()
