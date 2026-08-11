# Multiple-choice quality contract

Use this rule for persistent browser quizzes and any generated MCQ bank.

## Academic fidelity
- Every question, correct answer and explanatory feedback must be supported by the selected unit's canonical knowledge.
- Cross-unit prerequisites may clarify reasoning but must not be presented as target content of the selected unit.
- If canonical sources are uncertain or conflicting, preserve that uncertainty; do not turn it into a falsely absolute option.
- Do not use external knowledge unless the request explicitly asks for it and it is clearly labeled outside the canonical quiz.

## One best answer
- Exactly four options (`a`, `b`, `c`, `d`) and exactly one defensible best answer.
- Reject questions where two options become correct under a reasonable interpretation.
- Avoid hidden assumptions. Put every condition needed to answer in the prompt/code.
- Avoid trick negatives (`EXCEPT`, double negatives) unless the negative distinction itself is academically important; make such wording visually explicit.
- Do not use `all of the above` / `none of the above`.

## Distractors
- Distractors should be plausible misconceptions, neighboring concepts, common operator/order mistakes, incorrect initializations, lost conditions or other canonically meaningful confusions.
- A distractor must be clearly wrong for a specific reason. Do not invent nonsense just to fill four slots.
- Keep options reasonably parallel in grammar, specificity and length so the correct answer is not visually cued.
- Do not systematically place the correct answer in the same letter position.

## Feedback
- Every option carries concise feedback.
- Correct-option feedback explains the governing concept, not merely “correct”.
- Wrong-option feedback identifies why that option fails without introducing unsupported content.
- Feedback appears only after checking in practice mode or after final submission in exam mode.

## Coverage and difficulty
- Use observed topics as a coverage guard, never as fixed quotas or inferred assessment weights.
- Prefer concept/application questions over trivia.
- Mix `basic`, `intermediate` and `advanced` where the canonical material supports it; difficulty labels describe reasoning demand, not arbitrary wording complexity.
- Explicitly unassigned concepts remain eligible and must not disappear from the coverage audit.

## Programming material
- A question may include an optional `code` block.
- Code must preserve exact syntax/operators/initial values from the intended scenario.
- If the answer depends on execution order, types, precedence or a boundary condition, independently recompute the result before accepting the question.
