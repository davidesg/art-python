---
id: BUG-0037
title: guion_abandon sweeps away the very node that records the rejection — a decision node written after a failed branch hangs from it, and the cascade marks the reasoning as a dead end
status: fixed
severity: medium
component: guion
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - guion
  - map
  - documentation
references:
  - src/art/guion.py (abandon)
  - src/art/mcp_server.py (guion_node — el parámetro `parent`; guion_abandon)
  - bugs/BUG-0037-repro/repro.py
  - tests/test_bug_0035_0036_0037_verdicts_files_and_map.py
---

## Summary

`guion_node` encadena a la última entrada registrada. La secuencia natural de una
rama descartada es:

```
v10  m21   modelo que se conserva
v11  m30   modelo que se prueba          ← se va a abandonar
v12  nodo  "lo probé, ω sale con t=1,66, me quedo con el m21"
```

El nodo v12 explica **por qué** v11 se descarta, pero cuelga de v11 porque era la
última entrada. Al marcar v11 como callejón, la cascada arrastra a v12.

Y arrastrarlo es lo contrario de lo que el mapa existe para hacer. La doctrina
del `guion` lo dice en su propio código: *«lo que una iteración fallida produce
de valor NO es el modelo que se descarta, es la RAZÓN por la que se descarta —
que es lo único que impide volver a intentarlo»*. Marcar la razón como callejón
**la borra del tronco justo cuando más falta hace**.

## La cascada no está mal — está mal aplicada a los nodos

La cascada es correcta para los MODELOS: una decisión contaminada contamina lo
que se construye encima, y ésa es la propiedad que obliga a volver atrás en vez
de seguir parcheando.

Un **nodo** no es eso. Es un argumento escrito, y el argumento que suele venir
justo detrás de un modelo fallido es *el que lo condena*. No desciende del fallo:
es la conclusión que se saca de él, y pertenece al tronco que sobrevive.

## Fix

Dos piezas.

**1. `abandon` recoloca los nodos en vez de barrerlos.** Un nodo alcanzado por la
cascada se re-encadena al primer ancestro no alcanzado y conserva su estado; los
modelos se abandonan como siempre. La función devuelve ahora
`(abandonadas, recolocadas)` y `guion_abandon` lo dice en su salida:

```
**Nodos recolocados, no abandonados:** n13 (intervenciones) → ahora cuelgan de v10
```

**2. `guion_node` acepta `parent`.** Para colocarlo bien desde el principio en vez
de corregirlo después: cuando se registra la conclusión de una rama que se va a
descartar, se apunta al lugar seguro. El docstring lo explica en esos términos.

Las dos hacen falta: la primera arregla lo que ya ocurrió, la segunda evita que
vuelva a ocurrir.

## Repro

`bugs/BUG-0037-repro/repro.py` — monta la secuencia exacta (nodo de tronco →
modelo que se prueba → nodo que lo rechaza), abandona el modelo y mira qué le
pasa al nodo.

## Cómo se encontró

En el recorrido autónomo de ITCER, al descartar el segundo impulso de 2009:2. La
salida lo dijo sola:

```
Marcadas como callejón sin salida: v12 (m30), v13 (intervenciones)
```

v13 era el nodo que acababa de escribir explicando por qué v12 no valía.
