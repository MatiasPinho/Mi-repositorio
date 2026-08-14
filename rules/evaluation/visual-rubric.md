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
- a pedagogical derived diagram ignores the planned notebook-sketch treatment
  without a fidelity reason;
- `source-first` is used as an automatic reason to preserve a reconstructible
  flow, tree, concept map, relation map or technical schematic;
- a pencil-like treatment is applied mechanically to a screenshot, dense
  chart, visual table, formula, code or other precision-sensitive content;
- `preserve+derived_sketch` duplicates the source without adding a simpler,
  supported mental model.

Hard fail:
- broken image paths in the published artifact;
- any rendered figure fails to decode (`complete != true`, `naturalWidth == 0` or `naturalHeight == 0`) in an audited viewport;
- unreadable/missing alt text for an essential figure;
- a derived diagram changes academic meaning;
- a reinterpretation drops, obscures or invents a label, relation, direction,
  scale or other meaningful feature;
- a deterministic sketch omits element-level provenance, does not match its
  registered spec hash, or contains a node/edge not present in that spec;
- `02-plan.json` says `reinterpret` but the final Markdown omits the planned
  derived SVG or uses its source asset instead;
- a `preserve` decision has no explicit `fidelity_reason`, or a
  `preserve+derived_sketch` decision omits either member of the pair;
- a reinterpreted sketch carries an opaque canvas, internal notebook paper,
  outer frame or pasted-card plate instead of revealing the real document
  rules behind it;
- generated nodes or edges use a single perfectly geometric trace instead of
  the audited deterministic pencil treatment;
- the artifact claims an image shows something the reviewer cannot verify from canonical/source evidence;
- a rendered summary/guide/rapid-review is published without a successful `visual_audit.py` browser report;
- the final response claims visual PASS when rendered screenshots were not actually available for inspection.

Rendered-browser evidence:
- `visual_audit.py` must complete with `audit.json -> ok: true` before publication;
- the auditor must force lazy images through loading/decoding before the full-page screenshots and report `images == loadedImages` for each selected viewport;
- inspect at least desktop and mobile screenshots for hierarchy, clipping/overflow, figure legibility, spacing and callout readability;
- horizontal overflow that hides study content on mobile is a visual failure even when a scroll container technically exists;
- HTML-string checks, registry checks and image-path checks are integrity evidence, not substitutes for rendered visual evidence;
- missing Playwright/Chromium is an incomplete environment and must be repaired with the project setup, not silently downgraded to a skipped visual review.

Design-system fidelity:
- student Markdown expresses semantic roles, never local styling;
- no inline colors, custom HTML cards or per-course visual inventions;
- the normal page still reads as continuous editorial material rather than a dashboard;
- visual novelty must not compete with the concept hierarchy.
