---
id: BUG-0153
title: El pie de la figura de calibración dice «falta estructura» mientras el veredicto dice que el anómalo fabricaba la señal
status: open
severity: medium
component: describe
found_in: 0.2.0
fixed_in:
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - figuras
  - presentacion
references:
  - BUG-0132
  - BUG-0152
---

## Summary

En la misma pantalla, el pie de la figura de calibración de distorsiones y el
veredicto de la tabla dicen cosas opuestas. Sobre ITCER `m00`:

    pie de la figura   «Q barely drops: structure is missing»
    veredicto          el anómalo FABRICABA la señal → intervenir la quita

Y en el texto del escaneo, dos mensajes contrarios en la misma salida:

    «la Q NO es de los anómalos: falta estructura, y una intervención no la va
     a arreglar»
    «distorsión fuerte… tratar los anómalos antes de ARMA»

Además la Q pasaba —Q(15)=10,4—, así que «falta estructura» no casa con nada.

## Root cause

`describe.py:3329`. El pie clasifica por el **efecto de omitir sobre la Q**:

```python
_lect = ("the anomalies were making Q"        if efecto <= -50 else
         "the anomaly was masking structure"  if efecto >   5 else
         "Q barely drops: structure is missing" if efecto > -20
         else "mixed")
```

Tres umbrales sobre una sola cifra, y ninguno mira si la Q **pasa**. Con una Q
que ya es adecuada, «falta estructura» es un enunciado sin contenido: no falta
nada que la Q pueda ver. La frase se hereda de un caso —Q grande que no baja al
omitir— y se aplica a otro donde no significa lo mismo.

Y el veredicto de la tabla se calcula por otra vía (los cambios de banda de la
ACF/PACF), así que nada obliga a que los dos coincidan.

## Impact

El analista recibe dos conclusiones opuestas y tiene que decidir cuál se cree.
Es el arranque del nodo de intervención, donde la pregunta es precisamente
«¿hay que intervenir?».

## Fix propuesto

1. El pie **no clasifica si la Q pasa**: dice el efecto y calla el diagnóstico.
   «Falta estructura» sólo tiene sentido cuando hay estructura que falte.
2. Pie y veredicto salen del **mismo sitio**. Hoy son dos cálculos
   independientes con dos lenguajes; que uno cite al otro o que los dos vengan
   de la calibración.

## Validation

Sobre un modelo con Q adecuada y anómalos presentes, el pie y el veredicto no
pueden afirmar cosas contrarias, y ninguno de los dos puede decir «falta
estructura».
