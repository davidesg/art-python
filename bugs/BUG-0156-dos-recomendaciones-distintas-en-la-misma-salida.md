---
id: BUG-0156
title: La llamada 2 con escalera da DOS recomendaciones distintas en la misma salida — la escalera dice 1a y el veredicto Q2/2008×3
status: open
severity: high
component: interventions
found_in: 0.2.0
fixed_in:
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - intervenciones
  - escalera
references:
  - BUG-0086
  - BUG-0138
  - BUG-0150
---

## Summary

`guided_intervention(..., escalera=True)` devuelve, en la misma respuesta:

    escalera   recomienda `1a` — escalón en Q4/2008, UN parámetro, «la menos mala»
    Veredicto  recomienda `Q2/2008×3` — TRES parámetros, otra fecha

Dos recomendaciones incompatibles, sin decir cuál gobierna ni por qué difieren.
El analista tiene que arbitrar entre dos partes de la misma salida.

## Root cause

Son **dos instrumentos con dos preguntas distintas** cuyos resultados se
publican como si fueran uno:

| | pregunta | acota por |
|---|---|---|
| configuraciones | ¿qué arranque y cuántos escalones admite el dato? | el MECANISMO (extiende el arranque hacia atrás) |
| escalera | ¿qué sofisticación justifica el dato? | la NAVAJA (lo más simple mientras se sostenga) |

Que discrepen no es un error: es información. Que se publiquen sin decir que
son dos preguntas, sí.

Y hay una asimetría que agrava la discrepancia: la escalera recorre `1a`, `1b`
y el episodio de L+1 escalones **desde la fecha del episodio**, mientras las
configuraciones exploran arranques hacia atrás. Así que las dos no consideran
el mismo conjunto de formas, y la comparación entre sus ganadoras no es una
comparación.

## Impact

Es el nodo donde el analista elige la forma, y la salida le da dos respuestas.
Con BUG-0138 la escalera sólo aparece cuando se pide —o sea, cuando el analista
ya duda— y lo que recibe entonces es más duda.

Sobre ITCER el analista se quedó con la del veredicto, y las notas registran
que la escalera «no concuerda».

## Fix propuesto

**Decir que son dos preguntas, y cuál gobierna para qué.** El texto ya lo tiene
a medias —«para la FORMA gobierna `incident_configurations`»— pero no aparece
cuando la escalera está delante contradiciéndolo.

Concretamente: cuando las dos ganadoras difieren, la salida debe (1) decirlo,
(2) decir en qué difieren —fecha, número de escalones, o las dos— y (3) dar el
criterio: el mecanismo acota la FORMA, la navaja acota la SOFISTICACIÓN, y si
la forma que el mecanismo admite es más sofisticada que la que la navaja
sostiene, **eso es exactamente lo que hay que discutir**, no algo que resolver
por AIC.

Y arreglar la asimetría: que la escalera parta del mismo arranque que la
configuración ganadora, o que diga que no lo hace.

## Validation

Un caso donde las dos difieran: la salida tiene que nombrar la discrepancia y
el criterio, y no puede presentar dos recomendaciones sin jerarquía.
