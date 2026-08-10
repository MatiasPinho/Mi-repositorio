# Stressed Materials Protocol

The ingestion layer has a frozen adversarial benchmark for material and transcript edge cases.

## Goal

Normal unit tests prove expected behavior. This protocol deliberately feeds the system awkward inputs that commonly break local study workflows: Unicode paths, renames, duplicate bytes, empty files, metadata-only changes, Windows encodings, UTF-16 transcripts, malformed VTT and speaker tags.

The benchmark is deterministic and makes no LLM calls.

## Components

- `tests/fixtures/stressed_materials/cases.jsonl`: frozen adversarial corpus.
- `scripts/stressed_materials.py`: benchmark runner.
- `tests/test_stressed_materials.py`: regression tests.
- `.github/workflows/ci.yml`: runs the benchmark explicitly on Windows and Linux before the full release suite.

## Run it

```bash
python scripts/stressed_materials.py benchmark
```

Run one frozen case:

```bash
python scripts/stressed_materials.py case --id unicode-nested-filename
```

The command exits non-zero when a case crashes or its observable behavior differs from the frozen expectation.

## Frozen guarantees in V1

1. Unicode and emoji filenames survive material scanning unchanged.
2. SHA-256 detects content changes even when file size stays the same.
3. A rename is represented as one removal plus one addition rather than a fabricated content change.
4. Files with identical bytes but different paths remain distinct source records.
5. Empty material files are trackable while known system files remain ignored.
6. An mtime-only change does not invalidate material whose content is unchanged.
7. CP1252 Spanish transcripts decode without mojibake.
8. UTF-16 transcripts with BOM preserve text and timestamps.
9. VTT speaker tags and exam cues survive normalization.
10. Malformed VTT input fails soft: it produces zero parsed segments instead of crashing the benchmark.

## Adding a newly discovered failure

When a real course exposes a material-ingestion failure:

1. reduce it to the smallest synthetic reproduction;
2. add it to `cases.jsonl` without private course content;
3. confirm the new case fails on the buggy implementation;
4. fix the engine, not the expected result;
5. require both Windows and Ubuntu CI to pass.

Private course files must never be copied into this corpus.

## Scope

V1 stresses deterministic file/index and transcript boundaries. It does not yet judge semantic contradictions inside academic content or PDF extraction quality. Those require separate deterministic contracts or source-to-artifact evaluation cases rather than silently assigning that responsibility to an LLM.
