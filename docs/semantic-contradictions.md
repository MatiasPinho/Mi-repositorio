# Semantic Contradiction Protocol

The study engine keeps contradictory evidence explicit instead of flattening every source into one undifferentiated truth.

## Two canonical views

For each structured claim key, the resolver computes two independent views:

- `academic_truth`: the value best supported as academic knowledge.
- `assessment_expectation`: the value best supported as what the course/teacher expects for evaluation.

This distinction is intentional. A professor can say something that conflicts with stronger academic material, and the system must be able to preserve both facts:

```text
academic_truth         = A
assessment_expectation = B
status                 = split-view
```

A split view is not silently collapsed.

## Claims are structured evidence

The protocol does not compare arbitrary prose. Claims must already be reduced to a deterministic key:

```json
{
  "id": "teacher-cache-1",
  "domain": "academic",
  "subject": "cache",
  "predicate": "is-volatile",
  "object": "",
  "value": false,
  "source_type": "teacher_explicit",
  "source": "aclaracion-docente.md"
}
```

Claims live under `academico/academic.json -> claims`.

## Source types

V1 distinguishes:

- `official_regulation`
- `authoritative_textbook`
- `official_course_notice`
- `official_course_material`
- `teacher_explicit`
- `teacher_transcript`
- `student_note`
- `other`

The source ranks are versioned in `config/semantic_claim_policy.json` and differ between `academic_truth` and `assessment_expectation`.

## Critical transcript rule

`teacher_transcript` is evidence, not absolute authority.

A raw transcript cannot use `supersedes` to replace a prior claim. This avoids treating ASR mistakes, ambiguous phrasing or an off-hand classroom statement as a definitive update.

If a teacher statement is explicitly confirmed and should have stronger course authority, it must be represented as `teacher_explicit` with a concrete source reference.

## Supersession

Recency by itself does not erase old evidence.

A newer claim can supersede an older claim only when:

1. it explicitly lists the old claim id in `supersedes`;
2. its source type is allowed to supersede claims in that domain.

For example, an official May announcement can supersede the March exam scope. A raw transcript cannot.

## Resolution states

Each semantic key ends in one of three states:

- `resolved`: both canonical views resolve to the same value.
- `split-view`: academic truth and assessment expectation resolve, but to different values.
- `unresolved`: at least one view lacks enough authority separation to choose safely.

An unresolved conflict must never be silently turned into a categorical statement.

## Academic review gate

Academic evaluation policy V2 includes `contradiction_issues` among the issue fields that must be empty.

If a generated artifact relies on an unresolved contradiction as though it were settled, the reviewer must record that conflict in `contradiction_issues`, which makes the deterministic review gate fail.

## Commands

Run the frozen benchmark:

```bash
python scripts/semantic_claims.py benchmark
```

Resolve a standalone claims JSON:

```bash
python scripts/semantic_claims.py resolve --claims claims.json
```

Resolve the claims recorded in a course:

```bash
python scripts/semantic_claims.py course --course materias/programacion-i
```

Persist the derived diagnostic under `.study/semantic-claims.json`:

```bash
python scripts/semantic_claims.py course --course materias/programacion-i --write
```

## Example: professor says something academically wrong

Evidence:

```text
authoritative textbook → cache is volatile
explicit teacher note  → cache is not volatile
```

Possible V1 result:

```text
academic_truth         → true
assessment_expectation → false
status                 → split-view
```

The study material can therefore explain the academically supported answer while also warning that the course appears to expect a conflicting answer. Neither source disappears.

## Scope

V1 deliberately does not extract claims automatically from prose with an LLM. It only resolves claims after they have been structured. That keeps the resolution layer testable and prevents a language model from both inventing the claim and deciding whether its own invention is true.
