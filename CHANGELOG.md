# V4.0.0

- Agrega `unidades/<unit-id>/conocimiento/topics.json` como catálogo canónico
  de temas observados, separado de `academic.json -> units[].topics` y de los
  conceptos.
- Incorpora reconciliación con IDs estables, asignación principal única o
  `unassigned_concept_ids`, `declared_matches` validados y evidencia semántica.
- `study_get_unit_context`, `/resumen`, `/preguntas`, `/simulacro` y `/estado`
  consumen temas observados sin fijar secciones, longitud, cantidad de preguntas
  ni duplicar mastery.
- `artifact_contract_version = 9`: cambios en temas observados invalidan los
  artefactos derivados de esa unidad.
- Acota el fingerprint temático a IDs, nombres y asignaciones que afectan la
  cobertura generada; aliases, evidencia y `declared_matches` ya no provocan
  staleness por sí solos.
- Hace explícita la cobertura del dominio derivado: una media parcial se expone
  como `tracked_mastery_average`, y `average_mastery` sólo tiene valor cuando
  todos los conceptos del tema tienen progreso.

- Introduce `materias/<course>/unidades/<unit-id>/` como límite canónico para
  fuentes pedagógicas, conocimiento, figuras, progreso, notas, artefactos,
  assets y ejecuciones.
- Agrega `study.py units list|sync|migrate`, migración V3 collision-safe y copia
  de recuperación en `.study/legacy-layout-v3/`.
- CLI, MCP y pipelines resuelven primero un `unit_id`; MCP suma
  `study_list_units` y rutas canónicas en `study_get_unit_context`.
- `artifact_contract_version = 9`: un artefacto de unidad fuera de su directorio
  canónico es inválido, los cambios de temas lo vuelven stale y los artefactos
  V3 quedan stale.
- Corrige el cierre de pipelines V4 para validar la publicación dentro de
  `unidades/<unit-id>/resumenes/`, conservando compatibilidad con materias V3.
- Migra `programacion-1` a nueve unidades sin reprocesar fuentes.

# V3.7.2

Reviewer académico adversarial y contrato de fidelidad reforzado.

- `academic_fidelity` pasa a ser un score obligatorio del gate, no sólo una descripción de rúbrica.
- `05-review.json`/`07-review.json` deben auditar explícitamente definiciones/taxonomías, condiciones, relaciones/orden, certeza/conflictos, reglas de evaluación, consistencia interna y separación de ejemplos.
- El reviewer debe contrastar afirmaciones de alto riesgo contra el estado canónico y luego hacer una segunda pasada candidato-vs-candidato para detectar drift interno (por ejemplo, una taxonomía de 4 elementos que reaparece como 5).
- El gate falla ante claims no soportados o ante cualquier issue académico, pedagógico o visual registrado, aunque `pass: true` o los scores sean altos.
- `artifact_contract_version = 7`: artefactos pedagógicos anteriores quedan stale y se regeneran sin reprocesar las fuentes.
- `assets/study-theme.css` vuelve a compilarse exclusivamente desde `design/`; se agregó una prueba de reproducibilidad exacta para evitar residuos de tests.
- Release suite en el entorno de build: 86 tests passing + 1 MCP stdio E2E skipped por ausencia del SDK opcional; el mismo E2E está incluido para ejecutarse donde `mcp` esté instalado.

# V3.7.0

Primera integración MCP local del sistema, manteniendo `study.py` y los scripts determinísticos como core.

- Nuevo servidor `study_mcp/` por `stdio`, sin API HTTP ni puerto local.
- 12 tools curadas: contexto de materias/unidades, progreso, figuras, artefactos, validación y dos escrituras seguras (`register_derived_figure`, `mark_artifact`).
- 4 resources `study://...` para contexto reusable.
- `study_get_unit_context` agrega en una sola llamada unidad estable, conceptos, figuras, restricciones académicas y progreso para reducir lectura repetida de JSONs.
- Las mutaciones MCP delegan en `figure_assets.py` y `artifact_state.py`; el adapter no edita registries académicos directamente.
- `.mcp.json` (Claude Code) y `.codex/config.toml` (Codex) arrancan `python study.py mcp serve` con UTF-8 forzado.
- `python study.py mcp preflight [--json]` valida la dependencia opcional del SDK.
- MCP V1 no expone borrado, reset, escritura JSON arbitraria ni publicación libre.
- Pipelines y router prefieren llamadas MCP gruesas cuando están disponibles y conservan fallback completo a CLI/scripts.
- SDK fijado a `mcp>=1.28,<2` por compatibilidad actual de stdio entre Claude Code y Codex.
- Release suite: 79/79 tests passing.

# V3.6.5

Correcciones detectadas en la primera corrida completa de Codex sobre V3.6.4.

