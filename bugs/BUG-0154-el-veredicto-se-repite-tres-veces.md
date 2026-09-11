---
id: BUG-0154
title: El veredicto de la llamada 2 se imprime tres veces casi literal — bloque, «Veredicto» y pie
status: fixed
severity: low
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
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

## Fix

Un veredicto, una vez, y en la sección que lo anuncia.

**1 · `describe_configuraciones(conj, veredicto=False)`.** El bloque callaba o
hablaba según quién lo use, y esa es la distinción que faltaba: **suelto**
—`incident_configurations`— es lo único que hay y enuncia el suyo entero;
**empotrado** en la llamada 2, aporta el hecho —qué configuración gana y con
cuánto margen— y deja la lectura al veredicto de quien lo empotra.

**2 · La recomendación es lo que TOCA HACER**, no la conclusión otra vez:

    **Construye la forma del veredicto**: `date="Q1/2010"`, `form="step"`,
    `n_omega=2` — y verifica el ajuste.

Se conserva `d_cfg.recommendation` en el caso que sí aporta algo que el
veredicto no lleva: cuando el dato **no** identifica, que es una orden de no
elegir por AIC.

Medido sobre el mismo testigo: de **tres** enunciados del veredicto a **uno**.
La cuarta aparición de la frase es la leyenda de la notación —«se lee “fecha×N”
como N escalones…»— y ésa se queda: explica cómo leer la tabla, no concluye.

## Validation

Sobre la salida real de la llamada 2: la frase del veredicto aparece **una vez**
—excluyendo la leyenda, que no es un veredicto—, y **después** del encabezado
«## Veredicto», que es donde se decide. Más dos pruebas de lo que no puede
perderse: el bloque empotrado tiene que seguir diciendo cuál gana, y el suelto
tiene que seguir enunciándolo entero.
