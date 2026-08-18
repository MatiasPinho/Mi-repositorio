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

## Medium-specific review
A missing `visual_medium` on an existing derived plan entry means `diagram` for backward compatibility.

A `visual_medium: diagram` may carry exact labels, direction, grouping, order and topology because those semantics are declared in its validated deterministic spec. All existing deterministic-sketch review requirements below remain unchanged.

A `visual_medium: illustration` is only a supporting physical/conceptual likeness. It must be `visual_helpful`, while authoritative academic meaning stays in prose/HTML or a deterministic diagram. Do not demand photorealism or aesthetic perfection. A simple, recognizable, relevant and non-misleading illustration is sufficient; do not start an open-ended regeneration loop for style preference.

Generated illustration pixels must not be used to teach exact sequence, quantities, chronology, wiring/topology, formulas, taxonomies or assessment-critical relationships. Requested/generated text, labels, numbers or arrows inside the illustration are a policy defect; exact annotation belongs outside the pixels.

Hard fail:
- broken image paths in the published artifact;
- any rendered figure fails to decode (`complete != true`, `naturalWidth == 0` or `naturalHeight == 0`) in an audited viewport;
- unreadable/missing alt text for an essential figure;
- a derived diagram changes academic meaning;
- a reinterpretation drops, obscures or invents a label, relation, direction,
  scale or other meaningful feature;
- a deterministic sketch omits element-level provenance, does not match its
  registered spec hash, or contains a node/edge not present in that spec;
- a planned `visual_medium: diagram` is not backed by the registered deterministic SVG generator;
- a planned `visual_medium: illustration` is not backed by a registered `kind: illustration` record with `illustration_generation.method: generated-illustration`;
- a generated illustration is marked `visual_required` or is treated as authoritative evidence for an exact academic claim;
- a generated illustration visibly contains misleading labels/text/arrows or unsupported technical internals;
- `02-plan.json` says `reinterpret` but the final Markdown omits the planned
  derived asset or uses its source asset instead;
- a `preserve` decision has no explicit `fidelity_reason`, or a
  `preserve+derived_sketch` decision omits either member of the pair;
- a reinterpreted sketch carries an opaque canvas, internal notebook paper,
  outer frame or pasted-card plate instead of revealing the real document
  rules behind it;
- a generated illustration remains an opaque white/card canvas instead of the registered transparent notebook overlay;
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
- missing Playwright/Chromium is an incomplete environment and must be repaired with the project setup, not silently downgraded to a skipped visual review;
- browser auditing remains final document integration QA; it does not reopen an aesthetic image-regeneration loop.

Design-system fidelity:
- student Markdown expresses semantic roles, never local styling;
- no inline colors, custom HTML cards or per-course visual inventions;
- the normal page still reads as continuous editorial material rather than a dashboard;
- visual novelty must not compete with the concept hierarchy.
