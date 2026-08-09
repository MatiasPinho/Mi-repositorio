# V3.6.4

Corrección de migración del registro de figuras detectada al probar Programación I real.

- Las figuras `origin: source` pueden tener `asset: null`: significa que la figura está registrada pero todavía no fue extraída/renderizada desde el PDF.
- Los assets nulos no participan en detección de colisiones.
- Las figuras `origin: derived` siguen requiriendo asset real, `unit_id`, namespace `derived:` y `based_on`.
- Una migración fallida de V3.6.3 puede repetirse de forma segura porque abortaba antes de escribir `figures.json`.
- La suite de release contiene 70 tests.
