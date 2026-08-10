from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.stressed_materials import DEFAULT_CASES, iter_cases, run_benchmark, run_case


class StressedMaterialsTests(unittest.TestCase):
    def test_frozen_stress_corpus_passes(self):
        result = run_benchmark()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["passed"], result["total"])
        self.assertGreaterEqual(result["total"], 10)

    def test_corpus_covers_scan_lifecycle_and_transcripts(self):
        cases = [case for _, case in iter_cases(DEFAULT_CASES)]
        kinds = {case["kind"] for case in cases}
        self.assertEqual(kinds, {"scan", "scan-lifecycle", "transcript"})
        ids = {case["id"] for case in cases}
        for required in {
            "unicode-nested-filename",
            "same-size-content-change",
            "rename-is-add-remove",
            "mtime-only-does-not-change-content",
            "cp1252-transcript-preserves-spanish",
            "utf16-transcript-preserves-timestamp",
            "malformed-vtt-does-not-crash",
        }:
            self.assertIn(required, ids)

    def test_wrong_frozen_expectation_is_detected(self):
        case = {
            "id": "regression-sentinel",
            "kind": "scan",
            "files": [{"path": "unidad.txt", "text": "contenido"}],
            "expected": {"added": [], "changed": [], "removed": [], "total": 0},
        }
        issues = run_case(case)
        self.assertTrue(issues)
        self.assertTrue(any(issue.startswith("added:") for issue in issues))
        self.assertTrue(any(issue.startswith("total:") for issue in issues))

    def test_benchmark_reports_case_exceptions_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cases.jsonl"
            path.write_text(
                json.dumps({"id": "bad-mutation", "kind": "scan-lifecycle", "files": [], "mutations": [{"op": "explode"}], "expected": {"added": [], "changed": [], "removed": [], "total": 0}}) + "\n",
                encoding="utf-8",
            )
            result = run_benchmark(path)
            self.assertFalse(result["ok"])
            self.assertEqual(result["failed"], 1)
            self.assertIn("exception:ValueError", result["results"][0]["issues"][0])


if __name__ == "__main__":
    unittest.main()
