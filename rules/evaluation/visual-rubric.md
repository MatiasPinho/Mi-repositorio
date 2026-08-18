# Visual-learning reviewer rubric

`visual_support` is the academic/pedagogical score: did the artifact choose useful visuals, preserve source truth and place them where they help learning?

Score `visual_support` from 0–5.

A 5 means either:
- the scope genuinely does not benefit from figures and the artifact correctly stays mostly textual; or
- every high-value visual opportunity is handled with a relevant figure placed near its explanation, with no decorative clutter and no unsupported visual claims.

Lower the score when a structural/spatial/process concept is explained with dense prose despite a useful visual opportunity; figures are decorative, duplicated or irrelevant; captions do not say what to notice; figure and explanation are far apart; source-first is misused as a pixel-preservation shortcut; or `preserve+derived_sketch` adds no simpler mental model.

## Hybrid representational fit
The active summary visual system chooses among deterministic diagrams, optional generated illustrations and preserved source figures. Judge whether the medium matches the teaching job.

- **Exact structure** — flows, cycles, timelines, hierarchies, architectures, state changes, buses, algorithms and other order/topology-bearing concepts should use deterministic diagrams or exact source evidence.
- **Physical recognition** — CPU package, RAM module, disk, keyboard, monitor, printer and similar recognizable objects may use a simple generated pencil illustration when likeness itself helps the learner.
- **Precision-sensitive evidence** — screenshots, charts, notation-heavy figures, formulas, geometry, circuits and exact layouts should remain preserved when reconstruction risks information loss.

A generated illustration is supporting recognition only. It must never be the sole carrier of an exact academic relationship, label, quantity, chronology, formula or topology.

## Graphic explanatory value
Inspect whether the visual itself carries useful explanatory work.

When a deterministic diagram is mostly a grid/row of titled boxes whose contents are short prose paraphrases, ask whether replacing the entire figure with ordinary text would lose meaningful understanding. If the answer is no **and** the concept offered a real graphical opportunity (mechanism, internal parts, flow, state change, relationship, hierarchy, spatial contrast or useful micro-example), lower `visual_support`.

For a **physical/tangible/recognizable component**, a generic titled rectangle should not receive full pedagogical credit when a simple recognizable illustration would safely improve the mental model. A plain box labeled `CPU` is an example of **generic-box substitution** when the concept is being represented physically rather than as a logical subsystem.

For a **process, sequence or state change**, prefer visible flow, cycle, path, transition or ordering rather than independent prose cards.

For an **architecture/system**, prefer meaningful spatial arrangement, layers, buses, connections, boundaries or nesting when those relationships are supported.

For **historical/staged evolution**, prefer an explicit deterministic temporal progression when chronology is the point.

Do **not** penalize boxes merely for being boxes. Containers are appropriate when boundaries, grouping, architecture, memory regions, layers or containment are themselves part of the concept. Never demand decorative realism or unsupported internals.

## Generated illustration boundary
Generated illustrations do not get a separate open-ended image-review cycle.

During normal academic review, verify only semantic appropriateness from the plan/metadata:
- the illustration is `visual_helpful`, not `visual_required`;
- its purpose is recognition/support rather than exact evidence;
- its compact semantic spec has provenance;
- exact facts remain in prose, deterministic diagrams or preserved source evidence.

During the final rendered-browser audit, reject an illustration only for an obvious integration or truth problem such as:
- broken/missing image;
- unreadable or misleading generated text/labels inside the pixels;
- a subject that is plainly unrelated to its caption/concept;
- clipping, extreme blur or effectively blank output;
- opaque pasted white card that breaks the notebook integration;
- a generated image being used where exact topology/chronology/labels are required.

A style preference alone does not trigger regeneration. If a generated illustration fails final QA, omit that optional visual for the run rather than starting an unbounded prompt/review loop.

## Deterministic diagram boundary
Exact diagrams remain auditable through compact structured specs and deterministic SVG generation. Hard fail when a diagram:
- invents or drops an academic relationship;
- has ambiguous direction/order where direction/order matters;
- contains unreadable labels or clipping;
- substitutes a source asset when the plan says `reinterpret`;
- violates the registered spec/asset hash contract;
- relies on generated image pixels to express exact structure.

The old schema-2 free-composition engine may still be tested/used for historical compatibility, but its independent scene-review protocol is no longer a required gate for the active `/resumen` hybrid path.

## General hard failures
- broken image paths in the published artifact;
- any rendered image fails to decode (`complete != true`, `naturalWidth == 0` or `naturalHeight == 0`);
- unreadable/missing alt text for an essential figure;
- a derived figure changes academic meaning, drops meaningful relations or invents unsupported content;
- `02-plan.json` says `reinterpret` but the final artifact omits the planned derived asset or substitutes its source asset;
- a `preserve` decision lacks `fidelity_reason`, or `preserve+derived_sketch` omits either member;
- a generated notebook overlay carries opaque paper/background pixels instead of using the document's real notebook surface;
- a rendered artifact is published without a successful browser audit.

## Rendered-browser evidence
Use `scripts/visual_audit.py` for the active hybrid summary path. The browser auditor must force images to load/decode, reject horizontal content overflow and require the complete Playwright/Chromium environment. HTML-string, registry and path checks are integrity evidence, not substitutes for rendered integration checks.

Inspect at least desktop and mobile document screenshots for hierarchy/integration. This final audit checks the artifact as the learner sees it; it is not an image-generation refinement loop.

## Design-system fidelity
- student Markdown expresses semantic roles, never local styling;
- no inline colors, custom HTML cards or per-course visual inventions;
- the normal page remains a Carpeta university-study notebook rather than a dashboard;
- canonical ruled paper/binding cues are intentional product grammar;
- the Neucha/Architects Daughter notebook typography, hand-drawn tables, captions and other visual-system improvements remain part of the document renderer;
- visual novelty must not compete with the concept hierarchy.
