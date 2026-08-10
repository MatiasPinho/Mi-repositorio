# Automatic Claim Candidate Extraction

The study engine can pre-register high-signal academic claim candidates from transcripts and official PDFs before semantic ingestion.

## Boundary

This layer is an evidence extractor, not a truth engine.

It writes to:

```text
academico/academic.json -> claim_candidates
```

It never writes directly to:

```text
academico/academic.json -> claims
```

A candidate remains `pending` until the semantic phase of `procesar` reviews the original context and marks it `accepted` or `rejected`. Accepted candidates may then be represented as canonical structured claims.

## Why this boundary exists

Mechanical text patterns are useful for finding material that deserves attention, but they cannot safely decide whether:

- a professor misspoke;
- a transcript is wrong;
- a PDF is outdated;
- `esto` refers to the previous unit or something else;
- a later statement truly supersedes an earlier rule.

Therefore `semantic_ready: true` means only that the extractor could propose a complete structured key/value. It does not mean the proposition is true.

## V1 candidate types

### Assessment scope

Example:

```text
Unidad 4 no entra en el primer parcial.
```

Produces hints equivalent to:

```json
{
  "domain": "assessment",
  "subject": "primer-parcial",
  "predicate": "includes",
  "object": "Unidad 4",
  "value": false
}
```

A pronominal statement such as `Esto entra en el parcial` is still surfaced, but remains `semantic_ready: false` because its referent must be resolved from context.

### Grading rules

Explicit forms such as `se aprueba con 6`, `se promociona con 8` and `se regulariza con 6` are registered as candidates with numeric value hints.

### Definitions

Explicit definitional forms such as `Una pila se define como una estructura LIFO` are surfaced with academic-domain hints.

This does not attempt to infer every definition from arbitrary prose.

### Change signals

Wording such as `finalmente`, `a partir de ahora`, `queda sin efecto` or `se modifica` is surfaced as a `change-signal` candidate.

A change signal is never semantically ready and never creates `supersedes` automatically. The semantic review must identify exactly what changed and whether the source is authorized to supersede the older claim.

## Evidence

Each candidate receives a stable deterministic ID and preserves:

- source path;
- suggested source type;
- exact excerpt;
- transcript segment and timestamp when available;
- PDF page when available;
- `evidence_ref` suitable for canonical provenance.

Examples:

```text
transcripciones/clase-08.srt#00:47:21
oficiales/programa.pdf#page=3
```

## Source treatment

Transcript candidates are suggested as `teacher_transcript`.

Official PDFs are suggested as `official_course_material`.

These are suggestions only. Semantic ingestion may correct a source classification when the actual document is a regulation, formal notice or another stronger source class.

A raw transcript must never be upgraded to `teacher_explicit` simply because the sentence sounds definitive.

## Idempotency

Candidate IDs are derived from source, locator, candidate type, excerpt and structured hints. Re-running extraction over unchanged material therefore produces the same IDs.

When `--write` is used:

- prior `accepted`/`rejected` review status is preserved for an unchanged candidate;
- refreshed sources replace their previous automatic candidates;
- automatic candidates from deleted sources are removed during a full scan;
- manually created candidate records are preserved.

## Commands

Run the frozen extraction benchmark:

```bash
python scripts/claim_candidates.py benchmark
```

Scan a course without writing:

```bash
python scripts/claim_candidates.py scan --course programacion-1
```

Register candidates for semantic review:

```bash
python scripts/claim_candidates.py scan --course programacion-1 --write
```

Restrict extraction to one source:

```bash
python scripts/claim_candidates.py scan --course programacion-1 --file transcripciones/clase-08.srt --write
```

## `procesar` flow

```text
changed sources
      ↓
deterministic candidate extraction
      ↓
claim_candidates (pending + evidence)
      ↓
semantic review of original context
    ↙       ↘
reject     accept
             ↓
        canonical claims
             ↓
 semantic contradiction resolver
             ↓
resolved / split-view / unresolved
```

This means automatic extraction reduces missed evidence and repetitive searching without giving a regex, a transcript or a PDF direct authority over canonical truth.
