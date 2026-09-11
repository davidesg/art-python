---
id: BUG-0153
title: El pie de la figura de calibración dice «falta estructura» mientras el veredicto dice que el anómalo fabricaba la señal
status: fixed
severity: medium
component: describe
found_in: 0.2.0
fixed_in: 0.2.1
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

## Fix

**1 · Una sola lectura, en una sola función.** `_lectura_de_la_q(q_obs, q_p,
efecto)` devuelve la clave, el texto del pie (inglés, como el resto del dibujo)
y el del escaneo (español). Los dos consumidores la llaman; no queda ninguna
clasificación suelta. Eran dos cadenas de `if` con **umbrales distintos sobre la
misma cifra**, y por eso podían —y solían— llegar a conclusiones opuestas.

**2 · Y lo PRIMERO que hace es preguntar si hay algo que diagnosticar.** Con la
Q pasando, el efecto de omitir es un dato descriptivo, no un problema:

    Q already passes: this is how much it moves, not a diagnosis

    → **la Q ya pasa**, así que esto mide cuánto se mueve, no un problema que
      arreglar. Si hay que intervenir el anómalo será por otra razón —la
      identificación, la normalidad, o el suceso en sí— y eso lo dice la
      calibración del correlograma, no la Q.

Esa última frase es la que cierra el defecto: manda al instrumento que sí
contesta, en vez de emitir un veredicto que contradice al de al lado.

**3 · Y se publica la p.** Nadie miraba si la Q pasaba, entre otras cosas porque
la salida no lo decía: imprimía `Q(15) = 10.4` a secas. Ahora va con su p y con
«pasa» / «RECHAZA», y `q_pvalue` y `q_lectura` están en `data` para el carril.

## Validation

La prueba comprueba las cinco lecturas —incluida la nueva— y, sobre todo, que
**no puedan volver a divergir**: cuenta cada frase del diagnóstico en el fuente
y exige que aparezca **una sola vez** y dentro de `_lectura_de_la_q`. El conteo
ignora los comentarios a propósito: éstos citan el texto viejo como explicación
del defecto, y contarlos haría que documentar el arreglo rompiera la prueba.
