# Visual-learning reviewer rubric

Score `visual_support` from 0–5.

A 5 means either:
- the scope genuinely does not benefit from figures and the artifact correctly stays mostly textual; or
- every high-value visual opportunity is handled with a relevant, legible figure placed near its explanation, with no decorative clutter.

Lower the score when:
- a structural/spatial/process concept is explained with dense prose despite an available useful figure;
- figures are decorative, duplicated or irrelevant;
- captions do not say what the learner should notice;
- figure and explanation are far apart;
- a figure introduces unsupported information;
- color/visual emphasis is inconsistent or used as the sole meaning channel;
- raw source screenshots are dumped without interpretation.

Hard fail:
- broken image paths in the published artifact;
- unreadable/missing alt text for an essential figure;
- a derived diagram changes academic meaning;
- the artifact claims an image shows something the reviewer cannot verify from canonical/source evidence;
- a rendered summary/guide/rapid-review is published without a successful `visual_audit.py` browser report;
- the final response claims visual PASS when rendered screenshots were not actually available for inspection.

Rendered-browser evidence:
- `visual_audit.py` must complete with `audit.json -> ok: true` before publication;
- inspect at least desktop and mobile screenshots for hierarchy, clipping/overflow, figure legibility, spacing and callout readability;
- HTML-string checks, registry checks and image-path checks are integrity evidence, not substitutes for rendered visual evidence;
- missing Playwright/Chromium is an incomplete environment and must be repaired with the project setup, not silently downgraded to a skipped visual review.

Design-system fidelity:
- student Markdown expresses semantic roles, never local styling;
- no inline colors, custom HTML cards or per-course visual inventions;
- the normal page still reads as continuous editorial material rather than a dashboard;
- visual novelty must not compete with the concept hierarchy.
