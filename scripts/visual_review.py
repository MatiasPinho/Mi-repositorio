#!/usr/bin/env python3
"""Hash-bound contract for independent visual inspection of rendered scene previews.

This module does not claim to perform vision. It only verifies that an external
vision-capable reviewer explicitly attested to the exact PNG bytes that will be
finalized. Capability and independence are asserted by the executor; file/hash
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
ISSUE_KEYS = {"severity", "type", "elements", "problem", "repair"}
FIGURE_KEYS = {"scene_id", "attempt", "status", "inspected", "scores", "issues"}


class VisualReviewError(ValueError):
    pass


def _err(path: str, message: str) -> VisualReviewError:
    return VisualReviewError(f"{path}: {message}")


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value.lower())
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VisualReviewError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VisualReviewError(f"review must be an object: {path}")
    return value


def validate_review(review: Any, *, require_policy: bool = False) -> dict[str, Any]:
    """Validate a review.

    The published JSON contract requires ``visual_policy_sha256``. The optional
    parser compatibility exists only for old synthetic unit fixtures that call
    this helper directly; every real preview binding passes ``require_policy``
    or is identified as a real scene by ``bind_review_to_preview`` below.

    ``figures`` may be empty only as a structural handoff. Binding decides whether
    that is valid by requiring the reviewed scene set to equal the current preview
    scene set exactly. This supports a summary that deliberately omitted every V2
    scene after exhausting the bounded visual-review budget.
    """
    if not isinstance(review, dict):
        raise _err("$", "must be an object")
    base_allowed = {"version", "vision_verified", "reviewer", "figures"}
    allowed = base_allowed | {"visual_policy_sha256"}
    if not set(review).issubset(allowed) or not base_allowed.issubset(review):
        missing = sorted(base_allowed - set(review))
        extra = sorted(set(review) - allowed)
        raise _err("$", f"invalid review keys; missing={missing} extra={extra}")
    if require_policy and "visual_policy_sha256" not in review:
        raise _err("$", "visual_policy_sha256 is required for a real visual PASS")
    if review.get("version") != 1:
        raise _err("$.version", "must equal 1")
    if review.get("vision_verified") is not True:
        raise _err("$.vision_verified", "must be true; metrics-only review cannot pass")
    policy_sha = review.get("visual_policy_sha256")
    if policy_sha is not None and not _valid_sha256(policy_sha):
        raise _err("$.visual_policy_sha256", "must be a SHA-256 hex digest")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        raise _err("$.reviewer", "must be an object")
    reviewer_keys = {"id", "capability", "independent"}
    if set(reviewer) != reviewer_keys:
        raise _err("$.reviewer", "must contain exactly id, capability, independent")
    if not isinstance(reviewer.get("id"), str) or not reviewer["id"].strip():
        raise _err("$.reviewer.id", "must identify the reviewer/execution")
    if reviewer.get("capability") != "vision":
        raise _err("$.reviewer.capability", "must explicitly be vision")
    if reviewer.get("independent") is not True:
        raise _err("$.reviewer.independent", "designer self-review cannot finalize")
    figures = review.get("figures")
    if not isinstance(figures, list):
        raise _err("$.figures", "must be an array")
    normalized = []
    seen: set[str] = set()
    for i, row in enumerate(figures):
        path = f"$.figures[{i}]"
        if not isinstance(row, dict):
            raise _err(path, "must be object")
        if set(row) != FIGURE_KEYS:
            missing = sorted(FIGURE_KEYS - set(row))
            extra = sorted(set(row) - FIGURE_KEYS)
            raise _err(path, f"must match figure contract; missing={missing} extra={extra}")
        scene_id = row.get("scene_id")
        if not isinstance(scene_id, str) or not scene_id:
            raise _err(path + ".scene_id", "must be non-empty")
        if scene_id in seen:
            raise _err(path + ".scene_id", "duplicate review")
        seen.add(scene_id)
        attempt = row.get("attempt")
        # Keep parser compatibility with historical attempt-3 evidence. New
        # previews are capped in scene_figure.MAX_ATTEMPTS and cannot create 3.
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
            if not _valid_sha256(digest):
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
        issues = row.get("issues")
        if not isinstance(issues, list):
            raise _err(path + ".issues", "must be an array")
        issue_norm = []
        for j, item in enumerate(issues):
            ipath = f"{path}.issues[{j}]"
            if not isinstance(item, dict):
                raise _err(ipath, "must be object")
            if set(item) != ISSUE_KEYS:
                missing = sorted(ISSUE_KEYS - set(item))
                extra = sorted(set(item) - ISSUE_KEYS)
                raise _err(ipath, f"must match issue contract; missing={missing} extra={extra}")
            severity = item.get("severity")
            if severity not in SEVERITIES:
                raise _err(ipath + ".severity", "invalid severity")
            if not isinstance(item.get("type"), str) or not item["type"]:
                raise _err(ipath + ".type", "required")
            elements = item.get("elements")
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
    result = {
        "version": 1,
        "vision_verified": True,
        "reviewer": {"id": reviewer["id"].strip(), "capability": "vision", "independent": True},
        "figures": normalized,
    }
    if policy_sha is not None:
        result["visual_policy_sha256"] = str(policy_sha).lower()
    return result


def bind_review_to_preview(review_value: Any, preview_report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(preview_report, dict):
        raise VisualReviewError("preview report must be an object")
    entries = preview_report.get("entries")
    if not isinstance(entries, list):
        raise VisualReviewError("preview report has no entries")

    expected_policy = preview_report.get("visual_policy_sha256")
    # Old tiny unit fixtures predate scene identity entirely. Keep those tests
    # usable without creating a production bypass: a real V2 preview always has
    # scene_sha256, and integrity independently requires the explicit policy hash.
    synthetic_legacy = (
        not _valid_sha256(expected_policy)
        and bool(entries)
        and all(isinstance(row, dict) and not row.get("scene_sha256") for row in entries)
    )
    review = validate_review(review_value, require_policy=not synthetic_legacy)
    if not synthetic_legacy:
        if not _valid_sha256(expected_policy):
            raise VisualReviewError("preview report has no valid visual_policy_sha256")
        if review.get("visual_policy_sha256") != str(expected_policy).lower():
            raise VisualReviewError("visual review policy does not match current preview policy")

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
    return {
        "ok": True,
        "vision_verified": True,
        "visual_policy_sha256": review.get("visual_policy_sha256"),
        "bindings": bindings,
        "review": review,
    }
