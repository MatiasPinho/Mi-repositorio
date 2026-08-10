# Visual learning rationale (design reference, not runtime prompt)

This file explains why the shipped study renderer uses its defaults. Agents should load the short operational rules under `rules/visual/` instead of this bibliography-heavy note.

## Main design decisions

### Words + relevant pictures
The multimedia-learning literature associated with Richard Mayer finds that learners often understand and transfer material better when relevant pictures are combined with words than when words are used alone. This does **not** justify decorative imagery: the coherence principle favors removing extraneous material.

### Keep figure and explanation together
The spatial-contiguity principle supports placing corresponding words and pictures near each other. The renderer/pipeline therefore puts figures inside the concept section they explain, not in a detached gallery or appendix.

### Signaling, not rainbow decoration
Signaling/cueing research supports highlighting the organization or relevant elements of instructional material. Color therefore has a stable semantic meaning (definition/example/warning/etc.) instead of being applied decoratively.

### Readability
W3C WCAG guidance motivates high contrast, meaningful heading hierarchy, non-justified blocks, resizeability and controlled line length. The shipped theme uses a single reading column, approximately 19px body text, 1.72 screen line-height and semantic callouts. Exact typography is a sensible default rather than a universal cognitive optimum.

### Highlighting is not studying
Dunlosky and colleagues' review rates practice testing and distributed practice much more strongly than highlighting/underlining alone. For that reason, visual emphasis is sparse and student artifacts add occasional retrieval prompts rather than turning every key phrase into colored highlighting.

## References
- Mayer, R. E., *Multimedia Learning* and chapters on the Multimedia, Coherence, Signaling and Spatial Contiguity principles.
- Mayer, R. E. & Fiorella, L. (eds.), *The Cambridge Handbook of Multimedia Learning*.
- Schneider, S., Beege, M., Nebel, S., & Rey, G. D. (2018). A meta-analysis of how signaling affects learning with media. *Educational Research Review*, 23, 1–24.
- Beege, M., Nebel, S., Schneider, S., & Rey, G. D. (2021). The effect of signaling in dependence on extraneous cognitive load in learning environments. *Cognitive Processing*, 22, 209–225.
- Rello, L., Pielot, M., & Marcos, M.-C. (2016). Make It Big! The Effect of Font Size and Line Spacing on Online Readability. CHI 2016.
- Dunlosky, J. et al. (2013). Improving Students' Learning With Effective Learning Techniques / Strengthening the Student Toolbox.
- W3C Web Content Accessibility Guidelines (WCAG) 2.2 and WAI writing/headings guidance.
