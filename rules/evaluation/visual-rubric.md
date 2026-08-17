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
- `pencil_fidelity`: the notebook/pencil language is perceptible at final display size without becoming cartoonish;
- `pedagogical_value`: the visual makes understanding easier than prose alone;
- `responsive`: both wide and narrow compositions work independently, with no mobile zoom dependency;
- `academic_fidelity`: every visual assertion preserves canonical meaning and analogies are not presented as source truth.

PASS requires every score >= 4 and no `blocking` or `major` issue.

Hard fail a V2 scene for any of the following:
- unreadable text or clipping;
- visible crowding or elements stuck together without deliberate meaning;
- ambiguous connection origin/destination;
- arrow/path through text or unrelated semantic content;
- missing or invented academic relationship;
- mobile/narrow figure that only works by shrinking the wide scene or requiring zoom;
- pencil treatment effectively invisible at final size;
- missing element-level provenance;
- reviewed screenshot missing or changed;
- reviewed scene/spec/asset hash differs from the finalized one;
- `vision_verified != true`;
- reviewer does not explicitly declare `capability: vision` and `independent: true`.

A model without image input can never emit visual PASS. Structural metrics may be PASS while perceptual inspection remains `UNVERIFIED`; the overall visual state is incomplete until a vision-capable reviewer actually inspects both PNGs.

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

Inspect at least desktop and mobile document screenshots for hierarchy/integration. For V2, also inspect every per-scene desktop/mobile crop because the physical notebook reader can hide figures on inactive leaves.

## Design-system fidelity
- student Markdown expresses semantic roles, never local styling;
- no inline colors, custom HTML cards or per-course visual inventions;
- the normal page remains a Carpeta university-study notebook rather than a dashboard;
- canonical ruled paper/binding cues are intentional product grammar;
- visual novelty must not compete with the concept hierarchy.
