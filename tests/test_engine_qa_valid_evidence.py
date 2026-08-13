from __future__ import annotations

import unittest

from scripts.engine_qa_rpc_policy import _qualifying_steps


class EngineQaValidEvidenceTests(unittest.TestCase):
    def test_engine_mode_requires_expected_exec_result_not_just_invocation(self):
        rows = [
            {
                "step": 10,
                "kind": "rpc-exec",
                "engine_invoked": True,
                "ok": False,
                "returncode": 2,
            },
            {
                "step": 11,
                "kind": "rpc-exec-timeout",
                "engine_invoked": True,
            },
        ]
        self.assertEqual(_qualifying_steps("engine", rows), [])

        rows.append(
            {
                "step": 12,
                "kind": "rpc-exec",
                "engine_invoked": True,
                "ok": True,
                "returncode": 2,
                "expected_returncode": 2,
            }
        )
        self.assertEqual(_qualifying_steps("engine", rows), [12])

    def test_guard_and_state_modes_keep_their_explicit_evidence_contracts(self):
        rows = [
            {"step": 20, "kind": "rpc-exec-rejected", "engine_invoked": False},
            {"step": 21, "kind": "check", "ok": True},
        ]
        self.assertEqual(_qualifying_steps("guard", rows), [20])
        self.assertEqual(_qualifying_steps("state", rows), [21])


if __name__ == "__main__":
    unittest.main()
