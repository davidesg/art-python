---
id: BUG-0047
title: max_rounds=0 no estimaba nada — el bucle de anómalos no daba ninguna vuelta y el modelo None moría en _write_inp con un AttributeError
status: fixed
severity: medium
component: pipeline
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia — hallado al escribir el repro de BUG-0046
tags:
  - pipeline
  - robustness
  - off-by-one
references:
  - src/art/pipeline.py (_outlier_loop)
  - tests/test_bug_0047_ronda_base.py
  - bugs/BUG-0047-repro/repro.py
---

## Summary

`_outlier_loop` recorre `range(1, max_rounds + 1)`. La **ronda 1 no interviene**:
es la estimación BASE, con la lista de intervenciones vacía; las intervenciones
se añaden AL FINAL de una ronda, para la siguiente.

Así que `max_rounds` cuenta rondas de intervención y la primera vuelta no es
una. Con `max_rounds=0` —que es exactamente lo que escribe quien quiere decir
«estima, pero no me añadas intervenciones»— el rango sale **vacío**: no se
estima nada, `m_fit` se queda en `None`, y `run_full` se lo pasa a `_write_inp`,
que hace `model.interventions` y muere con

```
AttributeError: 'NoneType' object has no attribute 'interventions'
```

Un `AttributeError` en las tripas, sin mensaje, por un argumento legal en la
frontera. Y en la rama estacional el fallo es peor de leer: llega después de
haber estimado y adjudicado las dos rutas.

## Repro

```
$ python bugs/BUG-0047-repro/repro.py

max_rounds  modelo devuelto
----------------------------------
    0       ajustado
    1       ajustado
    2       ajustado
```

Antes del arreglo, la fila `0` daba
`AttributeError: 'NoneType' object has no attribute 'interventions'`.

## Fix

`for round_num in range(1, max(int(max_rounds), 1) + 1)`.

Siempre hay una estimación: sin ella no hay modelo que devolver, y «cero rondas
de intervención» es justamente la base sola. `0` y `1` coinciden, que es lo que
significan.
