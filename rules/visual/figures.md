# Figures, diagrams and source visuals

A figure is pedagogical content, not decoration.

## Core rule
Use a visual when it makes a spatial, structural, causal, temporal or relational concept easier to understand than prose alone. This is especially important in subjects such as computer architecture, operating systems, networking, databases, electronics, algorithms and mathematics.

Good candidates include:
- architecture/block diagrams;
- process/state diagrams;
- memory maps and hierarchies;
- timelines and scheduling diagrams;
- flowcharts;
- tables whose structure carries meaning;
- annotated screenshots when the interface itself is being learned;
- graphs, geometric figures and circuit diagrams.

Do **not** include:
- decorative illustrations;
- logos and cover art;
- screenshots that add no instructional information;
- duplicate visuals that say the same thing;
- a dense page image when a clearer source figure or small schematic is available.

## Source-first policy
Prefer a relevant figure from the unit sources when it faithfully represents what the chair teaches. Preserve provenance internally in `unidades/<unit-id>/conocimiento/figures.json`.

If a source figure is too dense but the concept would benefit from a simpler schematic, a simplified diagram may be created only if every relationship shown is supported by canonical knowledge. Mark its origin as `derived` internally; never imply that a derived diagram came from the chair.

## Selection during PLAN
For every major concept, explicitly decide one of:
- `visual_required`: prose alone would be a poor teaching choice;
- `visual_helpful`: visual adds clear value;
- `visual_not_needed`: prose/example is better.

Do not force a fixed number of figures.

## Placement
Corresponding words and images belong together. Put the figure immediately after the paragraph that introduces it, followed by a short **How to read this figure** explanation when needed.

A useful figure block has:
1. a meaningful alt text/caption;
2. the visual;
3. 1–4 sentences telling the learner what relationship to notice;
4. optionally one recall prompt that asks the learner to reconstruct/explain the visual.

Do not describe every pixel. Explain the conceptual relationship the student should extract.

## Truth boundary
Never infer unlabeled components from an unreadable image. If the agent cannot confidently inspect or interpret a source visual, either omit it or state that visual interpretation is unavailable and use supported prose instead.


## On-demand discovery for migrated/older courses
If `unidades/<unit-id>/conocimiento/figures.json` has no relevant entry for the requested scope, do **not** reprocess the whole course. Instead:
1. run `python study.py figures scan <course> --write` if `.study/figure-pages.json` is missing/stale and the visual dependency is available;
2. use concept source references to identify candidate PDF pages for the requested scope;
3. inspect only those candidate pages/figures;
4. register/render only visuals that pass the pedagogical selection rule.

This is a narrow visual-indexing pass, not a reason to reread all transcripts or regenerate canonical text knowledge.


## Stable identity and derived registration
Unit matching is machine based. Use the resolved `unit_id` from `01-input.json`; do not compare strings such as `U1` and `Unidad 1` manually.

When creating a new diagram, save the asset under `assets/figures/` and register it with `python study.py figures register-derived ...`. Derived ids are automatically namespaced `derived:` and registration refuses id/asset collisions. Never directly overwrite a record whose origin is `source`.
