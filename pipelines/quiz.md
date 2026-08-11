# Pipeline: quiz

**Mode:** `QUIZ`

## READ
Load only these shared rules before semantic work:
- `rules/academic/source-truth.md`
- `rules/academic/uncertainty.md`
- `rules/pedagogy/learning-principles.md`
- `rules/evaluation/academic-fidelity.md`
- `rules/evaluation/multiple-choice.md`

## PURPOSE
Generate a persistent, self-contained multiple-choice quiz for one processed unit. The semantic source is JSON; the student opens the derived HTML directly in a browser and answers there. This action complements `preguntas`: it is not a conversational recall session and it never writes progress from browser-side JavaScript.

## RUN
1. Resolve course + scope to exactly one stable `unit_id`; quiz scope is unit-only. Load `study_get_unit_context(course, unit)` when MCP is available, otherwise the unit-scoped canonical concepts/topics directly. If canonical concepts are empty, stop with **NEEDS_INGESTION**. `procesar` may be orchestrated only as a separate prerequisite action, after which `quiz` restarts from step 1.
2. Resolve question count from the optional argument. Default to **15**. Honor explicit counts from 1 to 50; reject values outside that range instead of silently clamping.
3. Start a run with `python scripts/venv_exec.py scripts/quiz_run.py start --course <course-folder> --unit <unit-id>`. The quiz run reuses the shared engine/canonical snapshot machinery. Do not modify engine or canonical knowledge during the run.
4. **AUTHOR QUIZ JSON** → write `<run-dir>/02-quiz.json` with contract version 1:
   - root: `version`, `unit_id`, `title`, optional `subtitle`, `questions`;
   - every question: stable `id`, primary coverage `topic_id` (or `null` when the primary target is explicitly unassigned), one or more same-unit `concept_ids`, `difficulty` (`basic|intermediate|advanced`), `prompt`, optional `code`, four options and one `correct_option_id`;
   - `topic_id` must be represented by at least one target `concept_id`, but integrative questions may reference additional concepts from other observed topics in the same unit;
   - every option: `id` (`a|b|c|d`), `text`, concise `feedback`.
   Build questions only from canonical knowledge. Cross-unit prerequisites may help formulate/explain but must not become target concepts. Use observed topics as a flexible coverage guard, not a quota. Include unassigned concepts when pedagogically relevant.
5. Run deterministic validation:
   `python scripts/venv_exec.py scripts/quiz_artifact.py validate --course <course-folder> --unit <unit-id> --input <run-dir>/02-quiz.json`.
   Fix structural/canonical-reference errors before review.
6. **INDEPENDENT MCQ REVIEW 1** → review immutable `02-quiz.json` against the canonical unit and `rules/evaluation/multiple-choice.md`. Check canonical fidelity, one defensible best answer, distractor plausibility, absence of answer cues/trick wording, useful feedback and thematic coverage. Write `<run-dir>/03-review.json` with `candidate_sha256`, `pass`, `issues` and all six boolean checks:
   `canonical_fidelity`, `single_best_answer`, `distractor_quality`, `no_answer_cues`, `feedback_quality`, `topic_coverage`.
7. **ACCEPT OR REPAIR ONCE**:
   - if `03-review.json` passes, copy `02-quiz.json` byte-for-byte to `<run-dir>/04-final.json` and set `<accepted-json>` to that file;
   - if it fails, preserve both files unchanged, write one targeted `<run-dir>/04-repair.json`, run deterministic validation on the repair, review it independently into `<run-dir>/05-review.json`, and only if that second review passes copy it byte-for-byte to `<run-dir>/06-final.json`; set `<accepted-json>` to `06-final.json`;
   - no third academic review/repair cycle is allowed. Do not overwrite the rejected candidate or its review merely to obtain a passing history.
