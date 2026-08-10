# Programar antes de escribir código

Cómo se comporta el sistema con teoría continua, definiciones y distinciones, sin depender de imágenes.

## Del problema a la solución

Antes de escribir instrucciones hay que comprender qué se quiere obtener, con qué datos se cuenta y qué condiciones ya vienen garantizadas. El diseño ordena esa comprensión en una solución independiente del lenguaje.

> [!DEFINITION] Precondición
> Una condición que el problema da por garantizada sobre los datos de entrada. Si está garantizada, no se vuelve a validar como si fuera un dato incierto.

El punto importante no es memorizar una frase, sino distinguir dos responsabilidades: el enunciado puede garantizar algo de antemano y el programa puede tener que comprobar otras restricciones por sí mismo.

> [!EXAMPLE] Ejemplo mínimo
> Si el problema garantiza que una nota siempre estará entre 1 y 10, el algoritmo puede trabajar con ese rango como condición de partida. Si la aplicación recibe datos reales sin esa garantía, entonces la validación pertenece al sistema.

## Una distinción que conviene fijar

**Analizar** responde qué hay que resolver. **Diseñar** responde cómo se va a resolver. Mezclar ambas etapas hace que una solución se ate demasiado pronto a un lenguaje o a una herramienta concreta.

```text
// diseño, todavía sin lenguaje
leer nota
si nota no está entre 1 y 10
    rechazar y volver a pedir
sino
    registrar nota
```
<!-- caption: La validación aparece porque el dato ya no viene garantizado. -->

> [!CONNECTION] Relación
> Esta separación permite que un mismo diseño pueda traducirse después a lenguajes distintos sin cambiar la lógica central.

> [!RECALL] Comprobate sin mirar
> Explicá con tus palabras por qué una precondición no es lo mismo que una validación y por qué analizar no es diseñar.

## Qué retener

- El texto normal sigue siendo la superficie principal.
- Las señales aparecen cuando codifican una función académica real.
- Un resumen no debería parecer una sucesión de tarjetas.
