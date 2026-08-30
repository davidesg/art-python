---
id: BUG-0057
title: el incremento de guided_identification contaba operadores FIJADOS — un AR(1) fijado en cero se leía como «la base ya lleva p=1», y seguir esa aritmética estimaba un AR libre que nadie había pedido
status: fixed
severity: medium
component: mcp-server
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: carril Claude del RUN 3 — defecto (2) de su informe
tags:
  - identification
  - file-format
references:
  - src/art/mcp_server.py (guided_identification — el incremento)
  - bugs/BUG-0052-residual-identification-suggested-a-replacing-call.md
  - docs/TODO-identification.md (el artificio `1 1 / 0.000000 0`)
  - tests/test_bug_0052_0053_incremento_y_linaje.py
---

## Summary

**Es un agujero en el arreglo de BUG-0052**, y lo encontró el analista del RUN 3.

Aquel arreglo hace que la sugerencia de órdenes sobre residuos sea el **total** y
no el incremento, y para eso necesita saber qué ARMA lleva ya la base:

```python
p_base = len(m_pre.ar[0]) if m_pre.ar else 0
```

`len()` cuenta también los operadores **fijados**. Un `.inp` con

```
** Number and orders of regular AR operators:
1 1
**
0.000000  0          ← coeficiente 0, bandera 0 = FIJO
```

declara un AR(1) presente en la estructura pero **no estimado**. Se leía como «la
base ya lleva p=1», la sugerencia decía `p = 1 + incremento`, y seguirla estimaba
un **AR libre donde el analista no había pedido ninguno**.

## Fix

Se cuentan sólo los coeficientes **libres**, leyendo las banderas (`ar_free`,
`ma_free`). Sin banderas, todos libres.

Verificado en los dos sentidos: sobre `ITCER_m10` (AR(1) fijado, `ar_free =
[[False]]`) la sugerencia vuelve a `p=0` y **no** se imprime el aviso de
incremento —no hay base ARMA libre que advertir—; sobre `PGAS_m03` (MA(1) libre)
sigue diciendo `q = 1 + 1 = 2`.

## Esto arregla el síntoma, no la causa

El artificio `1 1 / 0.000000 0` **es la forma de escribir «no hay AR»** cuando el
motor C de `fue`, o su versión Python con *wheels*, no admiten decirlo de otro
modo. La versión Python pura no tiene ese problema de especificación, así que el
artificio no es una propiedad del modelo sino de la ruta por la que se escribió
el fichero.

Eso abre tres preguntas que no están contestadas y que **hay que medir, no
suponer**: cuántos sitios más de ART cuentan órdenes con `len()`; si `npar`
—y por tanto AIC y BIC— cambia según el motor con que se escribió el `.inp`; y si
es ART quien emite el factor vacío al construir un modelo sin AR.

Quedan anotadas en `docs/TODO-identification.md`, junto con las tres soluciones
posibles. La que evita que esto vuelva por un cuarto sitio es una única función
`ordenes_libres(model)` y prohibir `len()` sobre los factores en el resto del
código.