8. **RENDER** → `python scripts/venv_exec.py scripts/quiz_artifact.py render --course <course-folder> --unit <unit-id> --input <accepted-json> --html <run-dir>/09-rendered.html`.
   The renderer must produce one offline/self-contained HTML with both runtime modes:
   - **Práctica:** feedback after checking each answer.
   - **Examen:** no correctness feedback until final submission.
   Both modes show final score, per-topic results and question-by-question review. The HTML must not call network resources and must not write `progress.json`.
9. **INTEGRITY GATE** → `python scripts/venv_exec.py scripts/quiz_artifact.py check --course <course-folder> --unit <unit-id> --input <accepted-json> --html <run-dir>/09-rendered.html --write <run-dir>/10-integrity.json`. Require `ok: true`.
10. **REAL-BROWSER INTERACTION GATE** → `python scripts/venv_exec.py scripts/quiz_browser_check.py --json <accepted-json> --html <run-dir>/09-rendered.html --out <run-dir>/interaction-audit --write <run-dir>/10-interaction.json`. Require `ok: true`. This gate must actually click through both modes in Playwright Chromium: practice cannot reveal correctness before `Comprobar`, exam cannot reveal correctness before submission, and an all-correct exam must finish at 100% with per-topic and question review rendered. It must persist these non-empty evidence screenshots: `interaction-audit/practice-feedback.png`, `interaction-audit/exam-question-mobile.png` and `interaction-audit/exam-result-mobile.png`.
11. **BROWSER VISUAL GATE** → run `python scripts/venv_exec.py scripts/visual_audit.py <run-dir>/09-rendered.html --out <run-dir>/visual-audit`. Require exit code 0 and `visual-audit/audit.json -> ok: true`. Inspect `visual-audit/desktop.png` and `visual-audit/mobile.png` for the initial page, then personally inspect all three `interaction-audit/` screenshots for option wrapping, selected/correct/incorrect states, feedback legibility, code overflow, mobile navigation and final results/review layout. The interaction gate proves behavior; the screenshots + visual gate prove the actual states remain legible/responsive. Neither substitutes for the other.
12. **ATOMIC PUBLISH** → publish the exact validated JSON/HTML bytes:
    `python scripts/venv_exec.py scripts/publish_quiz.py --json <accepted-json> --html <run-dir>/09-rendered.html --dest-json <unit-root>/preguntas/_source/<unit-id>-quiz.json --dest-html <unit-root>/preguntas/<unit-id>-quiz.html --report <run-dir>/11-publication.json`.
    The run sources remain immutable. Re-running `quiz` replaces the unit's current quiz atomically rather than accumulating stale random banks.
13. Mark only the published HTML as artifact type `quiz`, scope `<unit-id>`, using MCP `study_mark_artifact` or `artifact_state.py mark`.
14. Finish with `python scripts/venv_exec.py scripts/quiz_run.py finish --run <run-dir>`. Finish rejects a changed canonical snapshot, an invalid review chain, failed integrity/interaction/visual gates, missing interaction screenshots, publication mismatch or engine mutation.
15. Return the final HTML path prominently. The JSON is the semantic source and may be linked secondarily.

## REVIEW JSON SHAPE
Both review files use:
```json
{
  "version": 1,
  "candidate_sha256": "<candidate hash>",
  "pass": true,
  "issues": [],
  "checks": {
    "canonical_fidelity": true,
    "single_best_answer": true,
    "distractor_quality": true,
    "no_answer_cues": true,
    "feedback_quality": true,
    "topic_coverage": true
  }
}
```
A failed first review keeps `pass: false`, non-empty `issues`, and boolean check results that describe the failure; it is evidence, not something to rewrite after repair.

## BROWSER/PROGRESS BOUNDARY
The quiz is a local study aid, not a secure proctoring environment. Correct answers necessarily exist inside the offline HTML so JavaScript can grade without a server. Browser answers are ephemeral and **must not update canonical mastery automatically** in V1. Progress integration belongs to a future explicit result-import contract, not hidden JavaScript/file-system behavior.

## Engine failure contract
If renderer, browser interaction, visual audit, publication or run validation fails, stop with **ENGINE FAILURE**. Do not patch engine files inside the active study run; fix the engine separately and rerun the quiz action.
