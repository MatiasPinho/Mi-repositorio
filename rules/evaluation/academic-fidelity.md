# Academic fidelity review

The reviewer is an adversarial verifier, not a second writer. Review the student artifact against the canonical academic state for the resolved scope. Pull original-source evidence only when the canonical state is missing, ambiguous or internally conflicted.

## Required claim audit

Before assigning scores, build a compact mental inventory of the candidate's **high-risk claims** and compare them with canonical knowledge. High-risk claims include:
- definitions and named concepts;
- taxonomies, counts and enumerations (for example, "four components" or "five steps");
- conditions, ranges, formulas, exceptions and boundaries;
- order, dependency, cause/effect and "X is/is not Y" relations;
- course/exam rules and assessment scope;
- statements carrying certainty such as confirmed, likely, unknown or excluded;
- examples that could be mistaken for an official rule;
- claims about what a figure or table proves.

Do not merely check that every canonical concept was mentioned. Check that the candidate says the **same thing** about it.

## Cross-document consistency pass

After canonical comparison, reread the candidate against itself. Repeated definitions, lists, counts, conditions and classifications must remain stable from introduction to conclusion. A formulation may become shorter, but it must not silently change the taxonomy.

Example of a failure that must be reported:
- body: "the analysis has four components: objective, inputs, output and test batch";
- conclusion: presents preconditions as a fifth peer component instead of a property/restriction attached to inputs.

This is a fidelity/pedagogy issue even if every individual term is otherwise correct.

## Certainty and examples

Preserve canonical epistemic status exactly:
- confirmed must not become merely possible;
- likely must not become confirmed;
- unknown must not be filled by inference;
- excluded must not be reintroduced.

Illustrative assumptions must remain visibly illustrative. Never let an invented example become an implicit course rule.

## Reject or repair if the artifact

- changes a definition, relation, formula, condition or code behavior;
- changes the number or membership of a named taxonomy/list;
- contradicts itself across sections or summary bullets;
- upgrades/downgrades confirmed/likely/unknown/excluded;
- invents exam scope or course rules;
- loses an important exception;
- silently resolves a material source conflict;
- introduces external knowledge as if it came from the course;
- states a high-risk claim that cannot be supported from canonical/source evidence.

## Review output discipline

`05-review.json` / `07-review.json` must contain the fidelity checks defined in `contracts/handoffs.md`. For every applicable category, record `pass` only after actively checking it. Use `not_applicable` only when the category genuinely does not occur in the artifact.

If a claim is unsupported, contradictory or needs qualification, add it to `academic_issues` and set `pass: false`. Do not award a high academic-fidelity score and hide a real problem in prose.
