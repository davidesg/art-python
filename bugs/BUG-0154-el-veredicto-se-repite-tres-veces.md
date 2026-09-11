---
id: BUG-0154
title: El veredicto de la llamada 2 se imprime tres veces casi literal — bloque, «Veredicto» y pie
status: open
severity: low
component: mcp-tools
found_in: 0.2.0
fixed_in:
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - presentacion
  - intervenciones
references:
  - BUG-0120
---

## Summary

La llamada 2 de `guided_intervention` publica el mismo veredicto **tres veces**,
casi con las mismas palabras: en el bloque de la configuración ganadora, en la
sección «Veredicto», y en el pie de la respuesta.

Es el mismo defecto que BUG-0120 —`meg_reformulate` imprimía el bloque del
modelo dos veces— en otra herramienta.

## Impact

Bajo por separado y alto acumulado: la llamada 2 es la respuesta más larga del
nodo, y repetir tres veces lo mismo entierra lo que **no** se repite —las
configuraciones rivales, la lectura de dominio, el aviso de que el dato no
identifica—. Hace que el nodo se lea, en palabras del analista, «enrevesado».

## Fix propuesto

Un veredicto, una vez, y en el sitio donde se decide. Las otras dos apariciones
o se quitan o se convierten en lo que aportan de verdad —la ganancia y su
contraste, la fecha— sin reenunciar la conclusión.

Conviene hacerlo con la fase 2 de `ORDEN.md` a la vista: una sola capa de
salida hace estructural lo que aquí es disciplina.

## Validation

Prueba sobre la salida de la llamada 2: la frase del veredicto aparece **una
vez**.
