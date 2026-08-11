#!/usr/bin/env python3
"""Validate and render offline multiple-choice study quizzes.

The semantic quiz lives in JSON. This module is deterministic: it validates the
quiz against unit-scoped canonical concepts/topics and renders one self-contained
HTML file with practice/exam modes. It never writes progress.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUIZ_VERSION = 1
OPTION_IDS = ("a", "b", "c", "d")
DIFFICULTIES = {"basic", "intermediate", "advanced"}
FORBIDDEN_OPTION_PHRASES = {
    "todas las anteriores",
    "ninguna de las anteriores",
    "all of the above",
    "none of the above",
}
SOURCE_META_RE = re.compile(
    r'<meta\s+name=["\']quiz-source-sha256["\']\s+content=["\']([0-9a-f]{64})["\']\s*/?>',
    re.IGNORECASE,
)
DATA_RE = re.compile(
    r'<script\s+id=["\']quiz-data["\']\s+type=["\']application/json["\']>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(value.split())


def _concept_index(data: Any) -> dict[str, dict[str, Any]]:
    rows = data.get("concepts", {}) if isinstance(data, dict) else {}
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, dict):
        return result
    for key, item in rows.items():
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or key).strip()
        if cid:
            result[cid] = item
    return result


def _topic_index(data: Any) -> tuple[dict[str, dict[str, Any]], set[str]]:
    rows = data.get("topics", {}) if isinstance(data, dict) else {}
    topics: dict[str, dict[str, Any]] = {}
    if isinstance(rows, dict):
        for key, item in rows.items():
            if not isinstance(item, dict):
                continue
            tid = str(item.get("id") or key).strip()
            if tid:
                topics[tid] = item
    raw_unassigned = data.get("unassigned_concept_ids", []) if isinstance(data, dict) else []
    unassigned = {str(value).strip() for value in raw_unassigned if str(value).strip()} if isinstance(raw_unassigned, list) else set()
    return topics, unassigned


def canonical_context(course: Path, unit: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], set[str]]:
    unit_root = course / "unidades" / unit
    concepts = _concept_index(read_json(unit_root / "conocimiento" / "concepts.json"))
    topics, unassigned = _topic_index(read_json(unit_root / "conocimiento" / "topics.json"))
    return concepts, topics, unassigned


def validate_quiz_document(
    data: Any,
    *,
    course: Path,
    unit: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["quiz-root-must-be-object"], "warnings": []}

    if int(data.get("version", 0) or 0) != QUIZ_VERSION:
        errors.append(f"quiz-version-must-be-{QUIZ_VERSION}")
    if str(data.get("unit_id", "")).strip() != unit:
        errors.append("quiz-unit-mismatch")
    if not str(data.get("title", "")).strip():
        errors.append("quiz-title-required")

    try:
        concepts, topics, unassigned = canonical_context(course, unit)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"canonical-context-unreadable:{type(exc).__name__}")
        return {"ok": False, "errors": errors, "warnings": warnings}

    if not concepts:
        errors.append("canonical-concepts-empty")

    questions = data.get("questions", [])
    if not isinstance(questions, list) or not questions:
        errors.append("quiz-questions-required")
        questions = []
    elif len(questions) > 50:
        errors.append("quiz-question-count-max-50")

    seen_ids: set[str] = set()
    seen_prompts: set[str] = set()
    topic_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()

    for index, question in enumerate(questions, start=1):
        prefix = f"q{index}"
        if not isinstance(question, dict):
            errors.append(f"{prefix}:must-be-object")
            continue

        qid = str(question.get("id", "")).strip()
        if not qid:
            errors.append(f"{prefix}:id-required")
        elif qid in seen_ids:
            errors.append(f"{prefix}:duplicate-id:{qid}")
        else:
            seen_ids.add(qid)

        prompt = str(question.get("prompt", "")).strip()
        if not prompt:
            errors.append(f"{prefix}:prompt-required")
        else:
            nprompt = normalize(prompt)
            if nprompt in seen_prompts:
                errors.append(f"{prefix}:duplicate-prompt")
            seen_prompts.add(nprompt)

        code = question.get("code")
        if code is not None and not isinstance(code, str):
            errors.append(f"{prefix}:code-must-be-string")

        difficulty = str(question.get("difficulty", "")).strip()
        if difficulty not in DIFFICULTIES:
            errors.append(f"{prefix}:difficulty-invalid")
        else:
            difficulty_counts[difficulty] += 1

        raw_concepts = question.get("concept_ids", [])
        if not isinstance(raw_concepts, list) or not raw_concepts:
            errors.append(f"{prefix}:concept-ids-required")
            concept_ids: list[str] = []
        else:
            concept_ids = [str(value).strip() for value in raw_concepts if str(value).strip()]
            if len(concept_ids) != len(raw_concepts):
                errors.append(f"{prefix}:concept-id-empty")
            if len(set(concept_ids)) != len(concept_ids):
                errors.append(f"{prefix}:duplicate-concept-id")
            for cid in concept_ids:
                if cid not in concepts:
                    errors.append(f"{prefix}:unknown-concept:{cid}")

        topic_id_raw = question.get("topic_id")
        topic_id = str(topic_id_raw).strip() if topic_id_raw is not None else ""
        known_concept_ids = [cid for cid in concept_ids if cid in concepts]
        if topic_id:
            topic = topics.get(topic_id)
            if not topic:
                errors.append(f"{prefix}:unknown-topic:{topic_id}")
            else:
                primary_members = {str(value).strip() for value in topic.get("concept_ids", []) if str(value).strip()}
                if known_concept_ids and not any(cid in primary_members for cid in known_concept_ids):
                    errors.append(f"{prefix}:primary-topic-not-represented:{topic_id}")
                topic_counts[topic_id] += 1
        else:
            if known_concept_ids and not any(cid in unassigned for cid in known_concept_ids):
                errors.append(f"{prefix}:unassigned-primary-topic-not-represented")
            topic_counts["__unassigned__"] += 1

        options = question.get("options", [])
        if not isinstance(options, list) or len(options) != 4:
            errors.append(f"{prefix}:exactly-four-options-required")
            options = []
        option_ids: list[str] = []
        option_texts: set[str] = set()
        for option_index, option in enumerate(options, start=1):
            oprefix = f"{prefix}:o{option_index}"
            if not isinstance(option, dict):
                errors.append(f"{oprefix}:must-be-object")
                continue
            oid = str(option.get("id", "")).strip().lower()
            option_ids.append(oid)
            if oid not in OPTION_IDS:
                errors.append(f"{oprefix}:id-must-be-a-b-c-d")
            text = str(option.get("text", "")).strip()
            feedback = str(option.get("feedback", "")).strip()
            if not text:
                errors.append(f"{oprefix}:text-required")
            else:
                ntext = normalize(text)
                if ntext in option_texts:
                    errors.append(f"{oprefix}:duplicate-option-text")
                option_texts.add(ntext)
                if ntext in FORBIDDEN_OPTION_PHRASES:
                    errors.append(f"{oprefix}:forbidden-meta-option")
            if not feedback:
                errors.append(f"{oprefix}:feedback-required")
        if len(set(option_ids)) != len(option_ids):
            errors.append(f"{prefix}:duplicate-option-id")
        if options and set(option_ids) != set(OPTION_IDS):
            errors.append(f"{prefix}:option-ids-must-be-a-b-c-d")

        correct = str(question.get("correct_option_id", "")).strip().lower()
        if correct not in OPTION_IDS or correct not in option_ids:
            errors.append(f"{prefix}:correct-option-invalid")

    represented = {key for key in topic_counts if key != "__unassigned__"}
    eligible_topics = {
        tid
        for tid, item in topics.items()
        if isinstance(item.get("concept_ids", []), list) and item.get("concept_ids")
    }
    uncovered = sorted(eligible_topics - represented)
    if uncovered and len(questions) >= len(eligible_topics):
        warnings.append("topics-not-covered:" + ",".join(uncovered))
    if unassigned and "__unassigned__" not in topic_counts and len(questions) >= max(1, len(eligible_topics) + 1):
        warnings.append("unassigned-concepts-not-covered")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "question_count": len(questions),
        "topic_counts": dict(sorted(topic_counts.items())),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
    }


def _html_safe_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _topic_labels(topics: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        tid: str(item.get("name") or tid)
        for tid, item in topics.items()
    }


QUIZ_CSS = r"""
:root {
  --quiz-bg: #f5f7fb;
  --quiz-card: #ffffff;
  --quiz-text: #172033;
  --quiz-muted: #667085;
  --quiz-line: #dce2ea;
  --quiz-accent: #3157d5;
  --quiz-accent-soft: #eef2ff;
  --quiz-good: #157347;
  --quiz-good-soft: #eaf7ef;
  --quiz-bad: #b42318;
  --quiz-bad-soft: #fff0ef;
  --quiz-shadow: 0 18px 46px rgba(16, 24, 40, .09);
}
* { box-sizing: border-box; }
body.quiz-page {
  margin: 0;
  min-height: 100vh;
  color: var(--quiz-text);
  background:
    radial-gradient(circle at 12% 0%, rgba(49,87,213,.08), transparent 30rem),
    var(--quiz-bg);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.quiz-shell { width: min(940px, calc(100% - 32px)); margin: 0 auto; padding: 40px 0 56px; }
.quiz-kicker { margin: 0 0 8px; color: var(--quiz-accent); font-size: .78rem; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
.quiz-title { margin: 0; font-size: clamp(1.9rem, 4vw, 3.2rem); line-height: 1.05; letter-spacing: -.035em; }
.quiz-subtitle { max-width: 720px; color: var(--quiz-muted); line-height: 1.65; margin: 16px 0 0; }
.quiz-card {
  margin-top: 28px; padding: clamp(20px, 4vw, 34px); border: 1px solid var(--quiz-line);
  border-radius: 22px; background: var(--quiz-card); box-shadow: var(--quiz-shadow);
}
.mode-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; margin-top: 22px; }
.mode-button {
  appearance: none; text-align: left; padding: 18px; border: 1px solid var(--quiz-line); border-radius: 16px;
  background: #fff; color: inherit; cursor: pointer; transition: .16s ease; font: inherit;
}
.mode-button:hover, .mode-button:focus-visible { border-color: var(--quiz-accent); transform: translateY(-1px); outline: 3px solid rgba(49,87,213,.12); }
.mode-button strong { display: block; font-size: 1rem; margin-bottom: 5px; }
.mode-button span { color: var(--quiz-muted); font-size: .91rem; line-height: 1.45; }
.quiz-topbar { display: flex; align-items: center; gap: 16px; justify-content: space-between; margin-bottom: 24px; }
.quiz-progress { flex: 1; height: 8px; border-radius: 999px; background: #edf0f4; overflow: hidden; }
.quiz-progress > span { display: block; height: 100%; width: 0; background: var(--quiz-accent); border-radius: inherit; transition: width .2s ease; }
.quiz-counter { color: var(--quiz-muted); font-size: .9rem; white-space: nowrap; }
.topic-chip { display: inline-flex; align-items: center; gap: 6px; padding: 7px 10px; border-radius: 999px; background: var(--quiz-accent-soft); color: #2847ad; font-size: .8rem; font-weight: 700; }
.question-title { margin: 16px 0 22px; font-size: clamp(1.25rem, 2.5vw, 1.65rem); line-height: 1.38; letter-spacing: -.015em; white-space: pre-wrap; }
.question-code { margin: -6px 0 22px; padding: 15px 16px; overflow-x: auto; border-radius: 13px; background: #101828; color: #f2f4f7; font: .92rem/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.options { display: grid; gap: 11px; }
.option {
  display: grid; grid-template-columns: 34px 1fr; gap: 12px; align-items: start; padding: 15px;
  border: 1px solid var(--quiz-line); border-radius: 15px; cursor: pointer; transition: .14s ease; background: #fff;
}
.option:hover { border-color: #aebbd0; }
.option > span:last-child { white-space: pre-wrap; }
.option input { position: absolute; opacity: 0; pointer-events: none; }
.option-letter {
  width: 31px; height: 31px; display: grid; place-items: center; border-radius: 9px;
  background: #f2f4f7; color: #475467; font-weight: 800; text-transform: uppercase;
}
.option.selected { border-color: var(--quiz-accent); background: var(--quiz-accent-soft); }
.option.selected .option-letter { background: var(--quiz-accent); color: white; }
.option.correct { border-color: #9bd3b1; background: var(--quiz-good-soft); }
.option.correct .option-letter { background: var(--quiz-good); color: #fff; }
.option.incorrect { border-color: #f1aaa4; background: var(--quiz-bad-soft); }
.option.incorrect .option-letter { background: var(--quiz-bad); color: #fff; }
.feedback {
  margin-top: 18px; padding: 16px 18px; border-radius: 14px; line-height: 1.58;
  background: #f8fafc; border: 1px solid var(--quiz-line);
}
.feedback.good { background: var(--quiz-good-soft); border-color: #b8dfc7; }
.feedback.bad { background: var(--quiz-bad-soft); border-color: #f2beb9; }
.feedback strong { display: block; margin-bottom: 5px; }
.quiz-actions { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; margin-top: 24px; }
.action-group { display: flex; flex-wrap: wrap; gap: 10px; }
.btn {
  appearance: none; border: 1px solid var(--quiz-line); border-radius: 11px; padding: 10px 15px;
  background: #fff; color: var(--quiz-text); font: inherit; font-weight: 700; cursor: pointer;
}
.btn:hover:not(:disabled), .btn:focus-visible:not(:disabled) { border-color: var(--quiz-accent); outline: 3px solid rgba(49,87,213,.12); }
.btn.primary { background: var(--quiz-accent); border-color: var(--quiz-accent); color: white; }
.btn.danger { color: var(--quiz-bad); }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.result-score { display: flex; align-items: baseline; gap: 12px; margin: 6px 0 20px; }
.result-score strong { font-size: clamp(2.6rem, 8vw, 5rem); line-height: 1; letter-spacing: -.06em; }
.result-score span { color: var(--quiz-muted); font-size: 1.05rem; }
.topic-results { display: grid; gap: 10px; margin: 22px 0; }
.topic-result { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--quiz-line); }
.review-list { display: grid; gap: 14px; margin-top: 24px; }
.review-item { padding: 17px; border: 1px solid var(--quiz-line); border-radius: 14px; background: #fff; }
.review-item h3 { margin: 0 0 10px; font-size: 1rem; line-height: 1.45; }
.review-item p { margin: 6px 0; line-height: 1.5; }
.review-item .muted { color: var(--quiz-muted); font-size: .9rem; }
.quiz-note { margin-top: 22px; color: var(--quiz-muted); font-size: .84rem; line-height: 1.5; }
.hidden { display: none !important; }
@media (max-width: 640px) {
  .quiz-shell { width: min(100% - 20px, 940px); padding-top: 22px; }
  .quiz-card { border-radius: 17px; padding: 18px; }
  .mode-grid { grid-template-columns: 1fr; }
  .quiz-topbar { align-items: flex-start; flex-direction: column; gap: 10px; }
  .quiz-counter { align-self: flex-end; margin-top: -28px; }
  .quiz-actions { flex-direction: column-reverse; }
  .action-group, .btn { width: 100%; }
  .action-group .btn { flex: 1; }
}
@media print {
  body.quiz-page { background: #fff; }
  .quiz-shell { width: 100%; padding: 0; }
  .quiz-card { box-shadow: none; }
  .quiz-actions, #start-card { display: none !important; }
}
"""

QUIZ_JS = r"""
(() => {
  const quiz = JSON.parse(document.getElementById('quiz-data').textContent);
  const topicLabels = JSON.parse(document.getElementById('quiz-topics').textContent);
  const startCard = document.getElementById('start-card');
  const playCard = document.getElementById('play-card');
  const resultCard = document.getElementById('result-card');
  const questionRoot = document.getElementById('question-root');
  const feedbackRoot = document.getElementById('feedback-root');
  const progressBar = document.getElementById('progress-bar');
  const counter = document.getElementById('counter');
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const checkBtn = document.getElementById('check-btn');
  const finishBtn = document.getElementById('finish-btn');
  const practiceFinishBtn = document.getElementById('practice-finish-btn');

  const state = { mode: null, index: 0, answers: {}, checked: {} };

  const optionById = (question, id) => question.options.find(option => option.id === id);
  const topicName = id => id ? (topicLabels[id] || id) : 'Sin tema asignado';

  function start(mode) {
    state.mode = mode;
    state.index = 0;
    state.answers = {};
    state.checked = {};
    startCard.classList.add('hidden');
    resultCard.classList.add('hidden');
    playCard.classList.remove('hidden');
    renderQuestion();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function selectAnswer(id) {
    const q = quiz.questions[state.index];
    if (state.mode === 'practice' && state.checked[q.id]) return;
    state.answers[q.id] = id;
    renderQuestion();
  }

  function renderQuestion() {
    const q = quiz.questions[state.index];
    const selected = state.answers[q.id] || '';
    const checked = !!state.checked[q.id];
    const pct = ((state.index + 1) / quiz.questions.length) * 100;
    progressBar.style.width = `${pct}%`;
    counter.textContent = `Pregunta ${state.index + 1} de ${quiz.questions.length}`;

    const options = q.options.map(option => {
      const classes = ['option'];
      if (selected === option.id) classes.push('selected');
      if (checked) {
        if (option.id === q.correct_option_id) classes.push('correct');
        else if (selected === option.id) classes.push('incorrect');
      }
      return `
        <label class="${classes.join(' ')}">
          <input type="radio" name="answer" value="${option.id}" ${selected === option.id ? 'checked' : ''}>
          <span class="option-letter">${option.id}</span>
          <span>${escapeHtml(option.text)}</span>
        </label>`;
    }).join('');

    questionRoot.innerHTML = `
      <span class="topic-chip">${escapeHtml(topicName(q.topic_id))} · ${escapeHtml(difficultyName(q.difficulty))}</span>
      <h2 class="question-title">${escapeHtml(q.prompt)}</h2>
      ${q.code ? `<pre class="question-code"><code>${escapeHtml(q.code)}</code></pre>` : ''}
      <div class="options">${options}</div>`;

    questionRoot.querySelectorAll('input[name="answer"]').forEach(input => {
      input.addEventListener('change', () => selectAnswer(input.value));
    });

    feedbackRoot.innerHTML = '';
    feedbackRoot.className = '';
    if (state.mode === 'practice' && checked) {
      const correct = selected === q.correct_option_id;
      const selectedOption = optionById(q, selected);
      const correctOption = optionById(q, q.correct_option_id);
      feedbackRoot.className = `feedback ${correct ? 'good' : 'bad'}`;
      feedbackRoot.innerHTML = correct
        ? `<strong>Correcto.</strong><span>${escapeHtml(correctOption.feedback)}</span>`
        : `<strong>No es la mejor respuesta.</strong>
           <span>${selectedOption ? escapeHtml(selectedOption.feedback) : 'No seleccionaste una opción.'}</span>
           <div style="margin-top:8px"><strong>Respuesta correcta: ${q.correct_option_id.toUpperCase()}.</strong> ${escapeHtml(correctOption.feedback)}</div>`;
    }

    prevBtn.disabled = state.index === 0;
    nextBtn.disabled = state.index === quiz.questions.length - 1;
    checkBtn.classList.toggle('hidden', state.mode !== 'practice');
    checkBtn.disabled = !selected || checked;
    finishBtn.classList.toggle('hidden', state.mode !== 'exam');
    practiceFinishBtn.classList.toggle('hidden', state.mode !== 'practice');
    finishBtn.textContent = `Finalizar (${Object.keys(state.answers).length}/${quiz.questions.length})`;
  }

  function checkCurrent() {
    const q = quiz.questions[state.index];
    if (!state.answers[q.id]) return;
    state.checked[q.id] = true;
    renderQuestion();
  }

  function finish() {
    if (state.mode === 'practice') {
      quiz.questions.forEach(q => {
        if (state.answers[q.id]) state.checked[q.id] = true;
      });
    }
    playCard.classList.add('hidden');
    renderResults();
    resultCard.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function renderResults() {
    let correct = 0;
    const topicStats = {};
    quiz.questions.forEach(q => {
      const topic = topicName(q.topic_id);
      if (!topicStats[topic]) topicStats[topic] = { correct: 0, total: 0 };
      topicStats[topic].total += 1;
      if (state.answers[q.id] === q.correct_option_id) {
        correct += 1;
        topicStats[topic].correct += 1;
      }
    });
    const pct = Math.round((correct / quiz.questions.length) * 100);
    document.getElementById('score').textContent = `${pct}%`;
    document.getElementById('score-detail').textContent = `${correct} de ${quiz.questions.length} correctas`;
    document.getElementById('topic-results').innerHTML = Object.entries(topicStats).map(([topic, stat]) => `
      <div class="topic-result"><span>${escapeHtml(topic)}</span><strong>${stat.correct}/${stat.total}</strong></div>
    `).join('');
    document.getElementById('review-list').innerHTML = quiz.questions.map((q, index) => {
      const selected = optionById(q, state.answers[q.id]);
      const correctOption = optionById(q, q.correct_option_id);
      const ok = selected && selected.id === q.correct_option_id;
      return `
        <article class="review-item">
          <span class="topic-chip">${index + 1} · ${escapeHtml(topicName(q.topic_id))}</span>
          <h3>${escapeHtml(q.prompt)}</h3>
          <p><strong>${ok ? '✓' : '✕'} Tu respuesta:</strong> ${selected ? `${selected.id.toUpperCase()}. ${escapeHtml(selected.text)}` : 'Sin responder'}</p>
          ${ok ? '' : `<p><strong>Correcta:</strong> ${correctOption.id.toUpperCase()}. ${escapeHtml(correctOption.text)}</p>`}
          ${!ok && selected ? `<p class="muted"><strong>Tu opción:</strong> ${escapeHtml(selected.feedback)}</p>` : ''}
          <p class="muted"><strong>Explicación:</strong> ${escapeHtml(correctOption.feedback)}</p>
        </article>`;
    }).join('');
  }

  function difficultyName(value) {
    return ({ basic: 'Básica', intermediate: 'Intermedia', advanced: 'Avanzada' })[value] || value;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  document.querySelectorAll('[data-start-mode]').forEach(button => {
    button.addEventListener('click', () => start(button.dataset.startMode));
  });
  prevBtn.addEventListener('click', () => { if (state.index > 0) { state.index -= 1; renderQuestion(); } });
  nextBtn.addEventListener('click', () => { if (state.index < quiz.questions.length - 1) { state.index += 1; renderQuestion(); } });
  checkBtn.addEventListener('click', checkCurrent);
  finishBtn.addEventListener('click', finish);
  practiceFinishBtn.addEventListener('click', finish);
  document.getElementById('retry-btn').addEventListener('click', () => {
    resultCard.classList.add('hidden');
    startCard.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
})();
"""


def render_quiz_html(data: dict[str, Any], *, source_sha256: str, topics: dict[str, dict[str, Any]]) -> str:
    title = str(data.get("title", "Quiz"))
    subtitle = str(data.get("subtitle", "")).strip() or "Multiple choice offline basado en el conocimiento canónico de la unidad."
    count = len(data.get("questions", []))
    quiz_json = _html_safe_json(data)
    topics_json = _html_safe_json(_topic_labels(topics))
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="quiz-source-sha256" content="{source_sha256}">
  <title>{escape(title)}</title>
  <style>{QUIZ_CSS}</style>
</head>
<body class="quiz-page">
  <main class="quiz-shell">
    <header>
      <p class="quiz-kicker">University Study · Quiz</p>
      <h1 class="quiz-title">{escape(title)}</h1>
      <p class="quiz-subtitle">{escape(subtitle)}</p>
    </header>

    <section id="start-card" class="quiz-card">
      <span class="topic-chip">{count} preguntas · 4 opciones · una respuesta correcta</span>
      <h2 class="question-title">Elegí cómo querés practicar</h2>
      <div class="mode-grid">
        <button class="mode-button" type="button" data-start-mode="practice">
          <strong>Práctica</strong>
          <span>Comprobás cada respuesta y recibís feedback antes de continuar.</span>
        </button>
        <button class="mode-button" type="button" data-start-mode="exam">
          <strong>Examen</strong>
          <span>No se revelan respuestas hasta finalizar. Podés volver y cambiar opciones.</span>
        </button>
      </div>
      <p class="quiz-note">Funciona offline y no actualiza <code>progress.json</code>. No es un entorno de examen seguro: las respuestas existen dentro del archivo para poder corregir sin servidor.</p>
    </section>

    <section id="play-card" class="quiz-card hidden">
      <div class="quiz-topbar">
        <div class="quiz-progress" aria-hidden="true"><span id="progress-bar"></span></div>
        <span id="counter" class="quiz-counter"></span>
      </div>
      <div id="question-root"></div>
      <div id="feedback-root" aria-live="polite"></div>
      <div class="quiz-actions">
        <div class="action-group">
          <button id="prev-btn" class="btn" type="button">Anterior</button>
          <button id="next-btn" class="btn" type="button">Siguiente</button>
        </div>
        <div class="action-group">
          <button id="check-btn" class="btn primary" type="button">Comprobar</button>
          <button id="practice-finish-btn" class="btn" type="button">Ver resultado</button>
          <button id="finish-btn" class="btn primary hidden" type="button">Finalizar</button>
        </div>
      </div>
    </section>

    <section id="result-card" class="quiz-card hidden">
      <p class="quiz-kicker">Resultado</p>
      <div class="result-score"><strong id="score">0%</strong><span id="score-detail"></span></div>
      <h2>Por tema</h2>
      <div id="topic-results" class="topic-results"></div>
      <h2>Revisión</h2>
      <div id="review-list" class="review-list"></div>
      <div class="quiz-actions">
        <button id="retry-btn" class="btn primary" type="button">Reintentar</button>
      </div>
    </section>
  </main>
  <script id="quiz-data" type="application/json">{quiz_json}</script>
  <script id="quiz-topics" type="application/json">{topics_json}</script>
  <script>{QUIZ_JS}</script>
</body>
</html>
"""


def render_command(course: Path, unit: str, input_path: Path, output_path: Path) -> dict[str, Any]:
    raw = input_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    validation = validate_quiz_document(data, course=course, unit=unit)
    if not validation["ok"]:
        return validation
    _, topics, _ = canonical_context(course, unit)
    html = render_quiz_html(data, source_sha256=sha256_bytes(raw), topics=topics)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return {
        **validation,
        "html": output_path.as_posix(),
        "source_sha256": sha256_bytes(raw),
        "html_sha256": sha256_file(output_path),
    }


def check_command(course: Path, unit: str, input_path: Path, html_path: Path) -> dict[str, Any]:
    raw = input_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    result = validate_quiz_document(data, course=course, unit=unit)
    errors = list(result.get("errors", []))
    if not html_path.is_file():
        errors.append("rendered-html-missing")
    else:
        html = html_path.read_text(encoding="utf-8")
        meta = SOURCE_META_RE.search(html)
        expected_sha = sha256_bytes(raw)
        if not meta or meta.group(1) != expected_sha:
            errors.append("rendered-source-sha-mismatch")
        payload_match = DATA_RE.search(html)
        if not payload_match:
            errors.append("rendered-quiz-data-missing")
        else:
            try:
                embedded = json.loads(payload_match.group(1))
            except json.JSONDecodeError:
                errors.append("rendered-quiz-data-invalid")
            else:
                if embedded != data:
                    errors.append("rendered-quiz-data-mismatch")
        for forbidden in ('<script src=', '<link rel="stylesheet"', "<link rel='stylesheet'"):
            if forbidden.lower() in html.lower():
                errors.append("rendered-html-not-self-contained")
                break
        for required_id in ("start-card", "play-card", "result-card", "question-root", "score", "topic-results"):
            if f'id="{required_id}"' not in html:
                errors.append(f"rendered-ui-missing:{required_id}")
    return {
        **result,
        "ok": not errors,
        "errors": errors,
        "source_sha256": sha256_bytes(raw),
        "html_sha256": sha256_file(html_path) if html_path.is_file() else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate/render offline study quizzes")
    sub = ap.add_subparsers(dest="command", required=True)

    for name in ("validate", "render", "check"):
        p = sub.add_parser(name)
        p.add_argument("--course", required=True)
        p.add_argument("--unit", required=True)
        p.add_argument("--input", required=True)
        if name in {"render", "check"}:
            p.add_argument("--html", required=True)
        if name == "check":
            p.add_argument("--write")

    args = ap.parse_args()
    course = Path(args.course).resolve()
    input_path = Path(args.input).resolve()

    if args.command == "validate":
        data = read_json(input_path)
        result = validate_quiz_document(data, course=course, unit=args.unit)
    elif args.command == "render":
        result = render_command(course, args.unit, input_path, Path(args.html).resolve())
    else:
        result = check_command(course, args.unit, input_path, Path(args.html).resolve())
        if args.write:
            out = Path(args.write).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
