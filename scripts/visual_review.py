#!/usr/bin/env python3
"""Hash-bound contract for independent visual inspection of rendered scene previews.

This module does not claim to perform vision.  It only verifies that an external
vision-capable reviewer explicitly attested to the exact PNG bytes that will be
finalized.  Capability and independence are asserted by the executor; file/hash
binding is deterministic and mechanically enforced here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCORE_KEYS = {
    "legibility", "spacing", "hierarchy", "connections", "density",
    "composition", "pencil_fidelity", "pedagogical_value", "responsive",
    "academic_fidelity",
}
SEVERITIES = {"blocking", "major", "minor"}


class VisualReviewError(ValueError):
    pass


def _err(path: str, message: str) -> VisualReviewError:
    return VisualReviewError(f"{path}: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VisualReviewError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VisualReviewError(f"review must be an object: {path}")
    return value


def validate_review(review: Any) -> dict[str, Any]:
    if not isinstance(review, dict):
        raise _err("$", "must be an object")
    allowed = {"version", "vision_verified", "reviewer", "figures"}
    extra = sorted(set(review) - allowed)
    if extra:
        raise _err("$", "unknown fields: " + ", ".join(extra))
    if review.get("version") != 1:
        raise _err("$.version", "must equal 1")
    if review.get("vision_verified") is not True:
        raise _err("$.vision_verified", "must be true; metrics-only review cannot pass")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        raise _err("$.reviewer", "must be an object")
    if set(reviewer) - {"id", "capability", "independent"}:
        raise _err("$.reviewer", "unknown reviewer fields")
    if not isinstance(reviewer.get("id"), str) or not reviewer["id"].strip():
        raise _err("$.reviewer.id", "must identify the reviewer/execution")
    if reviewer.get("capability") != "vision":
        raise _err("$.reviewer.capability", "must explicitly be vision")
    if reviewer.get("independent") is not True:
        raise _err("$.reviewer.independent", "designer self-review cannot finalize")
    figures = review.get("figures")
    if not isinstance(figures, list) or not figures:
        raise _err("$.figures", "must contain at least one reviewed scene")
    normalized = []
    seen: set[str] = set()
    for i, row in enumerate(figures):
        path = f"$.figures[{i}]"
        if not isinstance(row, dict):
            raise _err(path, "must be object")
        allowed_row = {"scene_id", "attempt", "status", "inspected", "scores", "issues"}
        extra = sorted(set(row) - allowed_row)
        if extra:
            raise _err(path, "unknown fields: " + ", ".join(extra))
        scene_id = row.get("scene_id")
        if not isinstance(scene_id, str) or not scene_id:
            raise _err(path + ".scene_id", "must be non-empty")
        if scene_id in seen:
            raise _err(path + ".scene_id", "duplicate review")
        seen.add(scene_id)
        attempt = row.get("attempt")
        if isinstance(attempt, bool) or not isinstance(attempt, int) or not (1 <= attempt <= 3):
            raise _err(path + ".attempt", "must be integer 1..3")
        status = row.get("status")
        if status not in {"pass", "fail"}:
            raise _err(path + ".status", "must be pass or fail")
        inspected = row.get("inspected")
        if not isinstance(inspected, list) or len(inspected) != 2:
            raise _err(path + ".inspected", "must bind exactly wide and narrow PNGs")
        inspected_norm = []
        variants = set()
        for j, item in enumerate(inspected):
            ipath = f"{path}.inspected[{j}]"
            if not isinstance(item, dict) or set(item) != {"variant", "file", "sha256"}:
                raise _err(ipath, "must contain exactly variant,file,sha256")
            variant = item.get("variant")
            if variant not in {"wide", "narrow"} or variant in variants:
                raise _err(ipath + ".variant", "must uniquely identify wide/narrow")
            variants.add(variant)
            if not isinstance(item.get("file"), str) or not item["file"]:
                raise _err(ipath + ".file", "must be non-empty")
            digest = item.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
                raise _err(ipath + ".sha256", "must be a SHA-256 hex digest")
            inspected_norm.append(dict(item))
        if variants != {"wide", "narrow"}:
            raise _err(path + ".inspected", "must include wide and narrow")
        scores = row.get("scores")
        if not isinstance(scores, dict) or set(scores) != SCORE_KEYS:
            raise _err(path + ".scores", "must contain exactly: " + ", ".join(sorted(SCORE_KEYS)))
        score_norm = {}
        for key in sorted(SCORE_KEYS):
            value = scores[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 5:
                raise _err(f"{path}.scores.{key}", "must be 0..5")
            score_norm[key] = float(value)
        issues = row.get("issues", [])
        if not isinstance(issues, list):
            raise _err(path + ".issues", "must be an array")
        issue_norm = []
        for j, item in enumerate(issues):
            ipath = f"{path}.issues[{j}]"
            if not isinstance(item, dict):
                raise _err(ipath, "must be object")
            if set(item) - {"severity", "type", "elements", "problem", "repair"}:
                raise _err(ipath, "unknown fields")
            severity = item.get("severity")
            if severity not in SEVERITIES:
                raise _err(ipath + ".severity", "invalid severity")
            if not isinstance(item.get("type"), str) or not item["type"]:
                raise _err(ipath + ".type", "required")
            elements = item.get("elements", [])
            if not isinstance(elements, list) or any(not isinstance(x, str) or not x for x in elements):
                raise _err(ipath + ".elements", "must be string ids")
            if not isinstance(item.get("problem"), str) or not item["problem"].strip():
                raise _err(ipath + ".problem", "required")
            if not isinstance(item.get("repair"), str) or not item["repair"].strip():
                raise _err(ipath + ".repair", "required")
            issue_norm.append(dict(item))
        if status == "pass":
            if any(value < 4 for value in score_norm.values()):
                raise _err(path + ".scores", "PASS requires every visual score >= 4")
            if any(item["severity"] in {"blocking", "major"} for item in issue_norm):
                raise _err(path + ".issues", "PASS cannot contain blocking/major issues")
        normalized.append({
            "scene_id": scene_id,
            "attempt": attempt,
            "status": status,
            "inspected": inspected_norm,
            "scores": score_norm,
            "issues": issue_norm,
        })
    return {
        "version": 1,
        "vision_verified": True,
        "reviewer": {"id": reviewer["id"].strip(), "capability": "vision", "independent": True},
        "figures": normalized,
    }


def bind_review_to_preview(review_value: Any, preview_report: dict[str, Any]) -> dict[str, Any]:
    review = validate_review(review_value)
    entries = preview_report.get("entries") if isinstance(preview_report, dict) else None
    if not isinstance(entries, list):
        raise VisualReviewError("preview report has no entries")
    preview_by_id = {
        row.get("scene_id"): row for row in entries
        if isinstance(row, dict) and row.get("scene_id")
    }
    reviewed_by_id = {row["scene_id"]: row for row in review["figures"]}
    if set(reviewed_by_id) != set(preview_by_id):
        raise VisualReviewError(
            "reviewed scene set does not match preview: "
            f"review={sorted(reviewed_by_id)} preview={sorted(preview_by_id)}"
        )
    bindings = []
    for scene_id, preview in preview_by_id.items():
        row = reviewed_by_id[scene_id]
        if row["attempt"] != preview.get("attempt"):
            raise VisualReviewError(f"{scene_id}: review attempt is stale")
        if row["status"] != "pass":
            raise VisualReviewError(f"{scene_id}: visual review did not pass")
        inspected = {item["variant"]: item for item in row["inspected"]}
        variants = preview.get("variants", {})
        for variant in ("wide", "narrow"):
            expected = variants.get(variant, {})
            got = inspected[variant]
            if got["file"] != expected.get("png") or got["sha256"].lower() != str(expected.get("png_sha256", "")).lower():
                raise VisualReviewError(f"{scene_id}:{variant}: reviewed screenshot does not match current preview")
            path = Path(got["file"])
            if not path.is_file():
                raise VisualReviewError(f"{scene_id}:{variant}: reviewed screenshot missing: {path}")
        bindings.append({"scene_id": scene_id, "attempt": row["attempt"], "status": "pass"})
    return {"ok": True, "vision_verified": True, "bindings": bindings, "review": review}