- CLI robusta en Windows: `study.py` fuerza UTF-8 en stdout/stderr y en subprocesses determinísticos.
- `materials scan --json` emite exclusivamente un documento JSON, sin narración humana ni mensajes de commit mezclados.
- El tooling visual redirige cualquier salida accidental de PyMuPDF/dependencias a stderr para proteger los contratos JSON.
- El pipeline `procesar` pide explícitamente las variantes `--json` de scan/preflight visual cuando consume estructura.
- Los títulos específicos de todos los callouts se preservan en el cuerpo: la categoría permanece en el gutter y el título académico ya no se pierde en WARNING, EXAM, RECALL o EXAMPLE.
- Release suite: 73/73 tests passing.

# 3.6.4 — Figure registry migration fix

- Fixed legacy figure migration when source figures are registered before PDF assets are rendered.
- `origin: source` figures may validly have `asset: null`; this now means pending extraction instead of a broken asset.
- Null assets are excluded from collision detection, preventing false `asset-collision` errors between source figures.
- Derived figures still require a real asset, a `derived:` namespaced id and explicit provenance.
- Failed V3.6.3 migrations can be safely rerun; they aborted before writing the registry.
- Added regression coverage for the exact mixed registry case: multiple source figures with null assets plus legacy derived figures.
- Release suite: 70/70 tests passing.

# 3.6.3 — Pipeline integrity hardening

- Added stable machine `unit_id` resolution (`U1`, `Unidad 1` and titled aliases resolve to `unidad-1`) for concept/figure artifact scoping.
- Added collision-safe derived figure registration with mandatory `derived:` namespace, provenance (`based_on`) and asset ownership checks.
- Added deterministic `artifact_integrity.py` gate before publication: captions, image paths/alt text, registered figures, stable unit scope and registry integrity must pass.
- Renderer now accepts blank lines between a table/code block and its caption metadata, while orphan captions fail `--check`.
- Pipeline runs now require `10-integrity.json` with `ok: true` and reject persistent ad-hoc repair scripts created in the course tree. Temporary helpers belong under the run directory only.
- Added visual capability preflight. Missing PyMuPDF is reported as `DISABLED` without attempting/failing optional PDF scanning.
- `/procesar`, `/resumen`, `/guia` and `/repaso` contracts updated so agents use deterministic tooling instead of creating repair scripts such as `fix_unit_scope.py`.
- Legacy derived figure registries can be migrated in-place with `python study.py figures migrate <course>`; no source reprocessing is required.
- Release suite: 67/67 tests passing.

# 3.6.2 — Course reset command

- Added `python study.py course reset <course>` and interactive menu option 13.
- Reset preserves the complete `fuentes/` tree and the course's basic identity, but rebuilds processed/derived course state from the clean template.
- Clears academic derived content, concept/figure knowledge, notes, progress, summaries/guides/reviews, questions, mock exams, generated figure assets and `.study/` caches/runs/indexes.
- Interactive reset requires typing the exact course slug; `--yes` is available for intentional automation.
- Removing `.study/materials-index.json` means all preserved sources are detected as new on the next processing pass.
- Added regression tests covering source preservation, identity preservation, full processed-state cleanup, material re-detection and cancellation safety.
- Release suite: 60/60 tests passing.

# 3.6.1 — Reference fidelity patch

- Corrected the integration after comparing the generated V3.6 pages against the original Claude Design screenshots and exported prototype.
- The first lede now stays inside the chapter opening under the H1, matching the reference composition.
- `Unidad N` remains in the running line but is presented editorially as `Capítulo N` in the opening gutter.
- Semantic gutter labels are now stable roles (`Definición`, `Ejemplo`, `Cuidado`, `Error típico`, `Relación`, `Recuperación`) instead of arbitrary callout titles.
- Definition/connection concept names move into the reading column as terms when useful.
- Recall blocks now render the semantic `Recuperación` label, visible prompt and quiet hint.
- Optional portable caption metadata (`<!-- caption: ... -->`) now produces textbook captions for code and tables; pseudocode is numbered.
- Long guides show the quiet right-side index/progress treatment from three major sections onward, matching the supplied Systems Operating reference.
- The three design stress samples were aligned with the actual Claude reference content so visual comparisons are meaningful.
- 58 release tests covered and passing across actions, pipeline, artifacts, system, CLI and visual renderer tests.

# 3.6.0 — Claude Design integration

- Integrated the external Claude Design proposal as the new canonical study surface rather than copying its preview HTML verbatim.
- New **contemporary technical manual** composition: 8rem semantic/number gutter + 42rem prose measure + 52rem technical width.
- Source Serif 4 + IBM Plex Sans/Mono are optional Google Fonts enhancements with complete system fallbacks for offline readability.
- Renderer now emits gutter/body rows, numbered H2 sections, semantic callout bodies, figure plates and split numbered captions.
- Recall prompts are visible by default instead of hidden in disclosure widgets.
- Long guides can show a 2px reading-progress indicator together with the quiet editorial TOC.
- Mobile collapses gutter metadata above content while preserving linear reading order; summaries remain free of sidebar chrome.
- Visual audit no longer blocks on external font loading and still captures desktop/tablet/mobile/A4 print.
- Design source, rules and portable Claude/Codex skills were updated to describe the actual rendered contract.

