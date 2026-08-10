# Conocimiento de la materia

`concepts.json` es el grafo conceptual persistente. El agente lo actualiza durante INGEST, LEARN, RECALL y AUDIT.

Cada concepto puede guardar definición, explicación, prerrequisitos, relaciones, fuentes, ejemplos, trampas, errores recurrentes y relevancia para evaluación. El dominio numérico y las fechas de repaso viven únicamente en `../progreso/progress.json` para evitar duplicar estado.
