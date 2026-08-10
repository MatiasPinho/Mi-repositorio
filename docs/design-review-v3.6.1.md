# Design review V3.6.1 — reference fidelity

V3.6 captured the external redesign's CSS vocabulary but not all of its semantic HTML grammar. Comparison against the user-supplied Claude screenshots showed that this changed the perceived design even though the tokens and most CSS were identical.

Corrections:
- chapter lede is part of the opening header;
- the opening gutter says `Capítulo N` while the running line preserves the real academic `Unidad N`;
- callout gutter text represents semantic role, never the arbitrary Markdown title;
- definition and connection terms can sit inside the body;
- recall uses the stable `Recuperación` apparatus with a visible prompt + hint;
- code/table captions use the same gutter grammar as figures;
- guide index appears for the three-section reference case.

The user-supplied screenshots and the exported Claude prototype are treated as the visual source of truth for this patch. The goal is structural fidelity, not reinterpretation.
