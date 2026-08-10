# Changelog

## V3.7.2

Reviewer académico adversarial y contrato de fidelidad reforzado.

- `academic_fidelity` pasa a ser un score obligatorio del gate.
- `05-review.json` / `07-review.json` incorporan `fidelity_checks` y `claim_checks` estructurados.
- El reviewer contrasta claims de alto riesgo contra el canonical y realiza una segunda pasada candidato-vs-candidato.
- El gate falla ante claims no soportados, drift interno o cualquier issue académico/pedagógico/visual aunque `pass: true`.
- `artifact_contract_version = 7` fuerza regeneración de artefactos pedagógicos viejos sin reprocesar las fuentes.
- Se agregó una prueba de reproducibilidad exacta del theme generado.
- Suite de build: 86 tests passing + 1 MCP stdio E2E skipped donde el SDK opcional no estaba instalado.

## V3.7.1

Corrección de la primera prueba real del MCP.

- Se eliminaron subprocesses Python del service MCP: las tools llaman directamente al core determinístico in-process.
- `study_list_artifacts`, `study_validate_artifact`, `study_mark_artifact`, `study_verify_figures`, `study_register_derived_figure` y `study_validate_course` dejan de depender de procesos hijos.
- Se agregó un test MCP end-to-end real por `stdio` con timeout.
- El E2E fue verificado en Windows con las 12 tools respondiendo sin hangs.

## V3.7.0

Primera integración MCP local sobre el mismo core de `study.py`.

- Servidor local por `stdio`, sin HTTP ni puerto.
- 12 tools curadas y 4 resources `study://...`.
- Contexto grueso por materia/unidad, progreso, figuras y artefactos.
- Mutaciones limitadas a operaciones seguras; sin borrado, reset ni edición JSON arbitraria.
- Fallback completo a CLI/scripts cuando MCP no está disponible.
