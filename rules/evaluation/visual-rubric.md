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
- raw source screenshots are dumped without interpretation;
- `source-first` is used as an automatic reason to preserve a reconstructible diagram;
- a pencil-like treatment is applied mechanically to precision-sensitive source evidence;
- `preserve+derived_sketch` duplicates the source without adding a simpler supported mental model.

## Medium-specific review
### Deterministic diagrams
A `visual_medium: diagram` is allowed to carry exact labels, direction, grouping, order and topology because those semantics are declared in its validated structured spec. Review academic meaning against the spec/provenance, not against aesthetic preference.

### Generated illustrations
A `visual_medium: illustration` is a supporting likeness only. It should help the learner recognize a physical/conceptual object while all authoritative academic meaning stays in prose/HTML or a deterministic diagram.

Do not demand photorealism or aesthetic perfection. Do reject an illustration when it visibly introduces misleading academic content. It must not be used to teach exact sequence, quantities, chronology, wiring/topology, formulas, taxonomies or assessment-critical relationships. Requested/generated text, labels, numbers or arrows inside the illustration are a policy defect; exact annotation belongs outside the pixels.

An illustration that is simple, recognizable, relevant and non-misleading is sufficient. Do not trigger an open-ended regeneration loop merely to improve style.

## Hard fail
- broken image paths in the published artifact;
- any rendered figure fails to decode (`complete != true`, `naturalWidth == 0` or `naturalHeight == 0`) in an audited viewport;
- unreadable/missing alt text for an essential figure;
- a derived diagram changes academic meaning;
- a deterministic reinterpretation drops, obscures or invents a meaningful label, relation, direction, scale, order or grouping;
- a deterministic sketch omits required provenance, does not match its registered spec hash, or contains a node/edge not present in that spec;
- a planned `visual_medium: diagram` is not backed by the registered deterministic SVG generator;
- a planned `visual_medium: illustration` is not backed by a registered `kind: illustration` record with `illustration_generation.method: generated-illustration`;
- a generated illustration is marked `visual_required` or is treated as authoritative evidence for an exact academic claim;
- a generated illustration visibly contains misleading labels/text/arrows or unsupported technical internals;
- `02-plan.json` says `reinterpret` but final Markdown omits the planned derived asset or substitutes a source asset;
- a `preserve` decision has no explicit `fidelity_reason`, or `preserve+derived_sketch` omits either member;
- a derived notebook visual is rendered as a pasted opaque page/card rather than integrating with the real document sheet;
- the artifact claims an image proves something the reviewer cannot verify from canonical/source evidence;
- a rendered summary/guide/rapid-review is published without a successful `visual_audit.py` browser report.

## Rendered-browser evidence
- `visual_audit.py` must complete with `audit.json -> ok: true` before publication;
- the auditor forces lazy images through loading/decoding before screenshots and reports `images == loadedImages` for selected viewports;
- inspect at least desktop and mobile screenshots for hierarchy, clipping/overflow, figure legibility, spacing and callout readability;
- horizontal overflow that hides study content on mobile is a visual failure;
- HTML-string, registry and path checks are integrity evidence, not substitutes for rendered evidence;
- browser auditing is final integration QA, not a second illustration-design pipeline.

## Design-system fidelity
- student Markdown expresses semantic roles, never local styling;
- no inline colors, custom HTML cards or per-course visual inventions;
- the normal page reads as continuous editorial material rather than a dashboard;
- visual novelty must not compete with the concept hierarchy.
