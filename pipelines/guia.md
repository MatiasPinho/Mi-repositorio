# Internal compatibility pipeline: guia

`guia` is no longer a public action.

Legacy intent that asks for a guide, exhaustive guide, dossier, or similarly detailed study document must route to `pipelines/resumen.md` with **detailed depth**. Do not start a `guia` run, publish a `*-guia.html` artifact, or maintain a second long-form document type.

This wrapper exists only so old references fail safely into the canonical `resumen` pipeline instead of duplicating methodology. Public adapters must not expose `guia`.
