# Evals — no optimizar por intuición

La infraestructura V3 sólo se conserva si mejora resultados medibles.

## Benchmark principal de resumen

Comparar para el mismo conjunto de fuentes y alcance:

- **Baseline:** modelo + fuentes + una instrucción simple del tipo “haceme un buen resumen para estudiar esta unidad”.
- **Candidate:** salida de `resumen` de V3.

El evaluador debe recibir A/B anonimizados, el conocimiento canónico necesario y `summary-rubric.json`. No debe saber cuál es V3 antes de puntuar.

Criterios de éxito:
- V3 no puede perder fidelidad académica.
- V3 debe ganar o empatar claramente en claridad, progresión, explicación, señal/ruido, naturalidad y cobertura.
- Si una etapa nueva no mejora el benchmark de forma repetible, se elimina.

Guardar casos reales por materia/unidad cuando se quiera hacer regresión cualitativa. No reemplazar tests determinísticos con evals; se complementan.
