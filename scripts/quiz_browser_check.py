#!/usr/bin/env python3
"""Real-browser interaction smoke test for a rendered offline quiz."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load(page: Page, html: str) -> None:
    page.set_content(html, wait_until="load")
    page.wait_for_selector('[data-start-mode="practice"]')
    page.wait_for_selector('[data-start-mode="exam"]')


def _choose(page: Page, option_id: str) -> None:
    option = page.locator(f'label.option:has(input[value="{option_id}"])')
    _assert(option.count() == 1, f"option-not-found:{option_id}")
    option.click()


def _practice(page: Page, html: str, quiz: dict[str, Any]) -> dict[str, Any]:
    _load(page, html)
    page.click('[data-start-mode="practice"]')
    page.wait_for_selector('#play-card:not(.hidden)')
    first = quiz["questions"][0]
    correct = str(first["correct_option_id"])
    _choose(page, correct)
    before = page.locator('#feedback-root').inner_text().strip()
    _assert(not before, "practice-feedback-revealed-before-check")
    page.click('#check-btn')
    feedback = page.locator('#feedback-root').inner_text().strip()
    _assert("Correcto" in feedback, "practice-correct-feedback-missing")
    _assert(page.locator('label.option.correct').count() == 1, "practice-correct-option-not-highlighted")
    return {
        "ok": True,
        "checked_question_id": str(first.get("id", "")),
        "feedback_visible_after_check": True,
    }


def _exam(page: Page, html: str, quiz: dict[str, Any]) -> dict[str, Any]:
    _load(page, html)
    page.click('[data-start-mode="exam"]')
    page.wait_for_selector('#play-card:not(.hidden)')
    questions = quiz["questions"]
    for index, question in enumerate(questions):
        _choose(page, str(question["correct_option_id"]))
        feedback = page.locator('#feedback-root').inner_text().strip()
        _assert(not feedback, f"exam-feedback-revealed-before-submit:q{index + 1}")
        _assert(page.locator('label.option.correct').count() == 0, f"exam-correctness-highlighted-before-submit:q{index + 1}")
        if index < len(questions) - 1:
            page.click('#next-btn')
    page.click('#finish-btn')
    page.wait_for_selector('#result-card:not(.hidden)')
    score = page.locator('#score').inner_text().strip()
    detail = page.locator('#score-detail').inner_text().strip()
    _assert(score == "100%", f"exam-score-unexpected:{score}")
    _assert(detail == f"{len(questions)} de {len(questions)} correctas", f"exam-score-detail-unexpected:{detail}")
    _assert(page.locator('#review-list .review-item').count() == len(questions), "exam-review-count-mismatch")
    _assert(page.locator('#topic-results .topic-result').count() >= 1, "exam-topic-results-missing")
    return {
        "ok": True,
        "answered": len(questions),
        "score": score,
        "reviewed": len(questions),
    }


def run_check(json_path: Path, html_path: Path) -> dict[str, Any]:
    quiz = json.loads(json_path.read_text(encoding="utf-8"))
    questions = quiz.get("questions", []) if isinstance(quiz, dict) else []
    if not isinstance(questions, list) or not questions:
        return {
            "ok": False,
            "engine": "playwright-chromium",
            "errors": ["quiz-questions-required"],
            "source_sha256": sha256_file(json_path),
            "html_sha256": sha256_file(html_path) if html_path.is_file() else None,
            "modes": {},
        }
    if not html_path.is_file():
        return {
            "ok": False,
            "engine": "playwright-chromium",
            "errors": ["rendered-html-missing"],
            "source_sha256": sha256_file(json_path),
            "html_sha256": None,
            "modes": {},
        }

    html = html_path.read_text(encoding="utf-8")
    modes: dict[str, Any] = {}
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.set_default_timeout(8000)
                try:
                    modes["practice"] = _practice(page, html, quiz)
                except Exception as exc:
                    errors.append(f"practice:{type(exc).__name__}:{exc}")
                    modes["practice"] = {"ok": False}

                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.set_default_timeout(8000)
                try:
                    modes["exam"] = _exam(page, html, quiz)
                except Exception as exc:
                    errors.append(f"exam:{type(exc).__name__}:{exc}")
                    modes["exam"] = {"ok": False}
            finally:
                browser.close()
    except Exception as exc:
        errors.append(f"browser:{type(exc).__name__}:{exc}")

    return {
        "ok": not errors and all(isinstance(row, dict) and row.get("ok") is True for row in modes.values()) and set(modes) == {"practice", "exam"},
        "engine": "playwright-chromium",
        "errors": errors,
        "source_sha256": sha256_file(json_path),
        "html_sha256": sha256_file(html_path),
        "modes": modes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Exercise offline quiz interactions in real Chromium")
    ap.add_argument("--json", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--write")
    args = ap.parse_args()

    json_path = Path(args.json).resolve()
    html_path = Path(args.html).resolve()
    result = run_check(json_path, html_path)
    if args.write:
        output = Path(args.write).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
