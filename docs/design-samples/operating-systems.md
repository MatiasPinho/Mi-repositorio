# Estados de un proceso

Esta muestra combina explicación, comparación, tabla y recuperación activa para probar una página más densa.

## Estado no significa prioridad

Un proceso puede cambiar de estado porque está ejecutándose, esperando un recurso o listo para recibir CPU. El estado describe **qué condición de ejecución tiene ahora**, no cuán importante es para el sistema.

> [!ERROR] Confusión típica
> “Listo” no significa “ejecutándose”. Significa que el proceso puede ejecutar, pero todavía no tiene asignado el procesador.

## Comparación rápida

| Estado | Qué significa | Qué necesita para avanzar |
| --- | --- | --- |
| Listo | Puede ejecutar | Recibir CPU |
| Ejecutando | Tiene CPU | Continuar o ser interrumpido |
| Bloqueado | Espera un evento/recurso | Que ocurra aquello que espera |

La tabla sirve para comparar roles; no reemplaza una explicación de las transiciones entre estados.

> [!CONNECTION] Cambio de contexto
> Cuando el sistema deja de ejecutar un proceso y pasa a otro, debe conservar el estado necesario para poder retomarlo después.

## Qué debería quedar después de leer

Podés mirar un escenario y justificar por qué un proceso está listo, ejecutando o bloqueado sin usar esos nombres como etiquetas memorizadas.

> [!RECALL] Caso corto
> Un proceso necesita leer un dato de disco y no puede continuar hasta recibirlo. ¿Qué estado esperarías durante esa espera y qué tendría que ocurrir para que vuelva a competir por CPU?