# 3.5.0 — Modern academic book

- Chapter-style front matter: course, artifact type, unit/scope and title form a textbook opening.
- Renderer accepts `--course` and `--scope`; repeated unit prefixes are stripped from the visible H1.
- H2/H3 hierarchy is more book-like: whitespace and serif typography replace interface-like top rules.
- Tables now use serif reading cells + compact utility headers; code blocks switch from dark editor slabs to light textbook treatment.
- Figures lose unnecessary borders and captions use `Figura N.` notation.
- Print requests page folios through CSS paged-media margin boxes where supported.
- Book feel is explicitly defined as hierarchy/rhythm/measure, never faux paper textures or ornamental cosplay.

# 3.4.0 — Editorial refinement

- Summary, review, learn and explain artifacts now render as a centered paper with no sidebar; only long guides receive the quiet editorial TOC.
- Reading measure and paper width are separate: prose stays around 64ch while figures, tables and code can use the wider page.
- Figures are numbered automatically in captions.
- Tables use a dedicated overflow wrapper, tabular numerals and quieter manual-like rules.
- Kicker/header chrome was reduced further.
- Microtypography and vertical rhythm were tightened for long reading sessions without dropping below 1.5 line-height.

# Changelog

## 3.3
- Dirección visual refinada a **academic paper reader**: papel cálido, tinta oscura y una sola columna de lectura dominante.
- Se eliminan degradados de callouts, sombras de hoja, fondos de tarjetas y chrome innecesario.
- Cuerpo serif de lectura larga; sans-serif queda para labels/TOC. Títulos menos heroicos y más editoriales.
- Color semántico mucho más desaturado; los callouts son normalmente transparentes con una línea marginal fina.
- Figuras ganan protagonismo relativo al reducir UI alrededor.
- El tema claro/papel es siempre el default; dark mode queda como opt-in explícito (`data-study-theme="dark"`).
- Reviewer visual falla texturas falsas de papel, grain, stickers, sombras fuertes y cualquier diseño que se note antes que la prosa.
- El cambio visual invalida sólo artefactos visuales mediante `design_sha256`; el artifact contract sigue en v6 para no regenerar preguntas/simulacros.

## 3.2
- Design system separado de la generación académica: `design/*.css` es la fuente de verdad y `assets/study-theme.css` se genera de forma determinística.
- Nueva dirección visual **technical editorial notebook**: columna de lectura dominante, navegación discreta y rails semánticos en lugar de card soup.
- `frontend-design` oficial de Anthropic vendorizada bajo Apache-2.0 para trabajo de diseño, no para cada resumen.
- Nuevas skills portables `study-design` y `study-design-reviewer`, sincronizadas a Claude Code y Codex.
- Stress tests visuales para teoría, arquitectura/diagramas y sistemas operativos/tablas.
- `scripts/visual_audit.py` captura desktop, tablet, mobile y A4 print y ejecuta checks mecánicos de overflow/contraste/tipografía.
- El design system usa tokens de tipografía, spacing, color semántico y layout; no se permite styling ad-hoc por materia.
- Artifact contract v6; los HTML de resumen/guía/repaso incluyen `design_sha256` y quedan STALE si cambia el design system. Preguntas/simulacros no se invalidan por cambios visuales.
- Documentación de investigación y review visual en `docs/design-research.md` y `docs/design-review-v3.2.md`.

## 3.1
- HTML pasa a ser la superficie principal de lectura para resumen/guía/repaso; Markdown queda como fuente portable.
- Sistema visual evidence-informed: jerarquía tipográfica, ancho de lectura, interlineado, alto contraste, modo oscuro e impresión/PDF desde navegador.
- Colores semánticos estables y callouts para definición, ejemplo, advertencia, examen, conexión y recall.
- Reglas explícitas contra subrayado/coloreado decorativo y contra paredes de callouts.
- Soporte pedagógico de figuras: registro `conocimiento/figures.json`, scanner de páginas visuales y render local de páginas/crops PDF con PyMuPDF opcional.
- Plan pedagógico decide por concepto `visual_required`, `visual_helpful` o `visual_not_needed`.
- Figuras fuente se colocan junto a la explicación y deben indicar qué relación mirar.
- On-demand visual discovery para materias migradas sin reprocesar transcripciones completas.
- Quality gate incorpora `visual_support` y detecta assets rotos/visuales no verificables.
- Artifact contract v5 incluye fingerprint visual por scope.
- CLI: `study.py figures ...` y `study.py open ...`.
- 49 tests de release + smoke real PDF → figura → Markdown → HTML.
