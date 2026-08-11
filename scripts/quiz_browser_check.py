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


def _practice(page: Page, html: str, quiz: dict[str, Any], screenshot: Path | None) -> dict[str, Any]:
    _load(page, html)
    page.click('[data-start-mode="practice"]')
    page.wait_for_selector('#play-card:not(.hidden)')
    first = quiz["questions"][0]
    correct = str(first["correct_option_id"])
    wrong = next(str(option["id"]) for option in first["options"] if str(option["id"]) != correct)
    _choose(page, wrong)
    before = page.locator('#feedback-root').inner_text().strip()
    _assert(not before, "practice-feedback-revealed-before-check")
    _assert(page.locator('label.option.correct').count() == 0, "practice-correctness-highlighted-before-check")
    page.click('#check-btn')
    feedback = page.locator('#feedback-root').inner_text().strip()
    _assert("No es la mejor respuesta" in feedback, "practice-wrong-feedback-missing")
    _assert("Respuesta correcta" in feedback, "practice-correct-answer-feedback-missing")
    _assert(page.locator('label.option.correct').count() == 1, "practice-correct-option-not-highlighted")
    _assert(page.locator('label.option.incorrect').count() == 1, "practice-wrong-option-not-highlighted")
    if screenshot is not None:
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=True)
    return {
        "ok": True,
        "checked_question_id": str(first.get("id", "")),
        "wrong_option_id": wrong,
        "feedback_visible_after_check": True,
    }


def _exam(
    page: Page,
    html: str,
    quiz: dict[str, Any],
    question_screenshot: Path | None,
    result_screenshot: Path | None,
) -> dict[str, Any]:
    _load(page, html)
    page.click('[data-start-mode="exam"]')
    page.wait_for_selector('#play-card:not(.hidden)')
    questions = quiz["questions"]
    for index, question in enumerate(questions):
        _choose(page, str(question["correct_option_id"]))
        feedback = page.locator('#feedback-root').inner_text().strip()
        _assert(not feedback, f"exam-feedback-revealed-before-submit:q{index + 1}")
        _assert(page.locator('label.option.correct').count() == 0, f"exam-correctness-highlighted-before-submit:q{index + 1}")
        if index == 0 and question_screenshot is not None:
            question_screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(question_screenshot), full_page=True)
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
    if result_screenshot is not None:
        result_screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(result_screenshot), full_page=True)
    return {
        "ok": True,
        "answered": len(questions),
        "score": score,
        "reviewed": len(questions),
    }


def run_check(json_path: Path, html_path: Path, out_dir: Path | None = None) -> dict[str, Any]:
    json_path = json_path.resolve()
    html_path = html_path.resolve()
    quiz = json.loads(json_path.read_text(encoding="utf-8"))
    questions = quiz.get("questions", []) if isinstance(quiz, dict) else []
    screenshot_paths = {
        "practice_feedback": (out_dir / "practice-feedback.png").resolve() if out_dir is not None else None,
        "exam_question_mobile": (out_dir / "exam-question-mobile.png").resolve() if out_dir is not None else None,
        "exam_result_mobile": (out_dir / "exam-result-mobile.png").resolve() if out_dir is not None else None,
    }
    if not isinstance(questions, list) or not questions:
        return {
            "ok": False,
            "engine": "playwright-chromium",
            "errors": ["quiz-questions-required"],
            "source_sha256": sha256_file(json_path),
            "html_sha256": sha256_file(html_path) if html_path.is_file() else None,
            "modes": {},
            "screenshots": {},
        }
    if not html_path.is_file():
        return {
            "ok": False,
            "engine": "playwright-chromium",
            "errors": ["rendered-html-missing"],
            "source_sha256": sha256_file(json_path),
            "html_sha256": None,
            "modes": {},
            "screenshots": {},
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
                    modes["practice"] = _practice(page, html, quiz, screenshot_paths["practice_feedback"])
                except Exception as exc:
                    errors.append(f"practice:{type(exc).__name__}:{exc}")
                    modes["practice"] = {"ok": False}

                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.set_default_timeout(8000)
                try:
                    modes["exam"] = _exam(
                        page,
                        html,
                        quiz,
                        screenshot_paths["exam_question_mobile"],
                        screenshot_paths["exam_result_mobile"],
                    )
                except Exception as exc:
                    errors.append(f"exam:{type(exc).__name__}:{exc}")
                    modes["exam"] = {"ok": False}
            finally:
                browser.close()
    except Exception as exc:
        errors.append(f"browser:{type(exc).__name__}:{exc}")

    screenshots: dict[str, str] = {}
    if out_dir is not None:
        for name, path in screenshot_paths.items():
            if path is None or not path.is_file() or path.stat().st_size <= 0:
                errors.append(f"screenshot-missing:{name}")
            else:
                screenshots[name] = path.as_posix()

    return {
        "ok": not errors and all(isinstance(row, dict) and row.get("ok") is True for row in modes.values()) and set(modes) == {"practice", "exam"},
        "engine": "playwright-chromium",
        "errors": errors,
        "source_sha256": sha256_file(json_path),
        "html_sha256": sha256_file(html_path),
        "modes": modes,
        "screenshots": screenshots,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Exercise offline quiz interactions in real Chromium")
    ap.add_argument("--json", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--out")
    ap.add_argument("--write")
    args = ap.parse_args()

    json_path = Path(args.json).resolve()
    html_path = Path(args.html).resolve()
    out_dir = Path(args.out).resolve() if args.out else None
    result = run_check(json_path, html_path, out_dir)
    if args.write:
        output = Path(args.write).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
