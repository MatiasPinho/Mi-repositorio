# Browser Quiz

`quiz` genera un multiple choice persistente de una unidad procesada para resolver directamente en el navegador.

## Frontera con otras acciones

- `preguntas`: active recall conversacional, una pregunta por vez, con actualización de progreso cuando existe evidencia significativa.
- `quiz`: artefacto HTML offline/autocontenido; las respuestas viven sólo en la sesión del navegador y no modifican `progress.json`.
- `simulacro`: evaluación ligada a un assessment registrado y a su alcance confirmado/probable.

## Uso

```text
Claude: /quiz programacion-1 unidad-3
Codex:  $quiz programacion-1 unidad-3
```

Cantidad opcional:

```text
$quiz programacion-1 unidad-3 25
```

El valor por defecto es 15 y el contrato admite entre 1 y 50 preguntas.

## Artefactos

```text
unidades/<unit-id>/
├── preguntas/
│   ├── <unit-id>-quiz.html
│   └── _source/
│       └── <unit-id>-quiz.json
└── .study/runs/<timestamp>-quiz/
    ├── 01-input.json
    ├── 02-quiz.json
    ├── 03-review.json
    ├── 04-final.json
    ├── 09-rendered.html
    ├── 10-integrity.json
    ├── 11-publication.json
    └── visual-audit/
```

El JSON es la fuente semántica. El HTML es una derivación determinística y autocontenida.

## Contrato de pregunta

Cada pregunta tiene:

- `id` estable dentro del quiz;
- `topic_id` observado, o `null` sólo para conceptos explícitamente unassigned;
- `concept_ids` canónicos de la misma unidad;
- `difficulty`: `basic`, `intermediate` o `advanced`;
- `prompt`;
- `code` opcional para ejercicios de programación;
- exactamente cuatro opciones `a|b|c|d`;
- exactamente un `correct_option_id`;
- feedback breve para cada opción.

`scripts/quiz_artifact.py` rechaza referencias a conceptos inexistentes, asignaciones concepto↔tema inválidas, IDs/opciones duplicadas, meta-opciones como “todas/ninguna de las anteriores” y HTML que no preserve el mismo JSON de origen.

## Calidad semántica

`rules/evaluation/multiple-choice.md` exige una revisión independiente de:

- fidelidad canónica;
- una única mejor respuesta defendible;
- distractores plausibles y específicamente incorrectos;
- ausencia de pistas por longitud/gramática/posición;
- feedback útil;
- cobertura temática flexible.

Los temas observados son guardrails de cobertura, no cuotas ni pesos de examen.

## Modos del HTML

### Práctica

La respuesta se corrige al presionar **Comprobar**. El usuario recibe feedback inmediato y puede continuar.

### Examen

No se muestra corrección durante la resolución. Al finalizar aparecen:

- porcentaje total;
- correctas/total;
- desglose por tema;
- revisión pregunta por pregunta.

Ambos modos funcionan sin servidor ni conexión de red.

## Seguridad y progreso

Un HTML offline necesita contener las respuestas correctas internamente para poder corregir con JavaScript. Por eso `quiz` es una herramienta de estudio, no un entorno de examen seguro/proctorizado.

V1 no intenta escribir archivos desde el navegador ni actualizar mastery de manera implícita. Si más adelante se integra progreso, debe hacerse mediante un resultado exportable/importable con contrato explícito y validación del lado del sistema.

## Gates

Antes de publicar:

1. validación estructural/canónica del JSON;
2. review MCQ independiente ligado por SHA-256 al candidato;
3. render determinístico;
4. integrity check JSON↔HTML;
5. Chromium visual audit + screenshots desktop/mobile;
6. publicación atómica exacta de JSON/HTML;
7. revalidación de academic/concepts/topics/figures y engine snapshot al cerrar el run.

Reejecutar `quiz` reemplaza atómicamente el quiz actual de esa unidad; no acumula bancos aleatorios obsoletos por defecto.
