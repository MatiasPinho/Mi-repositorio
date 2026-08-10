# Academic Evaluation Protocol

The staged study pipelines use a deterministic acceptance policy before an artifact can finish.

## Components

- `config/academic_eval_policy.json`: versioned acceptance policy. This is the only place to change score thresholds, required fidelity checks, accepted claim verdicts, or blocking issue fields.
- `scripts/academic_eval.py`: deterministic evaluator and benchmark runner. It does not call an LLM.
- `tests/fixtures/academic_eval/cases.jsonl`: frozen benign/adversarial corpus used as a regression oracle.
- `tests/test_academic_eval.py`: policy and regression tests included in the release suite.

`pipeline_run.review_gate()` delegates to this policy, so runtime validation and CI evaluate the same contract.

## Why this exists

Rules that can be checked mechanically should not depend on an LLM judgment. The LLM reviewer produces structured evidence and scores; this layer decides whether that structure is admissible.

The protocol separates two concerns:

1. semantic review: the model inspects fidelity, pedagogy and presentation;
2. deterministic acceptance: code enforces the versioned contract.

## Run the frozen benchmark

```bash
python scripts/academic_eval.py benchmark
```

The command exits non-zero if a frozen case changes classification or an expected rejection reason disappears.

Evaluate one review payload:

```bash
python scripts/academic_eval.py evaluate --review path/to/05-review.json
```

## Changing the policy

A policy change must:

1. increment `version` when acceptance semantics change;
2. keep the frozen benchmark green unless the expected behavior is intentionally changed;
3. add a frozen case for every newly discovered failure mode;
4. update an existing frozen expectation only when the academic contract itself changed, not merely to make CI pass;
5. pass the complete release suite on Windows and Linux.

This gives policy evolution a regression surface: a stricter or looser rule cannot silently change accepted academic behavior.

## Next extension

The frozen corpus currently validates structured review decisions. A later layer can add end-to-end source-to-summary benchmark cases with measurable coverage and citation/fidelity assertions while keeping this deterministic gate unchanged.
