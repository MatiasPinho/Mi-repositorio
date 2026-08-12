# Engine QA reports

Este directorio es el **outbox versionable** de Engine QA Lab.

Los runs completos viven localmente en `.study/engine-qa/` y las materias sintéticas en `materias/qa-engine-*`; ambos son estado efímero. Cuando un run encuentra fallos confirmados, `engine_qa.py finish --export` copia aquí únicamente un paquete compacto y seguro:

```text
qa/reports/<run-id>/
├── report.md
├── report.json
├── replay.json
└── findings/
```

La skill interna `engine-qa` puede publicar ese único directorio en un draft PR `Engine QA findings <run-id>`. No deben incluirse materias reales, el workspace QA completo ni modificaciones del engine en esos PRs.

Los reportes son evidencia de descubrimiento, no tests permanentes. Después de corregir un finding, la reproducción mínima debe convertirse en una regresión determinística dentro de `tests/` o del benchmark correspondiente.