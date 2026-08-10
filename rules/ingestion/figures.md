# Figure ingestion

Figures are part of the source model.

## Deterministic preparation
Before attempting PDF scanning, run `python study.py figures preflight <course>`. Only when it reports `READY` and PDFs are new/changed run:
`python study.py figures scan <course> --write`

A missing PyMuPDF capability is a declared disabled feature, not a failed ingestion step.

The scanner records PDF pages with raster images/vector drawings and text density in `.study/figure-pages.json`. This step is deterministic and does not decide academic importance.

## Semantic figure registry
During ingestion, create/update
`unidades/<unit-id>/conocimiento/figures.json` only for visuals worth
referencing later. A figure record may contain:
- `id`;
- stable `unit_id` plus optional human-readable `unit` / related concept ids;
- `source_file` and 1-based `page`;
- `kind`: diagram, table, chart, screenshot, illustration, other;
- `role`: essential, supporting, ignore;
- `description`: what the visual actually represents;
- `learner_focus`: the relationships/components a learner should notice;
- `source_sha256`;
- optional `asset` path if already rendered;
- `origin`: source or derived.

Do not register every image object in a PDF. Register pedagogically meaningful visuals.

## Rendering source figures
Render only selected pages/figures, not every PDF page:
`python scripts/figure_assets.py render-page --course <course> --file "oficiales/foo.pdf" --page 3 --id u2-memory-hierarchy`

The resulting image belongs under `assets/figures/` inside the course and its path should be stored in the figure registry.

If PyMuPDF is unavailable, do not fabricate a figure. Continue text processing and report the optional visual capability as unavailable.
