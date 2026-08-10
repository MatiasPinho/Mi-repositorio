# PDF Stress Protocol

The study engine includes a deterministic PDF health probe plus a frozen adversarial benchmark for common academic-document failure modes.

## Goal

PDFs are treated as files with measurable structural properties before any semantic interpretation happens. The probe answers questions such as:

- can the file be opened at all?
- is it password-protected?
- how many pages are readable?
- which pages have an extractable text layer?
- which pages are image-only and therefore likely scans?
- which pages are blank or rotated?
- do vector-heavy pages contain table/diagram-like drawing primitives?

The protocol does **not** perform OCR and does not decide academic relevance.

## Components

- `scripts/pdf_probe.py`: deterministic per-file and per-course PDF diagnostics.
- `scripts/pdf_stress.py`: runtime generator and frozen benchmark runner.
- `tests/fixtures/pdf_stress/cases.jsonl`: adversarial expectations.
- `tests/test_pdf_stress.py`: regression tests.
- `.github/workflows/ci.yml`: explicit PDF stress step on Windows and Ubuntu.

## Run it

```bash
python scripts/pdf_stress.py benchmark
```

Run one case:

```bash
python scripts/pdf_stress.py case --id image-only-scan
```

Probe a real PDF directly:

```bash
python scripts/pdf_probe.py probe path/to/material.pdf
```

Probe every official PDF in a course:

```bash
python scripts/pdf_probe.py scan --course programacion-i
```

## Frozen guarantees in V1

1. A normal text PDF exposes an extractable text layer.
2. An image-only PDF is flagged as likely scanned without pretending OCR occurred.
3. Page rotation is preserved in diagnostics.
4. Vector/table-like pages expose drawing primitives and text.
5. Blank pages are distinguishable from failed extraction.
6. Corrupt PDFs are reported as unreadable instead of crashing the benchmark.
7. Password-protected PDFs are reported explicitly as encrypted.
8. Unicode and emoji PDF filenames survive diagnostics unchanged.
9. Mixed multi-page documents retain per-page text/blank/rotation state.
10. A batch scan continues when one PDF is corrupt and still reports healthy files.

## Interpretation

`likely_scanned` means a page contains raster images but no extractable text layer. It is a mechanical signal only. A scanned page may still be perfectly readable to a human, but downstream automation must not assume searchable text exists.

A blank page is different: it has no extractable text, raster images, or vector drawings.

## Adding a real regression

When a private course PDF exposes a new failure mode:

1. reproduce the structural condition with a synthetic PDF generated at test time;
2. add a frozen case without copying course content;
3. confirm the new case fails before the fix;
4. fix the deterministic boundary or explicitly document the unsupported condition;
5. require Windows and Ubuntu CI to pass.

## Scope

V1 diagnoses PDF structure and extraction readiness. It does not evaluate whether extracted text is semantically complete, whether a table was reconstructed correctly, or whether two academic sources contradict each other. Those belong to later source-to-artifact and semantic-contradiction protocols.
