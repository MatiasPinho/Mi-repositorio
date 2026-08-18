# Visual-learning reviewer rubric

`visual_support` remains the academic/pedagogical score: did the artifact choose useful visuals, preserve source truth and place them where they help learning? It does **not** certify that a generated figure is visually well executed.

Score `visual_support` from 0–5.

A 5 means either:
- the scope genuinely does not benefit from figures and the artifact correctly stays mostly textual; or
- every high-value visual opportunity is handled with a relevant figure placed near its explanation, with no decorative clutter and no unsupported visual claims.

Lower the score when a structural/spatial/process concept is explained with dense prose despite a useful visual opportunity; figures are decorative, duplicated or irrelevant; captions do not say what to notice; figure and explanation are far apart; source-first is misused as a pixel-preservation shortcut; or `preserve+derived_sketch` adds no simpler mental model.

## Visual System V2 execution gate
A schema-2 derived scene additionally requires a separate **independent vision review** of its actual `wide` and `narrow` preview PNGs before it can be registered. This is a pass/fail execution gate, not an average that can be hidden inside `visual_support`.

The reviewer scores 0–5 for exactly these dimensions:
- `legibility`: every label is readable without zoom and nothing is clipped;
- `spacing`: elements do not look collapsed, accidentally attached or needlessly cramped;
- `hierarchy`: the first thing to inspect and the intended reading structure are clear;
- `connections`: arrows/routes are traceable, unambiguous and do not run through text or unrelated objects;
- `density`: information fits the available space; split the figure if that is clearly better;
- `composition`: visual weight and empty space look deliberate rather than accidental auto-layout;
- `pencil_fidelity`: the figure itself visibly reads as hand-drawn notebook ink/pencil at final size. Boxes, arrows, dividers and geometric forms must have perceptible stroke wander/overdraw and must **not** read as ruler-straight diagram-editor vectors merely placed on notebook paper;
- `pedagogical_value`: the visual makes understanding easier than prose alone by encoding useful structure, mechanism, relationship, state, flow, comparison or spatial intuition rather than merely decorating text;
- `responsive`: both wide and narrow compositions work independently, with no mobile zoom dependency;
- `academic_fidelity`: every visual assertion preserves canonical meaning and analogies are not presented as source truth.

For `pedagogical_value`, specifically inspect whether the drawing itself carries explanatory work. When a scene is mostly a grid/row of titled boxes whose contents are short prose paraphrases, ask whether replacing the entire figure with those labels as ordinary text would lose meaningful understanding. If the answer is no **and** the supported concept offered a real graphical opportunity (mechanism, internal parts, flow, state change, relationship, hierarchy, spatial contrast or useful micro-example), score `pedagogical_value <= 3`, which prevents PASS. Prefer scenes where the learner can *see* the distinction or mechanism.

Do **not** penalize boxes merely for being boxes. Containers are appropriate when boundaries, grouping, architecture, memory regions, layers or containment are themselves part of the concept, and a genuinely simple concept may deserve a genuinely simple figure. Never demand extra visual detail that is not supported by provenance.

PASS requires every score >= 4 and no `blocking` or `major` issue.

Hard fail a V2 scene for any of the following:
- unreadable text or clipping;
- any semantic shape/container that visibly renders empty or unexplained;
- visible crowding or elements stuck together without deliberate meaning;
- ambiguous connection origin/destination;
- arrow/path through text, through its own label, or through unrelated semantic content;
- missing or invented academic relationship;
- mobile/narrow figure that only works by shrinking the wide scene or requiring zoom;
- pencil treatment effectively invisible at final size;
- geometric boxes/arrows/lines that still look mechanically perfect, ruler-straight or like clean diagram-editor SVG rather than drawn strokes;
- missing element-level provenance;
- reviewed screenshot missing or changed;
- reviewed scene/spec/asset hash differs from the finalized one;
- `vision_verified != true`;
- reviewer does not explicitly declare `capability: vision` and `independent: true`.

A model without image input can never emit visual PASS. Structural metrics may be PASS while perceptual inspection remains `UNVERIFIED`; the overall visual state is incomplete until a vision-capable reviewer actually inspects both PNGs.

## Review economy
The vision gate is strict but narrow. Give the reviewer only the current screenshots, scene spec, pedagogical objective/provenance and this rubric. Do not load unrelated repository/course context.

If a scene already passed and its normalized scene SHA plus both PNG SHA-256 values are unchanged, that PASS remains valid within the same run. Carry the exact prior row forward mechanically. Do **not** spend another vision call re-inspecting byte-identical evidence. On a repair cycle, inspect only changed/failed scenes.

## General hard failures
- broken image paths in the published artifact;
- any rendered image fails to decode (`complete != true`, `naturalWidth == 0` or `naturalHeight == 0`);
- unreadable/missing alt text for an essential figure;
- a derived figure changes academic meaning, drops meaningful relations or invents unsupported content;
- `02-plan.json` says `reinterpret` but the final artifact omits the reviewed derived asset or substitutes its source asset;
- a `preserve` decision lacks `fidelity_reason`, or `preserve+derived_sketch` omits either member;
- a derived sketch carries opaque paper/background pixels instead of using the document's real notebook surface;
- a rendered artifact is published without a successful browser audit;
- the final response claims visual PASS without actual rendered screenshot evidence.

## Rendered-browser evidence
Legacy/non-scene artifacts use `scripts/visual_audit.py`. Artifacts containing V2 responsive scenes use `scripts/visual_audit_v2.py`, which runs the normal document audit and also writes desktop/mobile crops for every scene under `visual-audit/figures/`.

The browser auditor must force images to load/decode, reject horizontal content overflow and require the complete Playwright/Chromium environment. HTML-string, registry and path checks are integrity evidence, not substitutes for visual inspection.

Inspect at least desktop and mobile document screenshots for hierarchy/integration. For V2, also inspect every per-scene desktop/mobile crop because the physical notebook reader can hide figures on inactive leaves. This final audit checks integration; it does not reopen already hash-bound figure review unless the final browser render introduces a new visible defect.

## Design-system fidelity
- student Markdown expresses semantic roles, never local styling;
- no inline colors, custom HTML cards or per-course visual inventions;
- the normal page remains a Carpeta university-study notebook rather than a dashboard;
- canonical ruled paper/binding cues are intentional product grammar;
- visual novelty must not compete with the concept hierarchy.
