---
id: BUG-0053
title: meg_reformulate escribía a disco un modelo que el guion nunca veía — la reformulación quedaba huérfana y lo encadenado encima colgaba del modelo anterior, rompiendo el linaje justo en la rama que el MEG existe para documentar
status: fixed
severity: medium
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 2 — defecto (d) de su informe
tags:
  - guion
  - meg
  - lineage
references:
  - src/art/mcp_server.py (meg_reformulate)
  - tests/test_bug_0052_0053_incremento_y_linaje.py
  - bugs/BUG-0053-repro/repro.py
---

## Summary

Todas las herramientas que producen un modelo aceptan `guion_path`,
`guion_name`, `guion_decision` y `guion_rationale`, y registran una versión con
`_record_to_guion`. **`meg_reformulate` no los tenía.** Escribía su
`.inp`/`.pre`/`.out` y el guion no se enteraba.

Lo grave no es la entrada que falta: es el **linaje**. Con la reformulación
ausente del guion, el modelo que se encadene encima se registra como
descendiente del modelo **anterior** a la reformulación. En el RUN 2 la cadena
real era `m03 → m06 → m07` y el mapa la enseñaba como `m03 → m07`. El analista
tuvo que anotarla a mano en el texto del abandono:

> La cadena real —`m03 → m06 → m07`— es irrecuperable del mapa. Ocurre justo en
> la rama que el ejercicio pedía documentar.

## Fix

`meg_reformulate` acepta los cuatro parámetros y registra la versión, con
`base_pre_path=src` para que `infer_parent` la cuelgue de quien toca. La decisión
por defecto dice lo que la reformulación hizo: la frecuencia, `ifadf[f]=1`, los
armónicos eliminados y si lleva testigo.

**Se registra `mc`, no `m`.** `mc` es el modelo reformulado, recargado de
`output_path` tras reestimarlo; `m` es el baseline. Una entrada con la ruta de uno
y la especificación del otro sería peor que ninguna — fue el primer intento, y
sólo se vio al comprobar que `MEGResult` no transporta ningún modelo.

## Verificación

```
v1  m03          parent=None  ifadf=[0, 0, 0]
v2  m06_MEG_f1   parent=1     ifadf=[0, 1, 0]
```

El `ifadf` distinto en cada entrada es visible gracias a BUG-0051; antes de aquel
arreglo las dos versiones se habrían escrito con la misma ecuación y el mapa no
habría podido distinguirlas ni aun registrándolas.

## Nota de proceso

El primer intento colocó el registro en `meg_frequency` —el contraste— en lugar
de en `meg_reformulate` —la que escribe el modelo—. Las dos están seguidas en el
fichero y la de arriba no produce modelo alguno, así que el guion seguía sin
escribirse y el síntoma era idéntico. Se detectó porque el test de extremo a
extremo comprobaba el fichero del guion, no el código.
