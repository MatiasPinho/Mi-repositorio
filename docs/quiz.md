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
    ├── 04-final.json                    # si review 1 pasa
    ├── 04-repair.json                   # sólo si review 1 falla
    ├── 05-review.json                   # sólo sobre 04-repair
    ├── 06-final.json                    # sólo si review 2 pasa
    ├── 09-rendered.html
    ├── 10-integrity.json
    ├── 10-interaction.json
    ├── interaction-audit/
    │   ├── practice-feedback.png
    │   ├── exam-question-mobile.png
    │   └── exam-result-mobile.png
    ├── visual-audit/
    │   ├── audit.json
    │   ├── desktop.png
    │   └── mobile.png
    └── 11-publication.json
```

El JSON es la fuente semántica. El HTML es una derivación determinística y autocontenida. El candidato rechazado y su review nunca se reescriben: hay como máximo una reparación separada y un segundo review.

## Contrato de pregunta

Cada pregunta tiene:

- `id` estable dentro del quiz;
- `topic_id` como tema primario para cobertura/resultados; puede ser `null` cuando al menos un concepto objetivo está explícitamente unassigned;
- `concept_ids` canónicos de la misma unidad;
- una pregunta integradora puede combinar conceptos de distintos temas siempre que `topic_id` esté representado por al menos uno de ellos;
- `difficulty`: `basic`, `intermediate` o `advanced`;
- `prompt`;
- `code` opcional para ejercicios de programación;
- exactamente cuatro opciones `a|b|c|d`;
- exactamente un `correct_option_id`;
- feedback breve para cada opción.

`scripts/quiz_artifact.py` rechaza referencias a conceptos inexistentes, un tema primario que no esté representado por los conceptos objetivo, IDs/opciones duplicadas, meta-opciones como “todas/ninguna de las anteriores” y HTML que no preserve el mismo JSON de origen.

## Calidad semántica

`rules/evaluation/multiple-choice.md` exige una revisión independiente de:

- fidelidad canónica;
- una única mejor respuesta defendible;
- distractores plausibles y específicamente incorrectos;
- ausencia de pistas por longitud/gramática/posición;
- feedback útil;
- cobertura temática flexible.

Los temas observados son guardrails de cobertura, no cuotas ni pesos de examen. En preguntas integradoras, el resultado por tema usa el `topic_id` primario para no contar una misma pregunta varias veces.

El review queda ligado por SHA-256 al candidato evaluado. Si el primer review falla, sus issues/checks se conservan como evidencia; el motor sólo permite `04-repair.json → 05-review.json → 06-final.json`. No existe un tercer ciclo.

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
2. review MCQ independiente ligado por SHA-256, con como máximo una reparación + segundo review;
3. render determinístico;
4. integrity check JSON↔HTML;
5. **interaction gate en Chromium real**: Playwright entra a Práctica y Examen, prueba una respuesta incorrecta con feedback y completa un examen 100% correcto sin revelar feedback antes de entregar;
6. el interaction gate persiste tres estados reales: feedback desktop, pregunta móvil y resultados móviles;
7. Chromium visual audit de la pantalla inicial + inspección humana de `visual-audit/desktop.png`, `visual-audit/mobile.png` y las tres capturas de `interaction-audit/`;
8. publicación atómica exacta de JSON/HTML;
9. revalidación de academic/concepts/topics/figures y engine snapshot al cerrar el run.

El interaction gate y el visual gate son distintos: el primero demuestra comportamiento; las capturas y la inspección visual demuestran legibilidad/responsividad de los estados que el usuario realmente utiliza.

Reejecutar `quiz` reemplaza atómicamente el quiz actual de esa unidad; no acumula bancos aleatorios obsoletos por defecto.
